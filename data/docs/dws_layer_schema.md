# DWS Layer (Data Warehouse Summary) Schema Design - Optimized for Wide Table DWD

## Overview
The DWS layer provides pre-aggregated summary tables optimized for the new wide table DWD design. This layer focuses on high-performance analytical queries and business intelligence reporting, leveraging the optimized DWD structure for maximum efficiency.

## Design Philosophy

### Core Principles
- **Aggregation Optimization**: Pre-calculate common business metrics
- **Performance First**: Optimize for analytical query performance
- **Business Focus**: Align with business intelligence requirements
- **Scalable Aggregation**: Support multiple aggregation levels and time periods

### Design Benefits
- **Query Performance**: Pre-aggregated data reduces computation overhead
- **Business Intelligence**: Ready-to-use metrics for reporting and dashboards
- **Consistency**: Standardized business metrics across the organization
- **Flexibility**: Support for various analytical patterns and time periods

---

## DWS Table Structure

### Customer Analytics Summary

#### Table: dws_customer_summary
**Purpose**: Comprehensive customer analytics and behavior summary
**Source**: dwd_transaction_detail + dwd_customer_dimension
**Update Frequency**: Daily
**Retention**: 7 years

##### Structure
| Column | Type | Constraints | Description | Calculation Logic |
|--------|------|-------------|-------------|-------------------|
| customer_id | TEXT | PRIMARY KEY | Customer identifier | dwd_customer_dimension.customer_id |
| customer_name | VARCHAR(200) | NOT NULL | Customer name | dwd_customer_dimension.customer_name |
| customer_type | VARCHAR(20) | NOT NULL | Customer type | dwd_customer_dimension.customer_type |
| region | VARCHAR(50) | NULL | Geographic region | dwd_customer_dimension.region |
| total_transactions | INTEGER | NOT NULL | Total transaction count | COUNT(dwd_transaction_detail.sale_id) |
| total_spent | DECIMAL(15,2) | NOT NULL | Total amount spent | SUM(dwd_transaction_detail.total_amount) |
| avg_transaction_value | DECIMAL(12,2) | NOT NULL | Average transaction value | AVG(dwd_transaction_detail.total_amount) |
| max_transaction_value | DECIMAL(12,2) | NOT NULL | Maximum transaction value | MAX(dwd_transaction_detail.total_amount) |
| min_transaction_value | DECIMAL(12,2) | NOT NULL | Minimum transaction value | MIN(dwd_transaction_detail.total_amount) |
| total_quantity_purchased | INTEGER | NOT NULL | Total quantity purchased | SUM(dwd_transaction_detail.quantity_sold) |
| first_transaction_date | DATE | NOT NULL | First transaction date | MIN(dwd_transaction_detail.sale_date) |
| last_transaction_date | DATE | NOT NULL | Last transaction date | MAX(dwd_transaction_detail.sale_date) |
| days_since_last_transaction | INTEGER | NULL | Days since last transaction | DATEDIFF(DAY, last_transaction_date, GETDATE()) |
| transaction_frequency_days | DECIMAL(8,2) | NULL | Average days between transactions | Calculated |
| customer_lifetime_days | INTEGER | NOT NULL | Customer lifetime in days | DATEDIFF(DAY, first_transaction_date, last_transaction_date) |
| is_active_customer | BOOLEAN | NOT NULL | Active customer flag | days_since_last_transaction <= 90 |
| customer_value_tier | VARCHAR(20) | NOT NULL | Customer value tier | Derived from total_spent |
| etl_batch_id | VARCHAR(50) | NOT NULL | ETL batch ID | Generated |
| etl_timestamp | DATETIME | NOT NULL | ETL timestamp | CURRENT_TIMESTAMP |

##### Business Rules
- Customer value tiers: Bronze (<1000), Silver (1000-5000), Gold (5000-20000), Platinum (>20000)
- Active customer: Last transaction within 90 days
- Transaction frequency: Average days between transactions
- Customer lifetime: Days between first and last transaction

---

### Product Performance Summary

