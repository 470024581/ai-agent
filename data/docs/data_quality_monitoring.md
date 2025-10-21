# Data Quality Monitoring and Management Framework - Optimized Wide Table Architecture

## Overview
This document describes the comprehensive data quality monitoring framework for the optimized wide table data warehouse architecture, including quality metrics, monitoring processes, alerting mechanisms, and remediation procedures.

## Data Quality Framework

### 1. Data Quality Dimensions
- **Completeness**: Data is complete and not missing
- **Accuracy**: Data is correct and accurate
- **Consistency**: Data is consistent across systems
- **Timeliness**: Data is current and up-to-date
- **Validity**: Data conforms to business rules
- **Uniqueness**: Data is unique where required
- **Integrity**: Data maintains referential integrity

### 2. Quality Metrics Framework
```python
class DataQualityMetrics:
    def __init__(self):
        self.completeness_score = 0.0
        self.accuracy_score = 0.0
        self.consistency_score = 0.0
        self.timeliness_score = 0.0
        self.validity_score = 0.0
        self.uniqueness_score = 0.0
        self.integrity_score = 0.0
        self.overall_score = 0.0
        
    def calculate_overall_score(self):
        """Calculate overall data quality score"""
        weights = {
            'completeness': 0.25,
            'accuracy': 0.20,
            'consistency': 0.15,
            'timeliness': 0.15,
            'validity': 0.15,
            'uniqueness': 0.05,
            'integrity': 0.05
        }
        
        self.overall_score = sum(
            getattr(self, f"{dimension}_score") * weight
            for dimension, weight in weights.items()
        )
        
        return self.overall_score
```

---

## DIM Layer Data Quality Monitoring

### 1. Customer Dimension Quality Rules

#### Completeness Checks
```sql
-- Check for missing required fields
SELECT 
    'dim_customer' as table_name,
    'completeness' as check_type,
    COUNT(*) as total_records,
    COUNT(*) - COUNT(customer_id) as missing_customer_id,
    COUNT(*) - COUNT(customer_name) as missing_customer_name,
    COUNT(*) - COUNT(customer_type) as missing_customer_type,
    COUNT(*) - COUNT(created_at) as missing_created_at,
    COUNT(*) - COUNT(updated_at) as missing_updated_at,
    ROUND((COUNT(*) - COUNT(customer_id) - COUNT(customer_name) - COUNT(customer_type) - COUNT(created_at) - COUNT(updated_at)) * 100.0 / COUNT(*), 2) as completeness_score
FROM dim_customer;
```

#### Accuracy Checks
```sql
-- Check email format accuracy
SELECT 
    'dim_customer' as table_name,
    'email_format' as check_type,
    COUNT(*) as total_records,
    COUNT(CASE WHEN email REGEXP '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$' THEN 1 END) as valid_emails,
    COUNT(*) - COUNT(CASE WHEN email REGEXP '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$' THEN 1 END) as invalid_emails,
    ROUND(COUNT(CASE WHEN email REGEXP '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$' THEN 1 END) * 100.0 / COUNT(*), 2) as accuracy_score
FROM dim_customer
WHERE email IS NOT NULL;
```

---

### 2. Product Dimension Quality Rules

#### Completeness Checks
```sql
-- Check for missing required fields
SELECT 
    'dim_product' as table_name,
    'completeness' as check_type,
    COUNT(*) as total_records,
    COUNT(*) - COUNT(product_id) as missing_product_id,
    COUNT(*) - COUNT(product_name) as missing_product_name,
    COUNT(*) - COUNT(category) as missing_category,
    COUNT(*) - COUNT(unit_price) as missing_unit_price,
    ROUND((COUNT(*) - COUNT(product_id) - COUNT(product_name) - COUNT(category) - COUNT(unit_price)) * 100.0 / COUNT(*), 2) as completeness_score
FROM dim_product;
```

