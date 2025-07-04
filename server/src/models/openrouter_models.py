#!/usr/bin/env python3
"""
OpenRouter Model Configuration Tool
"""

# Available OpenRouter models
AVAILABLE_MODELS = {
    "Free Models": {
        "meta-llama/llama-3-8b-instruct:free": "Llama 3 8B - Free",
        "microsoft/phi-3-mini-128k-instruct:free": "Phi-3 Mini - Free",
        "google/gemma-7b-it:free": "Gemma 7B - Free",
    },
    "Economic Models": {
        "anthropic/claude-3-haiku:beta": "Claude 3 Haiku - Fast & Economical",
        "openai/gpt-3.5-turbo": "GPT-3.5 Turbo - Classic Choice",
        "google/gemini-flash-1.5": "Gemini Flash - Fast Response",
    },
    "High-Performance Models": {
        "anthropic/claude-3-sonnet:beta": "Claude 3 Sonnet - Balanced Performance",
        "openai/gpt-4-turbo": "GPT-4 Turbo - Powerful Intelligence",
        "google/gemini-pro-1.5": "Gemini Pro - Google Flagship",
    }
}

def list_models():
    """List all available models"""
    print("🤖 Available OpenRouter Models:")
    print("=" * 50)
    
    for category, models in AVAILABLE_MODELS.items():
        print(f"\n📂 {category}:")
        for model_id, description in models.items():
            print(f"   • {model_id}")
            print(f"     {description}")

def switch_model(model_id: str, config_path: str = '../config/config.py'): # Adjusted path
    """Switch to specified model"""
    try:
        # Check if model is in available list
        all_models = {}
        for category in AVAILABLE_MODELS.values():
            all_models.update(category)
        
        if model_id not in all_models:
            print(f"❌ Model '{model_id}' not found in available list")
            print("💡 Use python src/models/openrouter_models.py list to view available models") # Adjusted help path
            return False
        
        # Read current configuration
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update model configuration
        import re
        # Find OPENAI_MODEL line and replace
        pattern = r'OPENAI_MODEL = "[^"]*"'
        new_line = f'OPENAI_MODEL = "{model_id}"'
        
        if re.search(pattern, content):
            new_content = re.sub(pattern, new_line, content)
        else:
            # If not found, add to end of file
            new_content = content.rstrip() + f'\nOPENAI_MODEL = "{model_id}"\n' # Ensure newline
        
        # Write back to file
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"✅ Switched to model: {model_id}")
        print(f"📝 Description: {all_models[model_id]}")
        print("\n🔄 Please restart server for configuration to take effect:")
        print("   (cd .. && uvicorn src.main:app --reload --port 8001)  # If running from src dir")
        print("   (uvicorn src.main:app --reload --port 8001)           # If running from root dir")
        
        return True
        
    except FileNotFoundError:
        print(f"❌ Configuration file not found: {config_path}")
        print("Ensure config/config.py file exists")
        return False
    except Exception as e:
        print(f"❌ Switch failed: {e}")
        return False

def test_model(config_path: str = '../config/config.py'): # Adjusted path
    """Test current model"""
    print("🧪 Testing OpenRouter connection...")
    
    try:
        # Dynamically import config based on path
        import importlib.util
        spec = importlib.util.spec_from_file_location("config_module", config_path)
        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)
        
        from langchain_openai import ChatOpenAI
        
        llm_kwargs = {
            "model_name": config_module.OPENAI_MODEL,
            "temperature": 0.3,
            "openai_api_key": config_module.OPENAI_API_KEY
        }
        
        if hasattr(config_module, 'OPENAI_BASE_URL') and config_module.OPENAI_BASE_URL:
            llm_kwargs["openai_api_base"] = config_module.OPENAI_BASE_URL
        
        llm = ChatOpenAI(**llm_kwargs)
        
        # Test simple query
        response = llm.invoke("Hello! Please respond with 'OpenRouter connection successful.'")
        
        # Handle different response formats
        if hasattr(response, 'content'):
            response_text = response.content
        else:
            response_text = str(response)
        
        print("✅ Connection successful!")
        print(f"📝 Model: {config_module.OPENAI_MODEL}")
        print(f"💬 Response: {response_text}")
        
    except FileNotFoundError:
        print(f"❌ Configuration file not found: {config_path}")
    except AttributeError as e:
        print(f"❌ Configuration error: {e} - Ensure OPENAI_MODEL and OPENAI_API_KEY are defined in config.py")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("💡 Please check API Key and network connection")

if __name__ == "__main__":
    import sys
    import os

    # Determine the correct config path based on execution context
    # This script is now in src/models/, so config is in ../config/
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_file_path = os.path.join(current_dir, '..', 'config', 'config.py')
    
    if len(sys.argv) < 2:
        print("OpenRouter Model Configuration Tool (in src/models/ directory)")
        print("\nUsage (run from project root directory):")
        print("  python src/models/openrouter_models.py list                    # List all models")
        print("  python src/models/openrouter_models.py switch <model_id>       # Switch model")
        print("  python src/models/openrouter_models.py test                    # Test connection")
        print("\nExample:")
        print("  python src/models/openrouter_models.py switch anthropic/claude-3-haiku:beta")
    
    elif sys.argv[1] == "list":
        list_models()
    elif sys.argv[1] == "switch" and len(sys.argv) > 2:
        switch_model(sys.argv[2], config_path=config_file_path)
    elif sys.argv[1] == "test":
        test_model(config_path=config_file_path)
    else:
        print("❌ Invalid command")
        print("Use python src/models/openrouter_models.py for help") 