#### Table: dws_product_summary
**Purpose**: Comprehensive product performance and inventory summary
**Source**: dwd_transaction_detail + dwd_inventory_snapshot + dwd_product_dimension
**Update Frequency**: Daily
**Retention**: 7 years

##### Structure
| Column | Type | Constraints | Description | Calculation Logic |
|--------|------|-------------|-------------|-------------------|
| product_id | TEXT | PRIMARY KEY | Product identifier | dwd_product_dimension.product_id |
| product_name | VARCHAR(200) | NOT NULL | Product name | dwd_product_dimension.product_name |
| category | VARCHAR(100) | NOT NULL | Product category | dwd_product_dimension.category |
| unit_price | DECIMAL(12,2) | NOT NULL | Current unit price | dwd_product_dimension.unit_price |
| price_range | VARCHAR(20) | NOT NULL | Price range | dwd_product_dimension.price_range |
| total_sales_count | INTEGER | NOT NULL | Total sales count | COUNT(dwd_transaction_detail.sale_id) |
| total_quantity_sold | INTEGER | NOT NULL | Total quantity sold | SUM(dwd_transaction_detail.quantity_sold) |
| total_revenue | DECIMAL(15,2) | NOT NULL | Total revenue | SUM(dwd_transaction_detail.total_amount) |
| avg_sale_price | DECIMAL(12,2) | NOT NULL | Average sale price | AVG(dwd_transaction_detail.price_per_unit) |
| max_sale_price | DECIMAL(12,2) | NOT NULL | Maximum sale price | MAX(dwd_transaction_detail.price_per_unit) |
| min_sale_price | DECIMAL(12,2) | NOT NULL | Minimum sale price | MIN(dwd_transaction_detail.price_per_unit) |
| avg_quantity_per_sale | DECIMAL(8,2) | NOT NULL | Average quantity per sale | AVG(dwd_transaction_detail.quantity_sold) |
| first_sale_date | DATE | NOT NULL | First sale date | MIN(dwd_transaction_detail.sale_date) |
| last_sale_date | DATE | NOT NULL | Last sale date | MAX(dwd_transaction_detail.sale_date) |
| days_since_last_sale | INTEGER | NULL | Days since last sale | DATEDIFF(DAY, last_sale_date, GETDATE()) |
| current_stock_level | INTEGER | NOT NULL | Current stock level | dwd_inventory_snapshot.stock_level |
| current_stock_value | DECIMAL(15,2) | NOT NULL | Current stock value | dwd_inventory_snapshot.stock_value |
| stock_status | VARCHAR(20) | NOT NULL | Current stock status | dwd_inventory_snapshot.stock_status |
| is_low_stock | BOOLEAN | NOT NULL | Low stock flag | dwd_inventory_snapshot.is_low_stock |
| turnover_ratio | DECIMAL(8,4) | NULL | Inventory turnover ratio | total_quantity_sold / current_stock_level |
| product_performance_tier | VARCHAR(20) | NOT NULL | Performance tier | Derived from total_revenue |
| etl_batch_id | VARCHAR(50) | NOT NULL | ETL batch ID | Generated |
| etl_timestamp | DATETIME | NOT NULL | ETL timestamp | CURRENT_TIMESTAMP |

##### Business Rules
- Performance tiers: Low (<1000), Medium (1000-10000), High (10000-50000), Top (>50000)
- Turnover ratio: Total quantity sold / current stock level
- Low stock: Stock level below reorder point
- Price range: Low (<50), Medium (50-200), High (200-1000), Premium (>1000)

---

### Sales Analytics Summary

#### Table: dws_sales_summary_daily
**Purpose**: Daily sales performance summary
**Source**: dwd_transaction_detail
**Update Frequency**: Daily
**Retention**: 3 years