#### Validity Checks
```sql
-- Check price validity
SELECT 
    'dim_product' as table_name,
    'price_validity' as check_type,
    COUNT(*) as total_records,
    COUNT(CASE WHEN unit_price > 0 THEN 1 END) as valid_prices,
    COUNT(*) - COUNT(CASE WHEN unit_price > 0 THEN 1 END) as invalid_prices,
    ROUND(COUNT(CASE WHEN unit_price > 0 THEN 1 END) * 100.0 / COUNT(*), 2) as validity_score
FROM dim_product;
```

---

## DWD Layer Data Quality Monitoring - Wide Table Architecture

### 1. Sales Detail Table Quality Monitoring

#### Completeness Checks
```sql
-- Check sales detail completeness
SELECT 
    'dwd_sales_detail' as table_name,
    'completeness' as check_type,
    COUNT(*) as total_records,
    COUNT(*) - COUNT(sale_id) as missing_sale_id,
    COUNT(*) - COUNT(product_id) as missing_product_id,
    COUNT(*) - COUNT(quantity_sold) as missing_quantity_sold,
    COUNT(*) - COUNT(total_amount) as missing_total_amount,
    COUNT(*) - COUNT(sale_date) as missing_sale_date,
    COUNT(*) - COUNT(calculated_total) as missing_calculated_total,
    ROUND((COUNT(*) - COUNT(sale_id) - COUNT(product_id) - COUNT(quantity_sold) - COUNT(total_amount) - COUNT(sale_date) - COUNT(calculated_total)) * 100.0 / COUNT(*), 2) as completeness_score
FROM dwd_sales_detail;
```

#### Accuracy Checks
```sql
-- Check calculated total accuracy
SELECT 
    'dwd_sales_detail' as table_name,
    'calculated_total_accuracy' as check_type,
    COUNT(*) as total_records,
    COUNT(CASE WHEN ABS(calculated_total - (quantity_sold * price_per_unit)) < 0.01 THEN 1 END) as accurate_calculations,
    COUNT(*) - COUNT(CASE WHEN ABS(calculated_total - (quantity_sold * price_per_unit)) < 0.01 THEN 1 END) as inaccurate_calculations,
    ROUND(COUNT(CASE WHEN ABS(calculated_total - (quantity_sold * price_per_unit)) < 0.01 THEN 1 END) * 100.0 / COUNT(*), 2) as accuracy_score
FROM dwd_sales_detail;

-- Check sale value range accuracy
SELECT 
    'dwd_sales_detail' as table_name,
    'sale_value_range_accuracy' as check_type,
    COUNT(*) as total_records,
    COUNT(CASE 
        WHEN (total_amount < 100 AND sale_value_range = 'Low') OR
             (total_amount >= 100 AND total_amount < 500 AND sale_value_range = 'Medium') OR
             (total_amount >= 500 AND total_amount < 1000 AND sale_value_range = 'High') OR
             (total_amount >= 1000 AND sale_value_range = 'Premium')
        THEN 1 
    END) as accurate_ranges,
    COUNT(*) - COUNT(CASE 
        WHEN (total_amount < 100 AND sale_value_range = 'Low') OR
             (total_amount >= 100 AND total_amount < 500 AND sale_value_range = 'Medium') OR
             (total_amount >= 500 AND total_amount < 1000 AND sale_value_range = 'High') OR
             (total_amount >= 1000 AND sale_value_range = 'Premium')
        THEN 1 
    END) as inaccurate_ranges,
    ROUND(COUNT(CASE 
        WHEN (total_amount < 100 AND sale_value_range = 'Low') OR
             (total_amount >= 100 AND total_amount < 500 AND sale_value_range = 'Medium') OR
             (total_amount >= 500 AND total_amount < 1000 AND sale_value_range = 'High') OR
             (total_amount >= 1000 AND sale_value_range = 'Premium')
        THEN 1 
    END) * 100.0 / COUNT(*), 2) as accuracy_score
FROM dwd_sales_detail;
```

