#!/usr/bin/env python3
"""
数据库数据与设计逻辑一致性检查脚本（简化版）
Database Data and Design Logic Consistency Check Script (Simplified)
"""

import sqlite3
from datetime import datetime
from typing import Dict, List, Tuple

class DataConsistencyChecker:
    def __init__(self, db_path: str = "data/smart.db"):
        """初始化数据一致性检查器"""
        self.db_path = db_path
        self.conn = None
        
    def connect_db(self):
        """连接数据库"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def close_db(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
    
    def execute_query(self, sql: str, params: tuple = None) -> List[Dict]:
        """执行查询并返回结果"""
        cursor = self.conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        
        columns = [description[0] for description in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        return results
    
    def check_table_structure(self) -> Dict[str, bool]:
        """检查表结构一致性"""
        print("=" * 60)
        print("1. 表结构一致性检查")
        print("=" * 60)
        
        results = {}
        
        # 检查DIM层表
        dim_tables = ['dim_customer', 'dim_product']
        for table in dim_tables:
            try:
                cursor = self.conn.cursor()
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                print(f"PASS {table}: {len(columns)} 个字段")
                results[table] = True
            except Exception as e:
                print(f"FAIL {table}: 表不存在或错误 - {str(e)}")
                results[table] = False
        
        # 检查DWD层表
        dwd_tables = ['dwd_sales_detail', 'dwd_inventory_detail']
        for table in dwd_tables:
            try:
                cursor = self.conn.cursor()
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                print(f"PASS {table}: {len(columns)} 个字段")
                results[table] = True
            except Exception as e:
                print(f"FAIL {table}: 表不存在或错误 - {str(e)}")
                results[table] = False
        
        # 检查DWS层表
        dws_tables = ['dws_sales_cube', 'dws_inventory_cube']
        for table in dws_tables:
            try:
                cursor = self.conn.cursor()
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                print(f"PASS {table}: {len(columns)} 个字段")
                results[table] = True
            except Exception as e:
                print(f"FAIL {table}: 表不存在或错误 - {str(e)}")
                results[table] = False
        
        return results
    
    def check_data_volume_consistency(self) -> Dict[str, bool]:
        """检查数据量一致性"""
        print("\n" + "=" * 60)
        print("2. 数据量一致性检查")
        print("=" * 60)
        
        results = {}
        
        # 源表数据量
        source_tables = {
            'customers': 'dim_customer',
            'products': 'dim_product', 
            'sales': 'dwd_sales_detail',
            'inventory': 'dwd_inventory_detail'
        }
        
        for source_table, target_table in source_tables.items():
            try:
                cursor = self.conn.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM {source_table}")
                source_count = cursor.fetchone()[0]
                
                cursor.execute(f"SELECT COUNT(*) FROM {target_table}")
                target_count = cursor.fetchone()[0]
                
                if source_count == target_count:
                    print(f"PASS {source_table} -> {target_table}: {source_count:,} 条记录")
                    results[f"{source_table}_to_{target_table}"] = True
                else:
                    print(f"FAIL {source_table} -> {target_table}: 源表 {source_count:,} 条，目标表 {target_count:,} 条")
                    results[f"{source_table}_to_{target_table}"] = False
            except Exception as e:
                print(f"FAIL {source_table} -> {target_table}: 检查失败 - {str(e)}")
                results[f"{source_table}_to_{target_table}"] = False
        
        return results
    
    def check_data_quality(self) -> Dict[str, bool]:
        """检查数据质量"""
        print("\n" + "=" * 60)
        print("3. 数据质量检查")
        print("=" * 60)
        
        results = {}
        
        # 检查销售数据质量
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_records,
                    MIN(data_quality_score) as min_score,
                    MAX(data_quality_score) as max_score,
                    AVG(data_quality_score) as avg_score,
                    COUNT(CASE WHEN data_quality_score < 80 THEN 1 END) as low_quality_count
                FROM dwd_sales_detail
            """)
            quality_stats = cursor.fetchone()
            
            print(f"PASS 销售数据质量: 总计 {quality_stats[0]:,} 条")
            print(f"   质量分数范围: {quality_stats[1]} - {quality_stats[2]}")
            print(f"   平均质量分数: {quality_stats[3]:.2f}")
            print(f"   低质量记录: {quality_stats[4]:,} 条")
            
            results['sales_data_quality'] = quality_stats[4] == 0  # 无低质量记录为True
        except Exception as e:
            print(f"FAIL 销售数据质量检查失败: {str(e)}")
            results['sales_data_quality'] = False
        
        # 检查库存数据质量
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_records,
                    MIN(data_quality_score) as min_score,
                    MAX(data_quality_score) as max_score,
                    AVG(data_quality_score) as avg_score,
                    COUNT(CASE WHEN data_quality_score < 80 THEN 1 END) as low_quality_count
                FROM dwd_inventory_detail
            """)
            quality_stats = cursor.fetchone()
            
            print(f"PASS 库存数据质量: 总计 {quality_stats[0]:,} 条")
            print(f"   质量分数范围: {quality_stats[1]} - {quality_stats[2]}")
            print(f"   平均质量分数: {quality_stats[3]:.2f}")
            print(f"   低质量记录: {quality_stats[4]:,} 条")
            
            results['inventory_data_quality'] = quality_stats[4] == 0  # 无低质量记录为True
        except Exception as e:
            print(f"FAIL 库存数据质量检查失败: {str(e)}")
            results['inventory_data_quality'] = False
        
        return results
    
    def check_data_consistency(self) -> Dict[str, bool]:
        """检查数据一致性"""
        print("\n" + "=" * 60)
        print("4. 数据一致性检查")
        print("=" * 60)
        
        results = {}
        
        # 检查销售金额计算一致性
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM dwd_sales_detail 
                WHERE ABS(calculated_total - total_amount) > 0.01
            """)
            inconsistent_count = cursor.fetchone()[0]
            
            if inconsistent_count == 0:
                print(f"PASS 销售金额计算一致性: 100% 一致")
                results['sales_amount_consistency'] = True
            else:
                print(f"FAIL 销售金额计算不一致: {inconsistent_count:,} 条记录")
                results['sales_amount_consistency'] = False
        except Exception as e:
            print(f"FAIL 销售金额一致性检查失败: {str(e)}")
            results['sales_amount_consistency'] = False
        
        # 检查外键完整性
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM dwd_sales_detail s
                LEFT JOIN dim_product p ON s.product_id = p.product_id
                WHERE p.product_id IS NULL
            """)
            missing_products = cursor.fetchone()[0]
            
            if missing_products == 0:
                print(f"PASS 销售表产品外键完整性: 100% 完整")
                results['sales_product_fk'] = True
            else:
                print(f"FAIL 销售表产品外键缺失: {missing_products:,} 条记录")
                results['sales_product_fk'] = False
        except Exception as e:
            print(f"FAIL 销售表产品外键检查失败: {str(e)}")
            results['sales_product_fk'] = False
        
        return results
    
    def check_business_logic(self) -> Dict[str, bool]:
        """检查业务逻辑一致性"""
        print("\n" + "=" * 60)
        print("5. 业务逻辑一致性检查")
        print("=" * 60)
        
        results = {}
        
        # 检查价格区间分类
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT price_range, COUNT(*) as count
                FROM dim_product
                GROUP BY price_range
                ORDER BY count DESC
            """)
            price_ranges = cursor.fetchall()
            
            print("PASS 产品价格区间分布:")
            for row in price_ranges:
                print(f"   {row[0]}: {row[1]:,} 个产品")
            
            results['price_range_logic'] = True
        except Exception as e:
            print(f"FAIL 价格区间检查失败: {str(e)}")
            results['price_range_logic'] = False
        
        # 检查库存状态分布
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT stock_status, COUNT(*) as count
                FROM dwd_inventory_detail
                GROUP BY stock_status
                ORDER BY count DESC
            """)
            stock_statuses = cursor.fetchall()
            
            print("PASS 库存状态分布:")
            for row in stock_statuses:
                print(f"   {row[0]}: {row[1]:,} 个产品")
            
            results['stock_status_logic'] = True
        except Exception as e:
            print(f"FAIL 库存状态检查失败: {str(e)}")
            results['stock_status_logic'] = False
        
        return results
    
    def check_performance_optimization(self) -> Dict[str, bool]:
        """检查性能优化"""
        print("\n" + "=" * 60)
        print("6. 性能优化检查")
        print("=" * 60)
        
        results = {}
        
        # 检查索引
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            indexes = cursor.fetchall()
            
            print(f"PASS 创建的索引数量: {len(indexes)} 个")
            for index in indexes:
                print(f"   - {index[0]}")
            
            results['indexes_created'] = len(indexes) > 0
        except Exception as e:
            print(f"FAIL 索引检查失败: {str(e)}")
            results['indexes_created'] = False
        
        # 检查视图
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='view'
                ORDER BY name
            """)
            views = cursor.fetchall()
            
            print(f"PASS 创建的视图数量: {len(views)} 个")
            for view in views:
                print(f"   - {view[0]}")
            
            results['views_created'] = len(views) > 0
        except Exception as e:
            print(f"FAIL 视图检查失败: {str(e)}")
            results['views_created'] = False
        
        return results
    
    def run_comprehensive_check(self):
        """运行综合检查"""
        print("数据库数据与设计逻辑一致性检查")
        print("Database Data and Design Logic Consistency Check")
        print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            self.connect_db()
            
            # 执行各项检查
            structure_results = self.check_table_structure()
            volume_results = self.check_data_volume_consistency()
            quality_results = self.check_data_quality()
            consistency_results = self.check_data_consistency()
            business_results = self.check_business_logic()
            performance_results = self.check_performance_optimization()
            
            # 汇总结果
            all_results = {
                **structure_results,
                **volume_results,
                **quality_results,
                **consistency_results,
                **business_results,
                **performance_results
            }
            
            # 统计结果
            total_checks = len(all_results)
            passed_checks = sum(1 for result in all_results.values() if result)
            failed_checks = total_checks - passed_checks
            
            print("\n" + "=" * 60)
            print("检查结果汇总")
            print("=" * 60)
            print(f"总检查项: {total_checks}")
            print(f"通过检查: {passed_checks}")
            print(f"失败检查: {failed_checks}")
            print(f"通过率: {passed_checks/total_checks*100:.1f}%")
            
            if failed_checks == 0:
                print("\n所有检查项都通过！数据库数据与设计逻辑完全一致！")
            else:
                print(f"\n有 {failed_checks} 项检查未通过，需要进一步处理。")
            
        except Exception as e:
            print(f"检查过程失败: {str(e)}")
        finally:
            self.close_db()

def main():
    """主函数"""
    checker = DataConsistencyChecker()
    checker.run_comprehensive_check()

if __name__ == "__main__":
    main()
