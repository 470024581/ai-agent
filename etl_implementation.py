#!/usr/bin/env python3
"""
ELT Implementation for Wide Table Architecture
实现宽表架构的ELT处理逻辑
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import uuid
import re
from typing import List, Dict, Any

class ELTProcessor:
    def __init__(self, db_path: str = "data/smart.db"):
        """初始化ELT处理器"""
        self.db_path = db_path
        self.batch_id = self.generate_batch_id()
        self.conn = None
        
    def generate_batch_id(self) -> str:
        """生成批次ID"""
        return f"BATCH_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
    
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
    
    def execute_batch_insert(self, sql: str, data: List[Dict]):
        """批量插入数据"""
        cursor = self.conn.cursor()
        cursor.executemany(sql, [tuple(record.values()) for record in data])
        self.conn.commit()
    
    def standardize_phone(self, phone: str) -> str:
        """标准化电话号码"""
        if not phone:
            return None
        # 移除所有非数字字符
        digits = re.sub(r'\D', '', phone)
        if len(digits) >= 10:
            return digits[-10:]  # 取最后10位
        return phone
    
    def extract_region_from_address(self, address: str) -> str:
        """从地址中提取地区"""
        if not address:
            return None
        
        # 简单的地区提取逻辑
        address_lower = address.lower()
        if any(keyword in address_lower for keyword in ['beijing', '北京']):
            return 'Beijing'
        elif any(keyword in address_lower for keyword in ['shanghai', '上海']):
            return 'Shanghai'
        elif any(keyword in address_lower for keyword in ['guangzhou', '广州']):
            return 'Guangzhou'
        elif any(keyword in address_lower for keyword in ['shenzhen', '深圳']):
            return 'Shenzhen'
        else:
            return 'Other'
    
    def determine_active_status(self, record: Dict) -> bool:
        """确定客户活跃状态"""
        # 简单的活跃状态判断逻辑
        if record.get('customer_type') == 'VIP':
            return True
        return True  # 演示项目中假设所有客户都是活跃的
    
    def get_price_range(self, price: float) -> str:
        """获取价格区间"""
        if price < 50:
            return 'Low'
        elif price < 200:
            return 'Medium'
        elif price < 500:
            return 'High'
        else:
            return 'Premium'
    
    def get_sale_value_range(self, amount: float) -> str:
        """获取销售价值区间"""
        if amount < 100:
            return 'Low'
        elif amount < 500:
            return 'Medium'
        elif amount < 1000:
            return 'High'
        else:
            return 'Premium'
    
    def get_stock_status(self, stock_level: int) -> str:
        """获取库存状态"""
        if stock_level > 10:
            return 'In Stock'
        elif stock_level > 0:
            return 'Low Stock'
        else:
            return 'Out of Stock'
    
    def calculate_reorder_point(self, product_id: str) -> int:
        """计算重订货点"""
        # 简单的重订货点计算逻辑
        return 10  # 演示项目中固定为10
    
    def calculate_turnover_ratio(self, product_id: str) -> float:
        """计算周转率"""
        # 简单的周转率计算逻辑
        return 0.5  # 演示项目中固定为0.5
    
    def calculate_sales_quality_score(self, record: Dict) -> int:
        """计算销售数据质量分数"""
        score = 100
        
        # 完整性检查
        if not record.get('sale_id'):
            score -= 20
        if not record.get('product_id'):
            score -= 20
        if not record.get('total_amount'):
            score -= 15
        
        # 准确性检查
        calculated_total = record.get('quantity_sold', 0) * record.get('price_per_unit', 0)
        if abs(calculated_total - record.get('total_amount', 0)) > 0.01:
            score -= 10
        
        # 有效性检查
        if record.get('quantity_sold', 0) <= 0:
            score -= 10
        if record.get('price_per_unit', 0) <= 0:
            score -= 10
        
        # 时间有效性
        if record.get('sale_date'):
            try:
                sale_date = datetime.fromisoformat(record['sale_date']).date() if isinstance(record['sale_date'], str) else record['sale_date']
                if sale_date > datetime.now().date():
                    score -= 15
            except:
                score -= 15
        
        return max(0, score)
    
    def calculate_inventory_quality_score(self, record: Dict) -> int:
        """计算库存数据质量分数"""
        score = 100
        
        # 完整性检查
        if not record.get('product_id'):
            score -= 25
        if record.get('stock_level') is None:
            score -= 25
        if not record.get('last_updated'):
            score -= 25
        
        # 有效性检查
        if record.get('stock_level', 0) < 0:
            score -= 15
        
        # 及时性检查
        if record.get('last_updated'):
            try:
                last_updated_str = record['last_updated']
                if isinstance(last_updated_str, str):
                    # 清理日期字符串，移除可能的额外字符
                    clean_date_str = last_updated_str.split(' ')[0] + ' ' + last_updated_str.split(' ')[1] if ' ' in last_updated_str else last_updated_str
                    try:
                        last_updated = datetime.strptime(clean_date_str, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        try:
                            last_updated = datetime.fromisoformat(clean_date_str)
                        except ValueError:
                            last_updated = datetime.now()
                else:
                    last_updated = datetime.now()
                
                days_since_update = (datetime.now() - last_updated).days
                if days_since_update > 30:
                    score -= 10
            except:
                score -= 10
        
        return max(0, score)

    # DIM层ELT方法
    def extract_dim_customer(self) -> List[Dict]:
        """全量抽取客户数据"""
        sql = """
        SELECT 
            customer_id,
            customer_name,
            contact_person,
            phone,
            email,
            address,
            customer_type,
            created_at,
            updated_at
        FROM customers
        """
        return self.execute_query(sql)
    
    def transform_dim_customer(self, raw_data: List[Dict]) -> List[Dict]:
        """转换客户维度数据"""
        transformed_data = []
        for record in raw_data:
            updated_at = datetime.fromisoformat(record['updated_at']) if record['updated_at'] else datetime.now()
            created_at = datetime.fromisoformat(record['created_at']) if record['created_at'] else datetime.now()
            
            transformed_record = {
                'customer_id': record['customer_id'],
                'customer_name': record['customer_name'].strip() if record['customer_name'] else '',
                'contact_person': record['contact_person'].strip() if record['contact_person'] else None,
                'email': record['email'].lower().strip() if record['email'] else None,
                'phone': self.standardize_phone(record['phone']) if record['phone'] else None,
                'address': record['address'].strip() if record['address'] else None,
                'customer_type': record['customer_type'].upper().strip() if record['customer_type'] else 'REGULAR',
                'region': self.extract_region_from_address(record['address']) if record['address'] else None,
                'created_at': created_at,
                'updated_at': updated_at,
                'days_since_update': (datetime.now() - updated_at).days,
                'is_active_customer': self.determine_active_status(record),
                'etl_batch_id': self.batch_id,
                'etl_timestamp': datetime.now()
            }
            transformed_data.append(transformed_record)
        return transformed_data
    
    def load_dim_customer(self, transformed_data: List[Dict]):
        """加载客户维度数据"""
        sql = """
        INSERT OR REPLACE INTO dim_customer (
            customer_id, customer_name, contact_person, email, phone,
            address, customer_type, region, created_at, updated_at,
            days_since_update, is_active_customer, etl_batch_id, etl_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.execute_batch_insert(sql, transformed_data)
    
    def extract_dim_product(self) -> List[Dict]:
        """全量抽取产品数据"""
        sql = """
        SELECT 
            product_id,
            product_name,
            category,
            unit_price
        FROM products
        """
        return self.execute_query(sql)
    
    def transform_dim_product(self, raw_data: List[Dict]) -> List[Dict]:
        """转换产品维度数据"""
        transformed_data = []
        for record in raw_data:
            transformed_record = {
                'product_id': record['product_id'],
                'product_name': record['product_name'].strip() if record['product_name'] else '',
                'category': record['category'].upper().strip() if record['category'] else 'UNKNOWN',
                'unit_price': round(float(record['unit_price']), 2),
                'price_range': self.get_price_range(float(record['unit_price'])),
                'etl_batch_id': self.batch_id,
                'etl_timestamp': datetime.now()
            }
            transformed_data.append(transformed_record)
        return transformed_data
    
    def load_dim_product(self, transformed_data: List[Dict]):
        """加载产品维度数据"""
        sql = """
        INSERT OR REPLACE INTO dim_product (
            product_id, product_name, category, unit_price, price_range,
            etl_batch_id, etl_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        self.execute_batch_insert(sql, transformed_data)

    # DWD层ELT方法
    def extract_dwd_sales_detail(self) -> List[Dict]:
        """全量抽取销售数据"""
        sql = """
        SELECT 
            s.sale_id,
            s.product_id,
            s.product_name,
            s.quantity_sold,
            s.price_per_unit,
            s.total_amount,
            s.sale_date
        FROM sales s
        """
        return self.execute_query(sql)
    
    def transform_dwd_sales_detail(self, raw_data: List[Dict]) -> List[Dict]:
        """转换销售明细数据"""
        transformed_data = []
        for record in raw_data:
            # 解析日期，处理不同的日期格式
            sale_date_str = record['sale_date']
            if isinstance(sale_date_str, str):
                try:
                    # 尝试解析 'YYYY-MM-DD HH:MM:SS' 格式
                    sale_date = datetime.strptime(sale_date_str, '%Y-%m-%d %H:%M:%S').date()
                except ValueError:
                    try:
                        # 尝试解析 ISO 格式
                        sale_date = datetime.fromisoformat(sale_date_str).date()
                    except ValueError:
                        # 如果都失败，使用当前日期
                        sale_date = datetime.now().date()
            else:
                sale_date = datetime.now().date()
            
            transformed_record = {
                'sale_id': record['sale_id'],
                'product_id': record['product_id'],
                'customer_id': None,  # 销售表中没有客户ID
                'quantity_sold': record['quantity_sold'],
                'price_per_unit': round(float(record['price_per_unit']), 2),
                'total_amount': round(float(record['total_amount']), 2),
                'calculated_total': round(record['quantity_sold'] * float(record['price_per_unit']), 2),
                'sale_date': sale_date,
                'sale_value_range': self.get_sale_value_range(float(record['total_amount'])),
                'data_quality_score': self.calculate_sales_quality_score(record),
                'etl_batch_id': self.batch_id,
                'etl_timestamp': datetime.now()
            }
            transformed_data.append(transformed_record)
        return transformed_data
    
    def load_dwd_sales_detail(self, transformed_data: List[Dict]):
        """加载销售明细数据"""
        sql = """
        INSERT OR REPLACE INTO dwd_sales_detail (
            sale_id, product_id, customer_id, quantity_sold, price_per_unit,
            total_amount, calculated_total, sale_date, sale_value_range,
            data_quality_score, etl_batch_id, etl_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.execute_batch_insert(sql, transformed_data)
    
    def extract_dwd_inventory_detail(self) -> List[Dict]:
        """全量抽取库存数据"""
        sql = """
        SELECT 
            i.product_id,
            i.stock_level,
            i.last_updated,
            p.unit_price
        FROM inventory i
        LEFT JOIN products p ON i.product_id = p.product_id
        """
        return self.execute_query(sql)
    
    def transform_dwd_inventory_detail(self, raw_data: List[Dict]) -> List[Dict]:
        """转换库存明细数据"""
        transformed_data = []
        for record in raw_data:
            # 解析日期，处理不同的日期格式
            last_updated_str = record['last_updated']
            if isinstance(last_updated_str, str):
                # 清理日期字符串，移除可能的额外字符
                clean_date_str = last_updated_str.split(' ')[0] + ' ' + last_updated_str.split(' ')[1] if ' ' in last_updated_str else last_updated_str
                try:
                    # 尝试解析 'YYYY-MM-DD HH:MM:SS' 格式
                    last_updated = datetime.strptime(clean_date_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    try:
                        # 尝试解析 ISO 格式
                        last_updated = datetime.fromisoformat(clean_date_str)
                    except ValueError:
                        # 如果都失败，使用当前时间
                        last_updated = datetime.now()
            else:
                last_updated = datetime.now()
            
            days_since_update = (datetime.now() - last_updated).days
            stock_value = record['stock_level'] * float(record['unit_price']) if record['unit_price'] else 0
            reorder_point = self.calculate_reorder_point(record['product_id'])
            turnover_ratio = self.calculate_turnover_ratio(record['product_id'])
            
            transformed_record = {
                'product_id': record['product_id'],
                'stock_level': record['stock_level'],
                'last_updated': last_updated,
                'stock_status': self.get_stock_status(record['stock_level']),
                'days_since_update': days_since_update,
                'is_stale_data': days_since_update > 7,
                'stock_value': round(stock_value, 2),
                'reorder_point': reorder_point,
                'is_low_stock': record['stock_level'] < reorder_point,
                'turnover_ratio': round(turnover_ratio, 4),
                'data_quality_score': self.calculate_inventory_quality_score(record),
                'etl_batch_id': self.batch_id,
                'etl_timestamp': datetime.now()
            }
            transformed_data.append(transformed_record)
        return transformed_data
    
    def load_dwd_inventory_detail(self, transformed_data: List[Dict]):
        """加载库存明细数据"""
        sql = """
        INSERT OR REPLACE INTO dwd_inventory_detail (
            product_id, stock_level, last_updated, stock_status,
            days_since_update, is_stale_data, stock_value, reorder_point,
            is_low_stock, turnover_ratio, data_quality_score, etl_batch_id, etl_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.execute_batch_insert(sql, transformed_data)

    # DWS层ELT方法
    def extract_dws_sales_cube(self) -> List[Dict]:
        """从DWD层抽取销售数据用于立方体聚合"""
        sql = """
        SELECT 
            s.sale_date,
            s.product_id,
            p.category,
            p.price_range,
            s.sale_value_range,
            COUNT(*) as transaction_count,
            SUM(s.total_amount) as total_revenue,
            SUM(s.quantity_sold) as total_quantity,
            AVG(s.total_amount) as avg_transaction_value
        FROM dwd_sales_detail s
        LEFT JOIN dim_product p ON s.product_id = p.product_id
        GROUP BY s.sale_date, s.product_id, p.category, p.price_range, s.sale_value_range
        """
        return self.execute_query(sql)
    
    def transform_dws_sales_cube(self, raw_data: List[Dict]) -> List[Dict]:
        """转换销售立方体数据"""
        transformed_data = []
        for record in raw_data:
            transformed_record = {
                'sale_date': record['sale_date'],
                'product_id': record['product_id'],
                'category': record['category'],
                'price_range': record['price_range'],
                'sale_value_range': record['sale_value_range'],
                'transaction_count': record['transaction_count'],
                'total_revenue': round(float(record['total_revenue']), 2),
                'total_quantity_sold': record['total_quantity'],
                'avg_transaction_value': round(float(record['avg_transaction_value']), 2),
                'unique_products': 1,  # 在立方体中每个记录代表一个产品
                'etl_batch_id': self.batch_id,
                'etl_timestamp': datetime.now()
            }
            transformed_data.append(transformed_record)
        return transformed_data
    
    def load_dws_sales_cube(self, transformed_data: List[Dict]):
        """加载销售立方体数据"""
        sql = """
        INSERT OR REPLACE INTO dws_sales_cube (
            sale_date, product_id, category, price_range, sale_value_range,
            transaction_count, total_quantity_sold, total_revenue, avg_transaction_value,
            unique_products, etl_batch_id, etl_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.execute_batch_insert(sql, transformed_data)
    
    def extract_dws_inventory_cube(self) -> List[Dict]:
        """从DWD层抽取库存数据用于立方体聚合"""
        sql = """
        SELECT 
            DATE(i.last_updated) as last_updated_date,
            i.product_id,
            p.category,
            p.price_range,
            i.stock_status,
            i.is_low_stock,
            i.is_stale_data,
            COUNT(*) as product_count,
            SUM(i.stock_level) as total_stock_level,
            SUM(i.stock_value) as total_stock_value,
            AVG(i.stock_level) as avg_stock_level,
            AVG(i.stock_value) as avg_stock_value,
            AVG(i.turnover_ratio) as avg_turnover_ratio
        FROM dwd_inventory_detail i
        LEFT JOIN dim_product p ON i.product_id = p.product_id
        GROUP BY DATE(i.last_updated), i.product_id, p.category, p.price_range,
                 i.stock_status, i.is_low_stock, i.is_stale_data
        """
        return self.execute_query(sql)
    
    def transform_dws_inventory_cube(self, raw_data: List[Dict]) -> List[Dict]:
        """转换库存立方体数据"""
        transformed_data = []
        for record in raw_data:
            transformed_record = {
                'last_updated_date': record['last_updated_date'],
                'product_id': record['product_id'],
                'category': record['category'],
                'price_range': record['price_range'],
                'stock_status': record['stock_status'],
                'is_low_stock': record['is_low_stock'],
                'is_stale_data': record['is_stale_data'],
                'product_count': record['product_count'],
                'total_stock_level': record['total_stock_level'],
                'total_stock_value': round(float(record['total_stock_value']), 2),
                'avg_stock_level': round(float(record['avg_stock_level']), 2),
                'avg_stock_value': round(float(record['avg_stock_value']), 2),
                'avg_turnover_ratio': round(float(record['avg_turnover_ratio']), 4),
                'etl_batch_id': self.batch_id,
                'etl_timestamp': datetime.now()
            }
            transformed_data.append(transformed_record)
        return transformed_data
    
    def load_dws_inventory_cube(self, transformed_data: List[Dict]):
        """加载库存立方体数据"""
        sql = """
        INSERT OR REPLACE INTO dws_inventory_cube (
            last_updated_date, product_id, category, price_range, stock_status,
            is_low_stock, is_stale_data, product_count, total_stock_level,
            total_stock_value, avg_stock_level, avg_stock_value, avg_turnover_ratio,
            etl_batch_id, etl_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.execute_batch_insert(sql, transformed_data)

    def run_full_elt_process(self):
        """运行完整的ELT流程"""
        print(f"开始ELT流程，批次ID: {self.batch_id}")
        
        try:
            self.connect_db()
            
            # 1. DIM层处理
            print("开始DIM层处理...")
            
            # 客户维度
            print("  处理客户维度...")
            customer_raw = self.extract_dim_customer()
            print(f"    抽取了 {len(customer_raw)} 条客户记录")
            customer_transformed = self.transform_dim_customer(customer_raw)
            self.load_dim_customer(customer_transformed)
            print(f"    加载了 {len(customer_transformed)} 条客户维度记录")
            
            # 产品维度
            print("  处理产品维度...")
            product_raw = self.extract_dim_product()
            print(f"    抽取了 {len(product_raw)} 条产品记录")
            product_transformed = self.transform_dim_product(product_raw)
            self.load_dim_product(product_transformed)
            print(f"    加载了 {len(product_transformed)} 条产品维度记录")
            
            # 2. DWD层处理
            print("开始DWD层处理...")
            
            # 销售明细
            print("  处理销售明细...")
            sales_raw = self.extract_dwd_sales_detail()
            print(f"    抽取了 {len(sales_raw)} 条销售记录")
            sales_transformed = self.transform_dwd_sales_detail(sales_raw)
            self.load_dwd_sales_detail(sales_transformed)
            print(f"    加载了 {len(sales_transformed)} 条销售明细记录")
            
            # 库存明细
            print("  处理库存明细...")
            inventory_raw = self.extract_dwd_inventory_detail()
            print(f"    抽取了 {len(inventory_raw)} 条库存记录")
            inventory_transformed = self.transform_dwd_inventory_detail(inventory_raw)
            self.load_dwd_inventory_detail(inventory_transformed)
            print(f"    加载了 {len(inventory_transformed)} 条库存明细记录")
            
            # 3. DWS层处理
            print("开始DWS层处理...")
            
            # 销售立方体
            print("  处理销售立方体...")
            sales_cube_raw = self.extract_dws_sales_cube()
            print(f"    抽取了 {len(sales_cube_raw)} 条销售立方体记录")
            sales_cube_transformed = self.transform_dws_sales_cube(sales_cube_raw)
            self.load_dws_sales_cube(sales_cube_transformed)
            print(f"    加载了 {len(sales_cube_transformed)} 条销售立方体记录")
            
            # 库存立方体
            print("  处理库存立方体...")
            inventory_cube_raw = self.extract_dws_inventory_cube()
            print(f"    抽取了 {len(inventory_cube_raw)} 条库存立方体记录")
            inventory_cube_transformed = self.transform_dws_inventory_cube(inventory_cube_raw)
            self.load_dws_inventory_cube(inventory_cube_transformed)
            print(f"    加载了 {len(inventory_cube_transformed)} 条库存立方体记录")
            
            print("ELT流程完成！")
            
        except Exception as e:
            print(f"ELT流程失败: {str(e)}")
            raise
        finally:
            self.close_db()

def main():
    """主函数"""
    processor = ELTProcessor()
    processor.run_full_elt_process()

if __name__ == "__main__":
    main()