#### Consistency Checks
```sql
-- Check foreign key consistency
SELECT 
    'dwd_sales_detail' as table_name,
    'foreign_key_consistency' as check_type,
    COUNT(*) as total_records,
    COUNT(CASE WHEN customer_id IS NOT NULL THEN 1 END) as records_with_customer_id,
    COUNT(CASE WHEN customer_id IS NOT NULL AND customer_id IN (SELECT customer_id FROM dim_customer) THEN 1 END) as valid_customer_references,
    COUNT(CASE WHEN product_id IN (SELECT product_id FROM dim_product) THEN 1 END) as valid_product_references,
    ROUND(COUNT(CASE WHEN customer_id IS NOT NULL AND customer_id IN (SELECT customer_id FROM dim_customer) THEN 1 END) * 100.0 / COUNT(CASE WHEN customer_id IS NOT NULL THEN 1 END), 2) as customer_consistency_score,
    ROUND(COUNT(CASE WHEN product_id IN (SELECT product_id FROM dim_product) THEN 1 END) * 100.0 / COUNT(*), 2) as product_consistency_score
FROM dwd_sales_detail;
```

---

### 2. Inventory Detail Table Quality Monitoring

#### Completeness Checks
```sql
-- Check inventory detail completeness
SELECT 
    'dwd_inventory_detail' as table_name,
    'completeness' as check_type,
    COUNT(*) as total_records,
    COUNT(*) - COUNT(product_id) as missing_product_id,
    COUNT(*) - COUNT(stock_level) as missing_stock_level,
    COUNT(*) - COUNT(last_updated) as missing_last_updated,
    COUNT(*) - COUNT(stock_status) as missing_stock_status,
    COUNT(*) - COUNT(stock_value) as missing_stock_value,
    ROUND((COUNT(*) - COUNT(product_id) - COUNT(stock_level) - COUNT(last_updated) - COUNT(stock_status) - COUNT(stock_value)) * 100.0 / COUNT(*), 2) as completeness_score
FROM dwd_inventory_detail;
```

#### Accuracy Checks
```sql
-- Check stock status accuracy
SELECT 
    'dwd_inventory_detail' as table_name,
    'stock_status_accuracy' as check_type,
    COUNT(*) as total_records,
    COUNT(CASE 
        WHEN (stock_level > 10 AND stock_status = 'In Stock') OR
             (stock_level > 0 AND stock_level <= 10 AND stock_status = 'Low Stock') OR
             (stock_level = 0 AND stock_status = 'Out of Stock')
        THEN 1 
    END) as accurate_status,
    COUNT(*) - COUNT(CASE 
        WHEN (stock_level > 10 AND stock_status = 'In Stock') OR
             (stock_level > 0 AND stock_level <= 10 AND stock_status = 'Low Stock') OR
             (stock_level = 0 AND stock_status = 'Out of Stock')
        THEN 1 
    END) as inaccurate_status,
    ROUND(COUNT(CASE 
        WHEN (stock_level > 10 AND stock_status = 'In Stock') OR
             (stock_level > 0 AND stock_level <= 10 AND stock_status = 'Low Stock') OR
             (stock_level = 0 AND stock_status = 'Out of Stock')
        THEN 1 
    END) * 100.0 / COUNT(*), 2) as accuracy_score
FROM dwd_inventory_detail;

-- Check stock value calculation accuracy
SELECT 
    'dwd_inventory_detail' as table_name,
    'stock_value_accuracy' as check_type,
    COUNT(*) as total_records,
    COUNT(CASE WHEN ABS(stock_value - (stock_level * (SELECT unit_price FROM dim_product WHERE product_id = dwd_inventory_detail.product_id))) < 0.01 THEN 1 END) as accurate_values,
    COUNT(*) - COUNT(CASE WHEN ABS(stock_value - (stock_level * (SELECT unit_price FROM dim_product WHERE product_id = dwd_inventory_detail.product_id))) < 0.01 THEN 1 END) as inaccurate_values,
    ROUND(COUNT(CASE WHEN ABS(stock_value - (stock_level * (SELECT unit_price FROM dim_product WHERE product_id = dwd_inventory_detail.product_id))) < 0.01 THEN 1 END) * 100.0 / COUNT(*), 2) as accuracy_score
FROM dwd_inventory_detail;
```

---

## DWS Layer Data Quality Monitoring - Data Cube Architecture

### 1. Sales Cube Quality Monitoring