##### Structure
| Column | Type | Constraints | Description | Calculation Logic |
|--------|------|-------------|-------------|-------------------|
| sale_date | DATE | PRIMARY KEY | Sale date | dwd_transaction_detail.sale_date |
| sale_year | INTEGER | NOT NULL | Sale year | YEAR(sale_date) |
| sale_month | INTEGER | NOT NULL | Sale month | MONTH(sale_date) |
| sale_quarter | INTEGER | NOT NULL | Sale quarter | QUARTER(sale_date) |
| sale_week | INTEGER | NOT NULL | Sale week | WEEK(sale_date) |
| sale_day_of_week | INTEGER | NOT NULL | Day of week | DAYOFWEEK(sale_date) |
| total_transactions | INTEGER | NOT NULL | Total transactions | COUNT(dwd_transaction_detail.sale_id) |
| total_quantity_sold | INTEGER | NOT NULL | Total quantity sold | SUM(dwd_transaction_detail.quantity_sold) |
| total_revenue | DECIMAL(15,2) | NOT NULL | Total revenue | SUM(dwd_transaction_detail.total_amount) |
| avg_transaction_value | DECIMAL(12,2) | NOT NULL | Average transaction value | AVG(dwd_transaction_detail.total_amount) |
| max_transaction_value | DECIMAL(12,2) | NOT NULL | Maximum transaction value | MAX(dwd_transaction_detail.total_amount) |
| min_transaction_value | DECIMAL(12,2) | NOT NULL | Minimum transaction value | MIN(dwd_transaction_detail.total_amount) |
| unique_customers | INTEGER | NOT NULL | Unique customers | COUNT(DISTINCT dwd_transaction_detail.customer_id) |
| unique_products | INTEGER | NOT NULL | Unique products | COUNT(DISTINCT dwd_transaction_detail.product_id) |
| revenue_per_customer | DECIMAL(12,2) | NULL | Revenue per customer | total_revenue / unique_customers |
| revenue_per_product | DECIMAL(12,2) | NULL | Revenue per product | total_revenue / unique_products |
| etl_batch_id | VARCHAR(50) | NOT NULL | ETL batch ID | Generated |
| etl_timestamp | DATETIME | NOT NULL | ETL timestamp | CURRENT_TIMESTAMP |

---

#### Table: dws_sales_summary_monthly
**Purpose**: Monthly sales performance summary
**Source**: dwd_transaction_detail
**Update Frequency**: Monthly
**Retention**: 5 years

##### Structure
| Column | Type | Constraints | Description | Calculation Logic |
|--------|------|-------------|-------------|-------------------|
| sale_year | INTEGER | PRIMARY KEY | Sale year | YEAR(dwd_transaction_detail.sale_date) |
| sale_month | INTEGER | PRIMARY KEY | Sale month | MONTH(dwd_transaction_detail.sale_date) |
| sale_quarter | INTEGER | NOT NULL | Sale quarter | QUARTER(sale_date) |
| total_transactions | INTEGER | NOT NULL | Total transactions | COUNT(dwd_transaction_detail.sale_id) |
| total_quantity_sold | INTEGER | NOT NULL | Total quantity sold | SUM(dwd_transaction_detail.quantity_sold) |
| total_revenue | DECIMAL(15,2) | NOT NULL | Total revenue | SUM(dwd_transaction_detail.total_amount) |
| avg_transaction_value | DECIMAL(12,2) | NOT NULL | Average transaction value | AVG(dwd_transaction_detail.total_amount) |
| unique_customers | INTEGER | NOT NULL | Unique customers | COUNT(DISTINCT dwd_transaction_detail.customer_id) |
| unique_products | INTEGER | NOT NULL | Unique products | COUNT(DISTINCT dwd_transaction_detail.product_id) |
| revenue_growth_rate | DECIMAL(8,4) | NULL | Revenue growth rate | Calculated vs previous month |
| transaction_growth_rate | DECIMAL(8,4) | NULL | Transaction growth rate | Calculated vs previous month |
| customer_growth_rate | DECIMAL(8,4) | NULL | Customer growth rate | Calculated vs previous month |
| etl_batch_id | VARCHAR(50) | NOT NULL | ETL batch ID | Generated |
| etl_timestamp | DATETIME | NOT NULL | ETL timestamp | CURRENT_TIMESTAMP |

