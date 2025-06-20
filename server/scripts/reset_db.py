#!/usr/bin/env python3
"""
简单的数据库重置脚本
"""
import sys
from pathlib import Path
import asyncio

# Adjust import path to access app.db
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.db import initialize_database_schema, import_csv_data_to_db, DATABASE_PATH

async def reset_database():
    """重置数据库"""
    print("🔄 重置数据库...")
    
    # 删除现有数据库
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()
        print("✅ 删除旧数据库")
    
    # 重新初始化
    initialize_database_schema()
    print("✅ 创建新数据库结构")
    
    # 导入数据
    import_csv_data_to_db()
    print("✅ 导入CSV数据")
    
    print("🎉 数据库重置完成!")

if __name__ == "__main__":
    asyncio.run(reset_database()) 