#### Accuracy Checks
```sql
-- Verify sales cube accuracy
SELECT 
    'dws_sales_cube' as table_name,
    'cube_accuracy' as check_type,
    COUNT(*) as total_records,
    COUNT(CASE WHEN transaction_count = (SELECT COUNT(*) FROM dwd_sales_detail WHERE sale_date = dws_sales_cube.sale_date AND customer_id = dws_sales_cube.customer_id AND product_id = dws_sales_cube.product_id) THEN 1 END) as accurate_transaction_counts,
    COUNT(CASE WHEN ABS(total_revenue - (SELECT SUM(total_amount) FROM dwd_sales_detail WHERE sale_date = dws_sales_cube.sale_date AND customer_id = dws_sales_cube.customer_id AND product_id = dws_sales_cube.product_id)) < 0.01 THEN 1 END) as accurate_revenue,
    ROUND(COUNT(CASE WHEN transaction_count = (SELECT COUNT(*) FROM dwd_sales_detail WHERE sale_date = dws_sales_cube.sale_date AND customer_id = dws_sales_cube.customer_id AND product_id = dws_sales_cube.product_id) THEN 1 END) * 100.0 / COUNT(*), 2) as transaction_accuracy_score,
    ROUND(COUNT(CASE WHEN ABS(total_revenue - (SELECT SUM(total_amount) FROM dwd_sales_detail WHERE sale_date = dws_sales_cube.sale_date AND customer_id = dws_sales_cube.customer_id AND product_id = dws_sales_cube.product_id)) < 0.01 THEN 1 END) * 100.0 / COUNT(*), 2) as revenue_accuracy_score
FROM dws_sales_cube;
```

---

### 2. Inventory Cube Quality Monitoring

#### Accuracy Checks
```sql
-- Verify inventory cube accuracy
SELECT 
    'dws_inventory_cube' as table_name,
    'cube_accuracy' as check_type,
    COUNT(*) as total_records,
    COUNT(CASE WHEN product_count = (SELECT COUNT(*) FROM dwd_inventory_detail WHERE last_updated_date = dws_inventory_cube.last_updated_date AND product_id = dws_inventory_cube.product_id) THEN 1 END) as accurate_product_counts,
    COUNT(CASE WHEN ABS(total_stock_value - (SELECT SUM(stock_value) FROM dwd_inventory_detail WHERE last_updated_date = dws_inventory_cube.last_updated_date AND product_id = dws_inventory_cube.product_id)) < 0.01 THEN 1 END) as accurate_stock_values,
    ROUND(COUNT(CASE WHEN product_count = (SELECT COUNT(*) FROM dwd_inventory_detail WHERE last_updated_date = dws_inventory_cube.last_updated_date AND product_id = dws_inventory_cube.product_id) THEN 1 END) * 100.0 / COUNT(*), 2) as product_count_accuracy_score,
    ROUND(COUNT(CASE WHEN ABS(total_stock_value - (SELECT SUM(stock_value) FROM dwd_inventory_detail WHERE last_updated_date = dws_inventory_cube.last_updated_date AND product_id = dws_inventory_cube.product_id)) < 0.01 THEN 1 END) * 100.0 / COUNT(*), 2) as stock_value_accuracy_score
FROM dws_inventory_cube;
```

---

## Data Quality Monitoring Automation

### 1. Automated Quality Checks

