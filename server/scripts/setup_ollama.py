#!/usr/bin/env python3
"""
Ollama Setup Script - Automatically install and configure Ollama and Mistral model
"""
import os
import sys
import subprocess
import requests
import platform
import time
from pathlib import Path

def check_ollama_installed():
    """Check if Ollama is installed"""
    try:
        result = subprocess.run(['ollama', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Ollama installed: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    
    print("❌ Ollama not installed")
    return False

def install_ollama():
    """Install Ollama"""
    system = platform.system().lower()
    
    print("🔧 Starting Ollama installation...")
    
    if system == "windows":
        print("Please manually download and install Ollama for Windows:")
        print("https://ollama.ai/download/windows")
        return False
    elif system == "darwin":  # macOS
        print("Installing Ollama on macOS...")
        try:
            subprocess.run(['brew', 'install', 'ollama'], check=True)
            print("✅ Ollama installation completed")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Please manually install Ollama:")
            print("curl -fsSL https://ollama.ai/install.sh | sh")
            return False
    else:  # Linux
        print("Installing Ollama on Linux...")
        try:
            install_script = subprocess.run([
                'curl', '-fsSL', 'https://ollama.ai/install.sh'
            ], capture_output=True, text=True, check=True)
            
            subprocess.run(['sh'], input=install_script.stdout, text=True, check=True)
            print("✅ Ollama installation completed")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Installation failed: {e}")
            return False

def start_ollama_service():
    """Start Ollama service"""
    print("🚀 Starting Ollama service...")
    
    # Check if service is already running
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            print("✅ Ollama service is running")
            return True
    except requests.exceptions.RequestException:
        pass
    
    # Try to start service
    system = platform.system().lower()
    
    try:
        if system == "windows":
            # Windows: start in background
            subprocess.Popen(['ollama', 'serve'], 
                           creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            # macOS/Linux: start in background
            subprocess.Popen(['ollama', 'serve'], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
        
        # Wait for service to start
        print("⏳ Waiting for Ollama service to start...")
        for i in range(10):
            time.sleep(2)
            try:
                response = requests.get("http://localhost:11434/api/tags", timeout=3)
                if response.status_code == 200:
                    print("✅ Ollama service started successfully")
                    return True
            except requests.exceptions.RequestException:
                continue
        
        print("❌ Ollama service startup timeout")
        return False
        
    except Exception as e:
        print(f"❌ Failed to start Ollama service: {e}")
        return False

def list_available_models():
    """List available models"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=10)
        if response.status_code == 200:
            models = response.json().get('models', [])
            if models:
                print("\n📋 Installed models:")
                for model in models:
                    name = model.get('name', 'unknown')
                    size = model.get('size', 0)
                    size_gb = size / (1024**3) if size > 0 else 0
                    print(f"  - {name} ({size_gb:.1f} GB)")
                return [model.get('name') for model in models]
            else:
                print("📋 No models installed")
                return []
        else:
            print(f"❌ Failed to get model list: HTTP {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Failed to get model list: {e}")
        return []

def pull_model(model_name):
    """Download model"""
    print(f"📥 Downloading model {model_name}...")
    
    try:
        # Use ollama pull command to download model
        process = subprocess.Popen(
            ['ollama', 'pull', model_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            universal_newlines=True
        )
        
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(f"  {output.strip()}")
        
        if process.returncode == 0:
            print(f"✅ Model {model_name} download completed")
            return True
        else:
            print(f"❌ Model {model_name} download failed")
            return False
            
    except Exception as e:
        print(f"❌ Failed to download model: {e}")
        return False

def test_model(model_name):
    """Test model"""
    print(f"🧪 Testing model {model_name}...")
    
    try:
        test_data = {
            "model": model_name,
            "prompt": "Hello, please reply 'Test successful'",
            "stream": False
        }
        
        response = requests.post(
            "http://localhost:11434/api/generate",
            json=test_data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            test_response = result.get('response', '').strip()
            print(f"✅ Model test successful")
            print(f"  Test response: {test_response}")
            return True
        else:
            print(f"❌ Model test failed: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Model test failed: {e}")
        return False

def create_env_file():
    """Create environment configuration file"""
    env_file = Path(__file__).parent.parent / ".env"
    
    if env_file.exists():
        print(f"📝 Updating existing environment file: {env_file}")
        # Read existing configuration
        with open(env_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update LLM configuration
        lines = content.split('\n')
        updated_lines = []
        llm_config_updated = False
        
        for line in lines:
            if line.startswith('LLM_PROVIDER='):
                updated_lines.append('LLM_PROVIDER=ollama')
                llm_config_updated = True
            elif line.startswith('OLLAMA_BASE_URL='):
                updated_lines.append('OLLAMA_BASE_URL=http://localhost:11434')
            elif line.startswith('OLLAMA_MODEL='):
                updated_lines.append('OLLAMA_MODEL=mistral')
            else:
                updated_lines.append(line)
        
        # Add missing configurations
        if not any(line.startswith('LLM_PROVIDER=') for line in lines):
            updated_lines.append('LLM_PROVIDER=ollama')
        if not any(line.startswith('OLLAMA_BASE_URL=') for line in lines):
            updated_lines.append('OLLAMA_BASE_URL=http://localhost:11434')
        if not any(line.startswith('OLLAMA_MODEL=') for line in lines):
            updated_lines.append('OLLAMA_MODEL=mistral')
        if not any(line.startswith('OLLAMA_TIMEOUT=') for line in lines):
            updated_lines.append('OLLAMA_TIMEOUT=300')
        
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(updated_lines))
            
        print("✅ Environment file updated")
    else:
        print(f"📝 Creating new environment file: {env_file}")
        env_content = """# LLM Configuration
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
OLLAMA_TIMEOUT=300

# Other configurations can be added below
"""
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(env_content)
        
        print("✅ Environment file created")

def show_next_steps():
    """Show next steps"""
    print("\n🎉 Ollama setup completed!")
    print("\nNext steps:")
    print("1. Restart your application to load new configurations")
    print("2. Your application will now use Ollama local LLM")
    print("3. If you need other models, use: ollama pull <model_name>")
    print("\nAvailable models:")
    print("  - mistral (recommended, lightweight)")
    print("  - llama2 (general purpose)")
    print("  - codellama (programming)")
    print("  - neural-chat (conversation)")

def main():
    """Main function"""
    print("🚀 Ollama Automatic Setup Script")
    print("=" * 40)
    
    try:
        # 1. Check if Ollama is installed
        if not check_ollama_installed():
            print("\n📦 Installing Ollama...")
            if not install_ollama():
                print("❌ Ollama installation failed. Please install manually.")
                sys.exit(1)
        
        # 2. Start Ollama service
        print("\n🚀 Starting Ollama service...")
        if not start_ollama_service():
            print("❌ Failed to start Ollama service")
            sys.exit(1)
        
        # 3. Check existing models
        print("\n📋 Checking existing models...")
        existing_models = list_available_models()
        
        # 4. Download mistral model (if not exists)
        mistral_installed = any('mistral' in model for model in existing_models)
        if not mistral_installed:
            print("\n📥 Downloading Mistral model...")
            if not pull_model('mistral'):
                print("❌ Failed to download Mistral model")
                sys.exit(1)
        else:
            print("✅ Mistral model already installed")
        
        # 5. Test model
        print("\n🧪 Testing Mistral model...")
        if not test_model('mistral'):
            print("❌ Model test failed")
            sys.exit(1)
        
        # 6. Create/update environment file
        print("\n📝 Configuring environment...")
        create_env_file()
        
        # 7. Show completion message
        show_next_steps()
        
    except KeyboardInterrupt:
        print("\n❌ Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 