---

### Inventory Management Summary

#### Table: dws_inventory_summary
**Purpose**: Inventory management and optimization summary
**Source**: dwd_inventory_snapshot + dwd_product_dimension
**Update Frequency**: Daily
**Retention**: 3 years

##### Structure
| Column | Type | Constraints | Description | Calculation Logic |
|--------|------|-------------|-------------|-------------------|
| product_id | TEXT | PRIMARY KEY | Product identifier | dwd_inventory_snapshot.product_id |
| product_name | VARCHAR(200) | NOT NULL | Product name | dwd_product_dimension.product_name |
| category | VARCHAR(100) | NOT NULL | Product category | dwd_product_dimension.category |
| current_stock_level | INTEGER | NOT NULL | Current stock level | dwd_inventory_snapshot.stock_level |
| current_stock_value | DECIMAL(15,2) | NOT NULL | Current stock value | dwd_inventory_snapshot.stock_value |
| stock_status | VARCHAR(20) | NOT NULL | Stock status | dwd_inventory_snapshot.stock_status |
| is_low_stock | BOOLEAN | NOT NULL | Low stock flag | dwd_inventory_snapshot.is_low_stock |
| reorder_point | INTEGER | NULL | Reorder point | dwd_inventory_snapshot.reorder_point |
| days_since_update | INTEGER | NULL | Days since update | dwd_inventory_snapshot.days_since_update |
| is_stale_data | BOOLEAN | NOT NULL | Stale data flag | dwd_inventory_snapshot.is_stale_data |
| unit_price | DECIMAL(12,2) | NOT NULL | Unit price | dwd_product_dimension.unit_price |
| price_range | VARCHAR(20) | NOT NULL | Price range | dwd_product_dimension.price_range |
| inventory_turnover_ratio | DECIMAL(8,4) | NULL | Turnover ratio | Calculated from sales data |
| stock_value_percentage | DECIMAL(8,4) | NULL | Stock value percentage | Calculated vs total inventory value |
| etl_batch_id | VARCHAR(50) | NOT NULL | ETL batch ID | Generated |
| etl_timestamp | DATETIME | NOT NULL | ETL timestamp | CURRENT_TIMESTAMP |

---

### Category Performance Summary

#### Table: dws_category_performance
**Purpose**: Product category performance analysis
**Source**: dwd_transaction_detail + dwd_product_dimension
**Update Frequency**: Daily
**Retention**: 5 years

##### Structure
| Column | Type | Constraints | Description | Calculation Logic |
|--------|------|-------------|-------------|-------------------|
| category | VARCHAR(100) | PRIMARY KEY | Product category | dwd_product_dimension.category |
| total_products | INTEGER | NOT NULL | Total products | COUNT(DISTINCT dwd_product_dimension.product_id) |
| total_transactions | INTEGER | NOT NULL | Total transactions | COUNT(dwd_transaction_detail.sale_id) |
| total_quantity_sold | INTEGER | NOT NULL | Total quantity sold | SUM(dwd_transaction_detail.quantity_sold) |
| total_revenue | DECIMAL(15,2) | NOT NULL | Total revenue | SUM(dwd_transaction_detail.total_amount) |
| avg_transaction_value | DECIMAL(12,2) | NOT NULL | Average transaction value | AVG(dwd_transaction_detail.total_amount) |
| avg_sale_price | DECIMAL(12,2) | NOT NULL | Average sale price | AVG(dwd_transaction_detail.price_per_unit) |
| revenue_per_product | DECIMAL(12,2) | NULL | Revenue per product | total_revenue / total_products |
| transaction_per_product | DECIMAL(8,2) | NULL | Transactions per product | total_transactions / total_products |
| category_performance_tier | VARCHAR(20) | NOT NULL | Performance tier | Derived from total_revenue |
| market_share_percentage | DECIMAL(8,4) | NULL | Market share percentage | Calculated vs total revenue |
| etl_batch_id | VARCHAR(50) | NOT NULL | ETL batch ID | Generated |
| etl_timestamp | DATETIME | NOT NULL | ETL timestamp | CURRENT_TIMESTAMP |