#### Python Quality Monitoring Script
```python
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

class DataQualityMonitor:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        
    def run_completeness_check(self, table_name, required_fields):
        """Run completeness check for specified table and fields"""
        query = f"""
    SELECT 
            '{table_name}' as table_name,
            'completeness' as check_type,
            COUNT(*) as total_records,
            {', '.join([f"COUNT(*) - COUNT({field}) as missing_{field}" for field in required_fields])},
            ROUND((COUNT(*) - {(' + '.join([f'COUNT({field})' for field in required_fields]))}) * 100.0 / COUNT(*), 2) as completeness_score
        FROM {table_name}
        """
        
        result = pd.read_sql_query(query, self.conn)
        return result
    
    def run_accuracy_check(self, table_name, accuracy_rules):
        """Run accuracy check for specified table and rules"""
        results = []
        for rule_name, rule_query in accuracy_rules.items():
            query = f"""
            SELECT 
                '{table_name}' as table_name,
                '{rule_name}' as check_type,
                {rule_query}
            """
            result = pd.read_sql_query(query, self.conn)
            results.append(result)
        
        return pd.concat(results, ignore_index=True)
    
    def run_consistency_check(self, table_name, consistency_rules):
        """Run consistency check for specified table and rules"""
        results = []
        for rule_name, rule_query in consistency_rules.items():
            query = f"""
            SELECT 
                '{table_name}' as table_name,
                '{rule_name}' as check_type,
                {rule_query}
            """
            result = pd.read_sql_query(query, self.conn)
            results.append(result)
        
        return pd.concat(results, ignore_index=True)
    
    def calculate_overall_quality_score(self, table_name):
        """Calculate overall quality score for a table"""
        # Run all quality checks
        completeness_result = self.run_completeness_check(table_name, self.get_required_fields(table_name))
        accuracy_result = self.run_accuracy_check(table_name, self.get_accuracy_rules(table_name))
        consistency_result = self.run_consistency_check(table_name, self.get_consistency_rules(table_name))
        
        # Calculate weighted score
        weights = {'completeness': 0.4, 'accuracy': 0.4, 'consistency': 0.2}
        overall_score = 0
        
        if not completeness_result.empty:
            overall_score += completeness_result['completeness_score'].iloc[0] * weights['completeness']
        
        if not accuracy_result.empty:
            avg_accuracy = accuracy_result['accuracy_score'].mean()
            overall_score += avg_accuracy * weights['accuracy']
        
        if not consistency_result.empty:
            avg_consistency = consistency_result['consistency_score'].mean()
            overall_score += avg_consistency * weights['consistency']
        
        return overall_score
    
    def get_required_fields(self, table_name):
        """Get required fields for completeness check"""
        field_mapping = {
            'dwd_sales_detail': ['sale_id', 'product_id', 'quantity_sold', 'total_amount', 'sale_date'],
            'dwd_inventory_detail': ['product_id', 'stock_level', 'last_updated', 'stock_status'],
            'dim_customer': ['customer_id', 'customer_name', 'customer_type'],
            'dim_product': ['product_id', 'product_name', 'category', 'unit_price']
        }
        return field_mapping.get(table_name, [])
    
    def get_accuracy_rules(self, table_name):
        """Get accuracy rules for specified table"""
        rules_mapping = {
            'dwd_sales_detail': {
                'calculated_total_accuracy': """
                    COUNT(*) as total_records,
                    COUNT(CASE WHEN ABS(calculated_total - (quantity_sold * price_per_unit)) < 0.01 THEN 1 END) as accurate_calculations,
                    ROUND(COUNT(CASE WHEN ABS(calculated_total - (quantity_sold * price_per_unit)) < 0.01 THEN 1 END) * 100.0 / COUNT(*), 2) as accuracy_score
                """
            },
            'dwd_inventory_detail': {
                'stock_status_accuracy': """
                    COUNT(*) as total_records,
                    COUNT(CASE 
                        WHEN (stock_level > 10 AND stock_status = 'In Stock') OR
                             (stock_level > 0 AND stock_level <= 10 AND stock_status = 'Low Stock') OR
                             (stock_level = 0 AND stock_status = 'Out of Stock')
                        THEN 1 
                    END) as accurate_status,
                    ROUND(COUNT(CASE 
                        WHEN (stock_level > 10 AND stock_status = 'In Stock') OR
                             (stock_level > 0 AND stock_level <= 10 AND stock_status = 'Low Stock') OR
                             (stock_level = 0 AND stock_status = 'Out of Stock')
                        THEN 1 
                    END) * 100.0 / COUNT(*), 2) as accuracy_score
                """
            }
        }
        return rules_mapping.get(table_name, {})
    
    def get_consistency_rules(self, table_name):
        """Get consistency rules for specified table"""
        rules_mapping = {
            'dwd_sales_detail': {
                'foreign_key_consistency': """
                    COUNT(*) as total_records,
                    COUNT(CASE WHEN customer_id IS NOT NULL THEN 1 END) as records_with_customer_id,
                    COUNT(CASE WHEN customer_id IS NOT NULL AND customer_id IN (SELECT customer_id FROM dim_customer) THEN 1 END) as valid_customer_references,
                    ROUND(COUNT(CASE WHEN customer_id IS NOT NULL AND customer_id IN (SELECT customer_id FROM dim_customer) THEN 1 END) * 100.0 / COUNT(CASE WHEN customer_id IS NOT NULL THEN 1 END), 2) as consistency_score
                """
            }
        }
        return rules_mapping.get(table_name, {})
    
    def generate_quality_report(self):
        """Generate comprehensive quality report"""
        tables = ['dwd_sales_detail', 'dwd_inventory_detail', 'dim_customer', 'dim_product']
        report = {}
    
        for table in tables:
            report[table] = {
                'overall_score': self.calculate_overall_quality_score(table),
                'timestamp': datetime.now().isoformat(),
                'status': 'PASS' if self.calculate_overall_quality_score(table) >= 90 else 'FAIL'
            }
        
        return report
    
    def close(self):
        """Close database connection"""
        self.conn.close()

# Usage example
if __name__ == "__main__":
    monitor = DataQualityMonitor('data/smart.db')
    report = monitor.generate_quality_report()
    print("Data Quality Report:")
    for table, metrics in report.items():
        print(f"{table}: {metrics['overall_score']:.2f}% - {metrics['status']}")
    monitor.close()
```

