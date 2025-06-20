#!/usr/bin/env python3
"""
切换到本地模式（禁用OpenAI API）
"""

# Adjust path to config.py, assuming scripts/ and config/ are siblings
CONFIG_FILE_PATH = "../config/config.py"

def switch_to_local_mode():
    """切换到本地模式"""
    try:
        # 读取当前配置
        with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 将真实API Key注释掉
        new_content = content.replace(
            'OPENAI_API_KEY = "sk-proj-',
            '# OPENAI_API_KEY = "sk-proj-'  # 注释掉真实key
        ).replace(
            'OPENAI_API_KEY = "sk-or-',
            '# OPENAI_API_KEY = "sk-or-' # 注释掉OpenRouter真实key
        )
        
        # 添加本地模式配置
        # Ensure we are not duplicating the local_mode key if it already exists from a previous run
        import re
        if not re.search(r'^OPENAI_API_KEY\s*=\s*"local_mode"\s*# 本地模式', content, flags=re.MULTILINE):
            if '# 本地模式配置' not in new_content:
                 new_content += '\n\n# 本地模式配置（避免API配额问题）\nOPENAI_API_KEY = "local_mode"  # 本地模式\n'
            else: # if the section exists but key is commented or different
                new_content = re.sub(r'(#\s*)?OPENAI_API_KEY\s*=\s*".*"\s*(#.*)?', 'OPENAI_API_KEY = "local_mode"  # 本地模式', new_content, count=1)
        
        # 写回文件
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print("✅ 已切换到本地模式!")
        print(f"📝 配置文件 '{CONFIG_FILE_PATH}' 已更新:")
        print("   - 真实API Key已注释")
        print("   - OPENAI_API_KEY 设置为 \"local_mode\"")
        print("   - 所有功能仍然可用（使用数据库+基础分析）")
        print("\n🔄 请重启服务器 (从项目根目录运行):")
        print("   python start.py")
        
        print("\n💡 功能说明:")
        print("   ✅ 销售查询 - 基于数据库数据")
        print("   ✅ 库存检查 - 完整功能")
        print("   ✅ 报表生成 - 结构化报告")
        print("   ✅ 图表数据 - 完整支持")
        print("   ❌ AI增强分析 - 暂时禁用")
        
    except FileNotFoundError:
        print(f"❌ 配置文件未找到: {CONFIG_FILE_PATH}")
        print("   请确保 config/config.py 文件存在并且此脚本从 scripts/ 目录运行, 或从项目根目录使用 python scripts/switch_to_local_mode.py 运行")
    except Exception as e:
        print(f"❌ 切换失败: {e}")

if __name__ == "__main__":
    switch_to_local_mode() 