---

## ETL Processing Logic

### Customer Summary ETL
```python
def process_customer_summary():
    # Extract transaction data
    transaction_data = extract_transaction_data()
    customer_data = extract_customer_data()
    
    # Group by customer
    customer_summary = {}
    for transaction in transaction_data:
        customer_id = transaction.customer_id
        if customer_id not in customer_summary:
            customer_summary[customer_id] = {
                'customer_id': customer_id,
                'transactions': [],
                'total_spent': 0,
                'total_quantity': 0,
                'first_date': transaction.sale_date,
                'last_date': transaction.sale_date
            }
        
        customer_summary[customer_id]['transactions'].append(transaction)
        customer_summary[customer_id]['total_spent'] += transaction.total_amount
        customer_summary[customer_id]['total_quantity'] += transaction.quantity_sold
        
        if transaction.sale_date < customer_summary[customer_id]['first_date']:
            customer_summary[customer_id]['first_date'] = transaction.sale_date
        if transaction.sale_date > customer_summary[customer_id]['last_date']:
            customer_summary[customer_id]['last_date'] = transaction.sale_date
    
    # Calculate derived metrics
    for customer_id, summary in customer_summary.items():
        customer_info = get_customer_info(customer_id)
        
        summary_record = {
            'customer_id': customer_id,
            'customer_name': customer_info.customer_name,
            'customer_type': customer_info.customer_type,
            'region': customer_info.region,
            'total_transactions': len(summary['transactions']),
            'total_spent': summary['total_spent'],
            'avg_transaction_value': summary['total_spent'] / len(summary['transactions']),
            'total_quantity_purchased': summary['total_quantity'],
            'first_transaction_date': summary['first_date'],
            'last_transaction_date': summary['last_date'],
            'days_since_last_transaction': (datetime.now() - summary['last_date']).days,
            'customer_lifetime_days': (summary['last_date'] - summary['first_date']).days,
            'is_active_customer': (datetime.now() - summary['last_date']).days <= 90,
            'customer_value_tier': get_customer_tier(summary['total_spent']),
            'etl_batch_id': get_current_batch_id(),
            'etl_timestamp': datetime.now()
        }
        
        # Load to DWS
        load_customer_summary(summary_record)
```

### Product Summary ETL
```python
def process_product_summary():
    # Extract transaction and inventory data
    transaction_data = extract_transaction_data()
    inventory_data = extract_inventory_data()
    product_data = extract_product_data()
    
    # Group by product
    product_summary = {}
    for transaction in transaction_data:
        product_id = transaction.product_id
        if product_id not in product_summary:
            product_summary[product_id] = {
                'product_id': product_id,
                'transactions': [],
                'total_revenue': 0,
                'total_quantity': 0,
                'prices': [],
                'first_date': transaction.sale_date,
                'last_date': transaction.sale_date
            }
        
        product_summary[product_id]['transactions'].append(transaction)
        product_summary[product_id]['total_revenue'] += transaction.total_amount
        product_summary[product_id]['total_quantity'] += transaction.quantity_sold
        product_summary[product_id]['prices'].append(transaction.price_per_unit)
        
        if transaction.sale_date < product_summary[product_id]['first_date']:
            product_summary[product_id]['first_date'] = transaction.sale_date
        if transaction.sale_date > product_summary[product_id]['last_date']:
            product_summary[product_id]['last_date'] = transaction.sale_date
    
    # Calculate derived metrics
    for product_id, summary in product_summary.items():
        product_info = get_product_info(product_id)
        inventory_info = get_inventory_info(product_id)
        
        summary_record = {
            'product_id': product_id,
            'product_name': product_info.product_name,
            'category': product_info.category,
            'unit_price': product_info.unit_price,
            'price_range': product_info.price_range,
            'total_sales_count': len(summary['transactions']),
            'total_quantity_sold': summary['total_quantity'],
            'total_revenue': summary['total_revenue'],
            'avg_sale_price': sum(summary['prices']) / len(summary['prices']),
            'max_sale_price': max(summary['prices']),
            'min_sale_price': min(summary['prices']),
            'avg_quantity_per_sale': summary['total_quantity'] / len(summary['transactions']),
            'first_sale_date': summary['first_date'],
            'last_sale_date': summary['last_date'],
            'days_since_last_sale': (datetime.now() - summary['last_date']).days,
            'current_stock_level': inventory_info.stock_level,
            'current_stock_value': inventory_info.stock_value,
            'stock_status': inventory_info.stock_status,
            'is_low_stock': inventory_info.is_low_stock,
            'turnover_ratio': summary['total_quantity'] / inventory_info.stock_level if inventory_info.stock_level > 0 else 0,
            'product_performance_tier': get_product_tier(summary['total_revenue']),
            'etl_batch_id': get_current_batch_id(),
            'etl_timestamp': datetime.now()
        }
        
        # Load to DWS
        load_product_summary(summary_record)
```

