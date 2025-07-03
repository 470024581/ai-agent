from dotenv import load_dotenv
load_dotenv() # Load .env file at the very beginning

#!/usr/bin/env python3
"""
Smart Backend Service Startup Script
Supports startup configuration for development and production environments
Now integrated with LangServe functionality
"""

import sys
import os
import subprocess
from pathlib import Path
import uvicorn
import argparse

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from src.config.config import config, check_environment
from src.agents.intelligent_agent import initialize_app_state

def run_command(command, description):
    """Run a command and handle errors."""
    print(f"\n🚀 {description}...")
    try:
        # For scripts, ensure we use the python interpreter from sys.executable
        if command[0].endswith(".py"):
            cmd_list = [sys.executable] + command
        else:
            cmd_list = command
            
        result = subprocess.run(cmd_list, shell=False, check=True, capture_output=True, text=True, cwd=Path(__file__).parent)
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        if e.stderr:
            print(f"Error details: {e.stderr}")
        return False

def check_python():
    """Check if Python is available."""
    try:
        result = subprocess.run([sys.executable, "--version"], capture_output=True, text=True)
        python_version = result.stdout.strip()
        print(f"✓ Python found: {python_version}")
        return True
    except Exception as e:
        print(f"❌ Python check failed: {e}")
        return False

def check_dependencies():
    """Check if required packages are installed."""
    # Updated list of core dependencies including LangServe
    required_packages = ['fastapi', 'uvicorn', 'pydantic', 'langchain', 'langchain_openai', 'langserve'] 
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing packages: {missing_packages}")
        requirements_file = Path(__file__).parent / "requirements.txt"
        if requirements_file.exists():
            print(f"Installing dependencies from {requirements_file}...")
            return run_command([sys.executable, "-m", "pip", "install", "-r", str(requirements_file)], "Installing dependencies")
        else:
            print(f"❌ requirements.txt not found at {requirements_file}. Please create it or install manually.")
            return False
    else:
        print("✓ All required packages are installed (including LangServe)")
        return True

def start_server(reload=True):
    """Start the FastAPI server"""
    print("\n🌟 Starting FastAPI server...")
    os.environ["PYTHONPATH"] = str(Path(__file__).parent)
    uvicorn.run("src.main:app", host=config.HOST, port=config.PORT, reload=reload)

def main():
    """Main startup function"""
    parser = argparse.ArgumentParser(description="Smart Backend Service (LangServe Integrated)")
    parser.add_argument("--host", default=config.HOST, help="Server address")
    parser.add_argument("--port", type=int, default=config.PORT, help="Server port")
    parser.add_argument("--reload", action="store_true", default=config.RELOAD, help="Enable hot reload")
    parser.add_argument("--no-reload", action="store_true", help="Disable hot reload")
    parser.add_argument("--prod", action="store_true", help="Production mode")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")
    
    args = parser.parse_args()
    
    # If production mode is specified, override configuration
    if args.prod:
        config.DEBUG = False
        config.RELOAD = False
        args.reload = False
    
    # If no-reload is specified, override reload setting
    if args.no_reload:
        args.reload = False
    
    print("🚀 Starting Smart Backend Service (LangServe Integrated)...")
    print(f"📍 Service address: http://{args.host}:{args.port}")
    print(f"📖 API documentation: http://{args.host}:{args.port}/docs")
    print(f"🔗 LangServe routes: http://{args.host}:{args.port}/langserve/*/docs")
    
    # Check environment configuration
    check_environment()
    
    # Ensure necessary directories exist
    config.ensure_directories()
    
    # Initialize application state
    print("\n🔧 Initializing application state...")
    try:
        initialize_app_state()
        print("✅ Application state initialization completed")
    except Exception as e:
        print(f"❌ Application state initialization failed: {e}")
        print("⚠️  Service may not work properly")
    
    print(f"\n🌟 Startup mode: {'Development' if args.reload else 'Production'}")
    print("🔧 Integrated features: LangServe + FastAPI")
    print("Press Ctrl+C to stop the service\n")
    
    # Start server
    try:
        # Configure Python logging before starting uvicorn
        import logging
        log_level = config.LOG_LEVEL.upper()
        
        # Set the root logger level
        logging.getLogger().setLevel(getattr(logging, log_level, logging.INFO))
        
        # Set specific loggers for our application
        logging.getLogger("app").setLevel(getattr(logging, log_level, logging.INFO))
        logging.getLogger("app.langgraph_flow").setLevel(getattr(logging, log_level, logging.INFO))
        logging.getLogger("app.agent").setLevel(getattr(logging, log_level, logging.INFO))
        
        print(f"🔧 Python logging configured - Level: {log_level}")
        
        start_server(reload=args.reload)
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
    except Exception as e:
        print(f"\n❌ Server startup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Ensure the script is run from the project root for correct relative paths
    os.chdir(Path(__file__).resolve().parent)
    main() 