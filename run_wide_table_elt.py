#!/usr/bin/env python3
"""
宽表架构ELT主控制脚本
Main Control Script for Wide Table Architecture ELT
"""

import sqlite3
import sys
import os
from datetime import datetime

def create_tables(db_path: str = "data/smart.db"):
    """创建表结构"""
    print("=" * 60)
    print("创建宽表架构表结构...")
    print("=" * 60)
    
    # 读取SQL脚本
    with open("create_wide_table_schema.sql", "r", encoding="utf-8") as f:
        sql_script = f.read()
    
    # 连接数据库并执行脚本
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 执行SQL脚本
        cursor.executescript(sql_script)
        conn.commit()
        print("表结构创建成功！")
        
        # 显示创建的表
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name LIKE 'dim_%' OR name LIKE 'dwd_%' OR name LIKE 'dws_%'
            ORDER BY name
        """)
        tables = cursor.fetchall()
        
        print("\n创建的表:")
        for table in tables:
            print(f"  - {table[0]}")
            
    except Exception as e:
        print(f"表结构创建失败: {str(e)}")
        raise
    finally:
        conn.close()

def run_elt_process():
    """运行ELT流程"""
    print("\n" + "=" * 60)
    print("开始ELT数据处理流程...")
    print("=" * 60)
    
    try:
        # 导入ELT处理器
        from etl_implementation import ELTProcessor
        
        # 创建处理器并运行
        processor = ELTProcessor()
        processor.run_full_elt_process()
        
        print("ELT流程完成！")
        
    except Exception as e:
        print(f"ELT流程失败: {str(e)}")
        raise

def verify_data(db_path: str = "data/smart.db"):
    """验证数据质量和完整性"""
    print("\n" + "=" * 60)
    print("验证数据质量和完整性...")
    print("=" * 60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查各层数据量
        tables_to_check = [
            "dim_customer",
            "dim_product", 
            "dwd_sales_detail",
            "dwd_inventory_detail",
            "dws_sales_cube",
            "dws_inventory_cube"
        ]
        
        print("数据量统计:")
        for table in tables_to_check:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count:,} 条记录")
        
        # 检查数据质量
        print("\n数据质量检查:")
        
        # 检查销售数据质量
        cursor.execute("""
            SELECT 
                COUNT(*) as total_records,
                AVG(data_quality_score) as avg_quality_score,
                MIN(data_quality_score) as min_quality_score,
                COUNT(CASE WHEN data_quality_score < 80 THEN 1 END) as low_quality_records
            FROM dwd_sales_detail
        """)
        sales_quality = cursor.fetchone()
        print(f"  销售数据质量: 总计 {sales_quality[0]:,} 条，平均质量分数 {sales_quality[1]:.1f}，最低分数 {sales_quality[2]}，低质量记录 {sales_quality[3]:,} 条")
        
        # 检查库存数据质量
        cursor.execute("""
            SELECT 
                COUNT(*) as total_records,
                AVG(data_quality_score) as avg_quality_score,
                MIN(data_quality_score) as min_quality_score,
                COUNT(CASE WHEN data_quality_score < 80 THEN 1 END) as low_quality_records
            FROM dwd_inventory_detail
        """)
        inventory_quality = cursor.fetchone()
        print(f"  库存数据质量: 总计 {inventory_quality[0]:,} 条，平均质量分数 {inventory_quality[1]:.1f}，最低分数 {inventory_quality[2]}，低质量记录 {inventory_quality[3]:,} 条")
        
        # 检查数据一致性
        print("\n数据一致性检查:")
        
        # 检查销售金额计算一致性
        cursor.execute("""
            SELECT COUNT(*) FROM dwd_sales_detail 
            WHERE ABS(calculated_total - total_amount) > 0.01
        """)
        inconsistent_sales = cursor.fetchone()[0]
        print(f"  销售金额计算不一致记录: {inconsistent_sales:,} 条")
        
        # 检查外键完整性
        cursor.execute("""
            SELECT COUNT(*) FROM dwd_sales_detail s
            LEFT JOIN dim_customer c ON s.customer_id = c.customer_id
            WHERE s.customer_id IS NOT NULL AND c.customer_id IS NULL
        """)
        missing_customers = cursor.fetchone()[0]
        print(f"  缺失客户维度记录: {missing_customers:,} 条")
        
        cursor.execute("""
            SELECT COUNT(*) FROM dwd_sales_detail s
            LEFT JOIN dim_product p ON s.product_id = p.product_id
            WHERE p.product_id IS NULL
        """)
        missing_products = cursor.fetchone()[0]
        print(f"  缺失产品维度记录: {missing_products:,} 条")
        
        print("数据验证完成！")
        
    except Exception as e:
        print(f"数据验证失败: {str(e)}")
        raise
    finally:
        conn.close()

def show_sample_queries(db_path: str = "data/smart.db"):
    """显示示例查询"""
    print("\n" + "=" * 60)
    print("示例查询结果...")
    print("=" * 60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 示例1: 销售趋势分析
        print("1. 销售趋势分析 (最近7天):")
        cursor.execute("""
            SELECT 
                sale_date,
                COUNT(*) as daily_transactions,
                SUM(total_amount) as daily_revenue,
                AVG(total_amount) as avg_transaction_value
            FROM dwd_sales_detail
            WHERE sale_date >= date('now', '-7 days')
            GROUP BY sale_date
            ORDER BY sale_date DESC
            LIMIT 7
        """)
        sales_trend = cursor.fetchall()
        for row in sales_trend:
            print(f"  {row[0]}: {row[1]:,} 笔交易, 收入 ${row[2]:,.2f}, 平均 ${row[3]:,.2f}")
        
        # 示例2: 产品性能分析
        print("\n2. 产品性能分析 (Top 5):")
        cursor.execute("""
            SELECT 
                p.product_name,
                p.category,
                COUNT(*) as sales_count,
                SUM(s.total_amount) as total_revenue,
                AVG(s.total_amount) as avg_transaction_value
            FROM dwd_sales_detail s
            LEFT JOIN dim_product p ON s.product_id = p.product_id
            GROUP BY s.product_id, p.product_name, p.category
            ORDER BY total_revenue DESC
            LIMIT 5
        """)
        product_performance = cursor.fetchall()
        for row in product_performance:
            print(f"  {row[0]} ({row[1]}): {row[2]:,} 笔销售, 收入 ${row[3]:,.2f}, 平均 ${row[4]:,.2f}")
        
        # 示例3: 库存状态分析
        print("\n3. 库存状态分析:")
        cursor.execute("""
            SELECT 
                stock_status,
                COUNT(*) as product_count,
                SUM(stock_value) as total_value,
                AVG(stock_level) as avg_stock_level
            FROM dwd_inventory_detail
            GROUP BY stock_status
            ORDER BY total_value DESC
        """)
        inventory_status = cursor.fetchall()
        for row in inventory_status:
            print(f"  {row[0]}: {row[1]:,} 个产品, 总价值 ${row[2]:,.2f}, 平均库存 {row[3]:,.1f}")
        
        # 示例4: 数据立方体查询
        print("\n4. 销售立方体汇总 (按类别):")
        cursor.execute("""
            SELECT 
                category,
                SUM(transaction_count) as total_transactions,
                SUM(total_revenue) as total_revenue,
                AVG(avg_transaction_value) as avg_transaction_value
            FROM dws_sales_cube
            GROUP BY category
            ORDER BY total_revenue DESC
        """)
        cube_summary = cursor.fetchall()
        for row in cube_summary:
            print(f"  {row[0]}: {row[1]:,} 笔交易, 收入 ${row[2]:,.2f}, 平均 ${row[3]:,.2f}")
        
        print("示例查询完成！")
        
    except Exception as e:
        print(f"示例查询失败: {str(e)}")
        raise
    finally:
        conn.close()

def main():
    """主函数"""
    print("Wide Table Architecture ELT Processing System")
    print("宽表架构ELT处理系统")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 检查必要文件
        if not os.path.exists("data/smart.db"):
            print("数据库文件不存在: data/smart.db")
            sys.exit(1)
        
        if not os.path.exists("create_wide_table_schema.sql"):
            print("SQL脚本文件不存在: create_wide_table_schema.sql")
            sys.exit(1)
        
        if not os.path.exists("etl_implementation.py"):
            print("ELT实现文件不存在: etl_implementation.py")
            sys.exit(1)
        
        # 步骤1: 创建表结构
        create_tables()
        
        # 步骤2: 运行ELT流程
        run_elt_process()
        
        # 步骤3: 验证数据
        verify_data()
        
        # 步骤4: 显示示例查询
        show_sample_queries()
        
        print("\n" + "=" * 60)
        print("宽表架构ELT处理完成！")
        print("=" * 60)
        print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        print(f"处理失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
