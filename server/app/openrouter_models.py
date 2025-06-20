#!/usr/bin/env python3
"""
OpenRouter 模型配置工具
"""

# 可用的OpenRouter模型
AVAILABLE_MODELS = {
    "免费模型": {
        "meta-llama/llama-3-8b-instruct:free": "Llama 3 8B - 免费",
        "microsoft/phi-3-mini-128k-instruct:free": "Phi-3 Mini - 免费",
        "google/gemma-7b-it:free": "Gemma 7B - 免费",
    },
    "经济型模型": {
        "anthropic/claude-3-haiku:beta": "Claude 3 Haiku - 快速经济",
        "openai/gpt-3.5-turbo": "GPT-3.5 Turbo - 经典选择",
        "google/gemini-flash-1.5": "Gemini Flash - 快速响应",
    },
    "高性能模型": {
        "anthropic/claude-3-sonnet:beta": "Claude 3 Sonnet - 平衡性能",
        "openai/gpt-4-turbo": "GPT-4 Turbo - 强大智能",
        "google/gemini-pro-1.5": "Gemini Pro - 谷歌旗舰",
    }
}

def list_models():
    """列出所有可用模型"""
    print("🤖 OpenRouter 可用模型:")
    print("=" * 50)
    
    for category, models in AVAILABLE_MODELS.items():
        print(f"\n📂 {category}:")
        for model_id, description in models.items():
            print(f"   • {model_id}")
            print(f"     {description}")

def switch_model(model_id: str, config_path: str = '../config/config.py'): # Adjusted path
    """切换到指定模型"""
    try:
        # 检查模型是否在可用列表中
        all_models = {}
        for category in AVAILABLE_MODELS.values():
            all_models.update(category)
        
        if model_id not in all_models:
            print(f"❌ 模型 '{model_id}' 不在可用列表中")
            print("💡 使用 python app/openrouter_models.py list 查看可用模型") # Adjusted help path
            return False
        
        # 读取当前配置
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 更新模型配置
        import re
        # 找到OPENAI_MODEL行并替换
        pattern = r'OPENAI_MODEL = "[^"]*"'
        new_line = f'OPENAI_MODEL = "{model_id}"'
        
        if re.search(pattern, content):
            new_content = re.sub(pattern, new_line, content)
        else:
            # 如果没找到，添加到文件末尾
            new_content = content.rstrip() + f'\nOPENAI_MODEL = "{model_id}"\n' # Ensure newline
        
        # 写回文件
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"✅ 已切换到模型: {model_id}")
        print(f"📝 描述: {all_models[model_id]}")
        print("\n🔄 请重启服务器使配置生效:")
        print("   (cd .. && uvicorn app.main:app --reload --port 8001)  # If running from app dir")
        print("   (uvicorn app.main:app --reload --port 8001)           # If running from root dir")
        
        return True
        
    except FileNotFoundError:
        print(f"❌ 配置文件未找到: {config_path}")
        print("确保 config/config.py 文件存在")
        return False
    except Exception as e:
        print(f"❌ 切换失败: {e}")
        return False

def test_model(config_path: str = '../config/config.py'): # Adjusted path
    """测试当前模型"""
    print("🧪 测试 OpenRouter 连接...")
    
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
        
        # 测试简单查询
        response = llm.invoke("Hello! Please respond with 'OpenRouter connection successful.'")
        
        print("✅ 连接成功!")
        print(f"📝 模型: {config_module.OPENAI_MODEL}")
        print(f"💬 响应: {response.content}")
        
    except FileNotFoundError:
        print(f"❌ 配置文件未找到: {config_path}")
    except AttributeError as e:
        print(f"❌ 配置错误: {e} - 请确保 OPENAI_MODEL 和 OPENAI_API_KEY 在 config.py 中定义")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        print("💡 请检查API Key和网络连接")

if __name__ == "__main__":
    import sys
    import os

    # Determine the correct config path based on execution context
    # This script is now in app/, so config is in ../config/
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_file_path = os.path.join(current_dir, '..', 'config', 'config.py')
    
    if len(sys.argv) < 2:
        print("OpenRouter 模型配置工具 (位于 app/ 目录)")
        print("\n使用方法 (从项目根目录运行):")
        print("  python app/openrouter_models.py list                    # 列出所有模型")
        print("  python app/openrouter_models.py switch <model_id>       # 切换模型")
        print("  python app/openrouter_models.py test                    # 测试连接")
        print("\n示例:")
        print("  python app/openrouter_models.py switch anthropic/claude-3-haiku:beta")
    
    elif sys.argv[1] == "list":
        list_models()
    elif sys.argv[1] == "switch" and len(sys.argv) > 2:
        switch_model(sys.argv[2], config_path=config_file_path)
    elif sys.argv[1] == "test":
        test_model(config_path=config_file_path)
    else:
        print("❌ 无效命令")
        print("使用 python app/openrouter_models.py 查看帮助") 