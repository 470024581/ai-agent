from dotenv import load_dotenv
load_dotenv() # Load .env file at the very beginning

#!/usr/bin/env python3
"""
Smart 后端服务启动脚本
支持开发和生产环境的启动配置
现已集成 LangServe 功能
"""

import sys
import os
import subprocess
from pathlib import Path
import uvicorn
import argparse

# 添加当前目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from config import config, check_environment
from app.agent import initialize_app_state

def run_command(command, description):
    """Run a command and handle errors."""
    print(f"\n{description}...")
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

def main():
    """主启动函数"""
    parser = argparse.ArgumentParser(description="Smart 后端服务 (LangServe集成)")
    parser.add_argument("--host", default=config.HOST, help="服务器地址")
    parser.add_argument("--port", type=int, default=config.PORT, help="服务器端口")
    parser.add_argument("--reload", action="store_true", default=config.RELOAD, help="启用热重载")
    parser.add_argument("--no-reload", action="store_true", help="禁用热重载")
    parser.add_argument("--prod", action="store_true", help="生产模式")
    parser.add_argument("--workers", type=int, default=1, help="工作进程数量")
    
    args = parser.parse_args()
    
    # 如果指定生产模式，覆盖配置
    if args.prod:
        config.DEBUG = False
        config.RELOAD = False
        args.reload = False
    
    # 如果指定不重载，覆盖重载设置
    if args.no_reload:
        args.reload = False
    
    print("🚀 启动 Smart 后端服务 (LangServe 集成)...")
    print(f"📍 服务地址: http://{args.host}:{args.port}")
    print(f"📖 API文档: http://{args.host}:{args.port}/docs")
    print(f"🔗 LangServe路由: http://{args.host}:{args.port}/langserve/*/docs")
    
    # 检查环境配置
    check_environment()
    
    # 确保必要目录存在
    config.ensure_directories()
    
    # 初始化应用状态
    print("\n🔧 初始化应用状态...")
    try:
        initialize_app_state()
        print("✅ 应用状态初始化完成")
    except Exception as e:
        print(f"❌ 应用状态初始化失败: {e}")
        print("⚠️  服务可能无法正常工作")
    
    print(f"\n🌟 启动模式: {'开发' if args.reload else '生产'}")
    print("🔧 集成功能: LangServe + FastAPI")
    print("按 Ctrl+C 停止服务\n")
    
    # 启动服务器
    try:
        uvicorn.run(
            "app.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            workers=args.workers if not args.reload else 1,
            log_level=config.LOG_LEVEL.lower(),
            access_log=True
        )
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
    except Exception as e:
        print(f"\n❌ 服务器启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Ensure the script is run from the project root for correct relative paths
    os.chdir(Path(__file__).resolve().parent)
    main() 