### 2. Alerting and Notification

#### Quality Alert System
```python
class QualityAlertSystem:
    def __init__(self, quality_threshold=90):
        self.quality_threshold = quality_threshold
        self.alert_channels = []
    
    def add_alert_channel(self, channel):
        """Add alert channel (email, slack, etc.)"""
        self.alert_channels.append(channel)
    
    def check_quality_threshold(self, quality_report):
        """Check if quality scores meet threshold"""
        alerts = []
        
        for table, metrics in quality_report.items():
            if metrics['overall_score'] < self.quality_threshold:
                alert = {
                    'table': table,
                    'score': metrics['overall_score'],
                    'threshold': self.quality_threshold,
                    'timestamp': metrics['timestamp'],
                    'severity': 'HIGH' if metrics['overall_score'] < 80 else 'MEDIUM'
                }
                alerts.append(alert)
    
    return alerts

    def send_alerts(self, alerts):
        """Send alerts through configured channels"""
    for alert in alerts:
            message = f"Data Quality Alert: {alert['table']} scored {alert['score']:.2f}% (threshold: {alert['threshold']}%)"
            
            for channel in self.alert_channels:
                channel.send_alert(alert, message)
```

---

## Quality Remediation Procedures

### 1. Data Correction Workflows

#### Automatic Correction Rules
```python
class DataCorrectionEngine:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
    
    def correct_calculated_totals(self):
        """Correct calculated_total field in sales detail"""
        query = """
        UPDATE dwd_sales_detail 
        SET calculated_total = quantity_sold * price_per_unit
        WHERE ABS(calculated_total - (quantity_sold * price_per_unit)) > 0.01
        """
        
        cursor = self.conn.cursor()
        cursor.execute(query)
        corrected_count = cursor.rowcount
        self.conn.commit()
        
        return corrected_count
    
    def correct_stock_status(self):
        """Correct stock_status field in inventory detail"""
        query = """
        UPDATE dwd_inventory_detail 
        SET stock_status = CASE 
            WHEN stock_level > 10 THEN 'In Stock'
            WHEN stock_level > 0 THEN 'Low Stock'
            ELSE 'Out of Stock'
        END
        WHERE stock_status != CASE 
            WHEN stock_level > 10 THEN 'In Stock'
            WHEN stock_level > 0 THEN 'Low Stock'
            ELSE 'Out of Stock'
        END
        """
        
        cursor = self.conn.cursor()
        cursor.execute(query)
        corrected_count = cursor.rowcount
        self.conn.commit()
        
        return corrected_count
    
    def correct_price_ranges(self):
        """Correct price_range field in product dimension"""
        query = """
        UPDATE dim_product 
        SET price_range = CASE 
            WHEN unit_price < 50 THEN 'Low'
            WHEN unit_price < 200 THEN 'Medium'
            WHEN unit_price < 1000 THEN 'High'
            ELSE 'Premium'
        END
        WHERE price_range != CASE 
            WHEN unit_price < 50 THEN 'Low'
            WHEN unit_price < 200 THEN 'Medium'
            WHEN unit_price < 1000 THEN 'High'
            ELSE 'Premium'
        END
        """
        
        cursor = self.conn.cursor()
        cursor.execute(query)
        corrected_count = cursor.rowcount
        self.conn.commit()
        
        return corrected_count
    
    def run_all_corrections(self):
        """Run all automatic corrections"""
        corrections = {
            'calculated_totals': self.correct_calculated_totals(),
            'stock_status': self.correct_stock_status(),
            'price_ranges': self.correct_price_ranges()
        }
    
    return corrections

    def close(self):
        """Close database connection"""
        self.conn.close()
```

