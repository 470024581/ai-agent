#!/usr/bin/env python3
"""
创建.env配置文件
"""

def create_env_file():
    """创建.env文件"""
    env_content = """# Smart  Agent 环境配置文件
# OpenAI API 配置
OPENAI_API_KEY=123456

# 其他可选配置
# OPENAI_BASE_URL=https://api.openai.com/v1
# OPENAI_MODEL=gpt-3.5-turbo
"""
    
    try:
        with open('.env', 'w', encoding='utf-8') as f:
            f.write(env_content)
        print("✅ .env文件创建成功!")
        print("📝 配置内容:")
        print("   OPENAI_API_KEY=123456")
        print("\n💡 提醒:")
        print("   - 真实的OpenAI API Key通常以'sk-'开头")
        print("   - 如果你有真实的API Key，请替换'123456'")
        print("   - 重启服务器后配置生效")
        
    except Exception as e:
        print(f"❌ 创建.env文件失败: {e}")

if __name__ == "__main__":
    create_env_file() 