---

## Query Performance Examples

### Customer Analytics Query
```sql
-- Top customers by revenue (using DWS)
SELECT 
    customer_name,
    customer_type,
    region,
    total_spent,
    total_transactions,
    avg_transaction_value,
    customer_value_tier,
    is_active_customer
FROM dws_customer_summary
ORDER BY total_spent DESC
LIMIT 10;

-- Customer segmentation analysis
SELECT 
    customer_value_tier,
    COUNT(*) as customer_count,
    AVG(total_spent) as avg_spent,
    AVG(total_transactions) as avg_transactions,
    SUM(total_spent) as total_revenue
FROM dws_customer_summary
GROUP BY customer_value_tier
ORDER BY total_revenue DESC;
```

### Product Performance Query
```sql
-- Top products by revenue (using DWS)
SELECT 
    product_name,
    category,
    total_revenue,
    total_quantity_sold,
    avg_sale_price,
    current_stock_level,
    turnover_ratio,
    product_performance_tier
FROM dws_product_summary
ORDER BY total_revenue DESC
LIMIT 10;

-- Category performance analysis
SELECT 
    category,
    COUNT(*) as product_count,
    SUM(total_revenue) as category_revenue,
    AVG(turnover_ratio) as avg_turnover,
    SUM(current_stock_value) as total_stock_value
FROM dws_product_summary
GROUP BY category
ORDER BY category_revenue DESC;
```

### Sales Trend Analysis
```sql
-- Daily sales trends (using DWS)
SELECT 
    sale_date,
    total_revenue,
    total_transactions,
    unique_customers,
    avg_transaction_value,
    revenue_per_customer
FROM dws_sales_summary_daily
WHERE sale_date >= '2024-01-01'
ORDER BY sale_date;

-- Monthly growth analysis
SELECT 
    sale_year,
    sale_month,
    total_revenue,
    revenue_growth_rate,
    transaction_growth_rate,
    customer_growth_rate
FROM dws_sales_summary_monthly
WHERE sale_year >= 2024
ORDER BY sale_year, sale_month;
```

---

## Benefits of This DWS Design

### 1. **Performance Benefits**
- **Pre-aggregated Data**: Reduces computation overhead for common queries
- **Optimized for Analytics**: Designed specifically for analytical workloads
- **Fast Reporting**: Ready-to-use metrics for dashboards and reports
- **Reduced Load**: Minimizes impact on DWD layer for complex queries

### 2. **Business Benefits**
- **Standardized Metrics**: Consistent business metrics across the organization
- **Quick Insights**: Fast access to key performance indicators
- **Trend Analysis**: Built-in support for temporal analysis
- **Segmentation**: Pre-calculated customer and product segments

### 3. **Operational Benefits**
- **Maintenance**: Easier to maintain and update aggregated data
- **Scalability**: Design scales with business growth
- **Flexibility**: Support for various analytical patterns
- **Consistency**: Ensures data consistency across different reports

This optimized DWS design provides high-performance analytical capabilities while leveraging the benefits of the new wide table DWD architecture.