### 2. Manual Review Processes

#### Quality Review Checklist
1. **Data Completeness Review**
   - Identify missing critical fields
   - Review data collection processes
   - Implement additional validation rules

2. **Data Accuracy Review**
   - Verify calculation formulas
   - Cross-reference with source systems
   - Validate business rule implementations

3. **Data Consistency Review**
   - Check referential integrity
   - Validate data format consistency
   - Review naming conventions

4. **Data Timeliness Review**
   - Monitor data freshness
   - Review ETL processing schedules
   - Optimize processing performance

---

## Performance Monitoring

### 1. Query Performance Monitoring

#### Performance Metrics Collection
```python
class PerformanceMonitor:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
    
    def monitor_query_performance(self, query, query_name):
        """Monitor query execution performance"""
        start_time = time.time()
        
        try:
            result = pd.read_sql_query(query, self.conn)
            execution_time = time.time() - start_time
            
            performance_metrics = {
                'query_name': query_name,
                'execution_time': execution_time,
                'record_count': len(result),
                'timestamp': datetime.now().isoformat(),
                'status': 'SUCCESS'
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            performance_metrics = {
                'query_name': query_name,
                'execution_time': execution_time,
                'record_count': 0,
                'timestamp': datetime.now().isoformat(),
                'status': 'ERROR',
                'error_message': str(e)
            }
        
        return performance_metrics
    
    def get_slow_queries(self, threshold_seconds=5):
        """Identify slow queries"""
        # This would typically query a performance monitoring system
        # For demonstration, we'll simulate slow query detection
        slow_queries = [
            {
                'query_name': 'customer_analysis_complex',
                'execution_time': 8.5,
                'recommendation': 'Consider adding indexes on customer_id and sale_date'
            },
            {
                'query_name': 'product_performance_analysis',
                'execution_time': 6.2,
                'recommendation': 'Consider partitioning by product category'
            }
        ]
        
        return slow_queries
    
    def close(self):
        """Close database connection"""
        self.conn.close()
```

---

## Summary

This comprehensive data quality monitoring framework is specifically designed for the wide table architecture, providing:

### Key Features
- **Automated Quality Checks**: Comprehensive monitoring of completeness, accuracy, and consistency
- **Real-time Monitoring**: Continuous quality assessment of wide table data
- **Automated Corrections**: Self-healing capabilities for common data quality issues
- **Performance Monitoring**: Query performance tracking and optimization recommendations
- **Alert System**: Proactive notification of quality issues

### Wide Table Specific Benefits
- **Simplified Monitoring**: Fewer tables to monitor with clearer quality metrics
- **Better Performance**: Optimized quality checks for wide table structure
- **Enhanced Accuracy**: Focused monitoring on critical calculated fields
- **Improved Consistency**: Streamlined referential integrity checks

This framework ensures high data quality standards while leveraging the performance benefits of the wide table architecture.