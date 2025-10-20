# ETL Processing Logic and Implementation Guide - Wide Table Architecture

## Overview
This document describes the Extract, Transform, and Load (ETL) processing logic for the optimized wide table data warehouse architecture. It includes data validation, transformation rules, error handling, and performance optimization strategies specifically designed for the wide table approach.

## ETL Architecture

```
Source Systems → Staging Area → DWD Layer (Wide Tables) → DWS Layer → Data Marts
     ↓              ↓            ↓                        ↓           ↓
  Raw Data      Validated     Optimized Wide Tables    Aggregated  Business
  Extraction    Data          (2 Fact + 2 Dimension)   Data        Intelligence
```

---

## ETL Processing Framework

### 1. ETL Job Structure
```python
class ETLJob:
    def __init__(self, job_name, source_tables, target_tables):
        self.job_name = job_name
        self.source_tables = source_tables
        self.target_tables = target_tables
        self.batch_id = self.generate_batch_id()
        self.start_time = datetime.now()
        
    def execute(self):
        try:
            self.extract()
            self.validate()
            self.transform()
            self.load()
            self.post_process()
            self.log_success()
        except Exception as e:
            self.handle_error(e)
            self.log_failure(e)
```

### 2. Wide Table Processing Strategy
- **Batch ID**: Unique identifier for each ETL run
- **Wide Table Optimization**: Process multiple source tables into single wide tables
- **Foreign Key Strategy**: Maintain referential integrity without redundant data
- **Parallel Processing**: Process fact tables and dimension tables simultaneously
- **Dependency Management**: Ensure proper processing order for wide table dependencies

---

## Source to DWD ETL Logic - Wide Table Design

### 1. Transaction Detail ETL Process (Core Wide Table)

#### Extract Phase
```sql
-- Extract sales data with order relationship
SELECT 
    s.sale_id,
    s.product_id,
    s.product_name,
    s.quantity_sold,
    s.price_per_unit,
    s.total_amount,
    s.sale_date,
    o.customer_id,
    o.order_id,
    o.order_date,
    o.status as order_status,
    o.payment_method,
    o.shipping_address
FROM sales s
LEFT JOIN orders o ON s.customer_id = o.customer_id 
    AND DATE(s.sale_date) = DATE(o.order_date)
WHERE s.sale_date >= :last_etl_timestamp
   OR o.order_date >= :last_etl_timestamp;
```

#### Transform Phase
```python
def transform_transaction_data(raw_data):
    """Transform sales and order data into transaction wide table"""
    transformed_data = []
    
    for record in raw_data:
        # Data cleaning and standardization
        transformed_record = {
            'sale_id': record['sale_id'],
            'product_id': record['product_id'],
            'customer_id': record['customer_id'],  # Foreign key only
            'quantity_sold': record['quantity_sold'],
            'price_per_unit': round(record['price_per_unit'], 2),
            'total_amount': round(record['total_amount'], 2),
            'calculated_total': round(record['quantity_sold'] * record['price_per_unit'], 2),
            'sale_date': record['sale_date'],
            'sale_year': record['sale_date'].year,
            'sale_month': record['sale_date'].month,
            'sale_quarter': get_quarter(record['sale_date']),
            'sale_week': record['sale_date'].isocalendar()[1],
            'sale_day_of_week': record['sale_date'].weekday(),
            'sale_value_range': get_sale_value_range(record['total_amount']),
            'order_id': record['order_id'],
            'order_date': record['order_date'],
            'order_status': record['order_status'],
            'payment_method': record['payment_method'],
            'shipping_address': record['shipping_address'],
            'data_quality_score': calculate_transaction_quality_score(record),
            'etl_batch_id': self.batch_id,
            'etl_timestamp': datetime.now()
        }
        
        transformed_data.append(transformed_record)
    
    return transformed_data

def get_sale_value_range(total_amount):
    """Determine sale value range"""
    if total_amount < 100:
        return 'Low'
    elif total_amount < 500:
        return 'Medium'
    elif total_amount < 1000:
        return 'High'
    else:
        return 'Premium'

def calculate_transaction_quality_score(record):
    """Calculate data quality score for transaction record"""
    score = 100
    
    # Completeness checks
    if not record['sale_id']:
        score -= 20
    if not record['product_id']:
        score -= 20
    if not record['total_amount']:
        score -= 15
    
    # Accuracy checks
    if record['calculated_total'] != record['total_amount']:
        score -= 10
    
    # Validity checks
    if record['quantity_sold'] <= 0:
        score -= 10
    if record['price_per_unit'] <= 0:
        score -= 10
    
    # Time validity
    if record['sale_date'] > datetime.now():
        score -= 15
    
    return max(0, score)
```

#### Load Phase
```sql
-- Load transaction detail data
INSERT INTO dwd_transaction_detail (
    sale_id, product_id, customer_id, quantity_sold, price_per_unit,
    total_amount, calculated_total, sale_date, sale_year, sale_month,
    sale_quarter, sale_week, sale_day_of_week, sale_value_range,
    order_id, order_date, order_status, payment_method, shipping_address,
    data_quality_score, etl_batch_id, etl_timestamp
) VALUES (
    :sale_id, :product_id, :customer_id, :quantity_sold, :price_per_unit,
    :total_amount, :calculated_total, :sale_date, :sale_year, :sale_month,
    :sale_quarter, :sale_week, :sale_day_of_week, :sale_value_range,
    :order_id, :order_date, :order_status, :payment_method, :shipping_address,
    :data_quality_score, :etl_batch_id, :etl_timestamp
)
ON CONFLICT (sale_id) DO UPDATE SET
    quantity_sold = VALUES(quantity_sold),
    price_per_unit = VALUES(price_per_unit),
    total_amount = VALUES(total_amount),
    calculated_total = VALUES(calculated_total),
    sale_value_range = VALUES(sale_value_range),
    order_status = VALUES(order_status),
    payment_method = VALUES(payment_method),
    data_quality_score = VALUES(data_quality_score),
    etl_batch_id = VALUES(etl_batch_id),
    etl_timestamp = VALUES(etl_timestamp);
```

---

### 2. Inventory Snapshot ETL Process (Snapshot Wide Table)

#### Extract Phase
```sql
-- Extract inventory data with product information
SELECT 
    i.product_id,
    i.stock_level,
    i.last_updated,
    p.unit_price
FROM inventory i
LEFT JOIN products p ON i.product_id = p.product_id
WHERE i.last_updated >= :last_etl_timestamp;
```

#### Transform Phase
```python
def transform_inventory_data(raw_data):
    """Transform inventory data into snapshot wide table"""
    transformed_data = []
    
    for record in raw_data:
        # Calculate derived fields
        stock_status = get_stock_status(record['stock_level'])
        days_since_update = (datetime.now() - record['last_updated']).days
        stock_value = record['stock_level'] * record['unit_price']
        reorder_point = calculate_reorder_point(record['product_id'])
        
        transformed_record = {
            'product_id': record['product_id'],
            'stock_level': record['stock_level'],
            'last_updated': record['last_updated'],
            'stock_status': stock_status,
            'days_since_update': days_since_update,
            'is_stale_data': days_since_update > 7,
            'stock_value': round(stock_value, 2),
            'reorder_point': reorder_point,
            'is_low_stock': record['stock_level'] < reorder_point,
            'data_quality_score': calculate_inventory_quality_score(record),
            'etl_batch_id': self.batch_id,
            'etl_timestamp': datetime.now()
        }
        
        transformed_data.append(transformed_record)
    
    return transformed_data

def get_stock_status(stock_level):
    """Determine stock status based on stock level"""
    if stock_level > 10:
        return 'In Stock'
    elif stock_level > 0:
        return 'Low Stock'
    else:
        return 'Out of Stock'

def calculate_reorder_point(product_id):
    """Calculate reorder point based on historical sales velocity"""
    # This would typically query historical sales data
    # For now, using a simple business rule
    return 10  # Default reorder point

def calculate_inventory_quality_score(record):
    """Calculate data quality score for inventory record"""
    score = 100
    
    # Completeness checks
    if not record['product_id']:
        score -= 25
    if record['stock_level'] is None:
        score -= 25
    if not record['last_updated']:
        score -= 25
    
    # Validity checks
    if record['stock_level'] < 0:
        score -= 15
    
    # Timeliness checks
    days_since_update = (datetime.now() - record['last_updated']).days
    if days_since_update > 30:
        score -= 10
    
    return max(0, score)
```

#### Load Phase
```sql
-- Load inventory snapshot data
INSERT INTO dwd_inventory_snapshot (
    product_id, stock_level, last_updated, stock_status,
    days_since_update, is_stale_data, stock_value, reorder_point,
    is_low_stock, data_quality_score, etl_batch_id, etl_timestamp
) VALUES (
    :product_id, :stock_level, :last_updated, :stock_status,
    :days_since_update, :is_stale_data, :stock_value, :reorder_point,
    :is_low_stock, :data_quality_score, :etl_batch_id, :etl_timestamp
)
ON CONFLICT (product_id) DO UPDATE SET
    stock_level = VALUES(stock_level),
    last_updated = VALUES(last_updated),
    stock_status = VALUES(stock_status),
    days_since_update = VALUES(days_since_update),
    is_stale_data = VALUES(is_stale_data),
    stock_value = VALUES(stock_value),
    reorder_point = VALUES(reorder_point),
    is_low_stock = VALUES(is_low_stock),
    data_quality_score = VALUES(data_quality_score),
    etl_batch_id = VALUES(etl_batch_id),
    etl_timestamp = VALUES(etl_timestamp);
```

---

### 3. Customer Dimension ETL Process

#### Extract Phase
```sql
-- Extract customer data
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
WHERE updated_at >= :last_etl_timestamp
   OR created_at >= :last_etl_timestamp;
```

#### Transform Phase
```python
def transform_customer_dimension_data(raw_data):
    """Transform customer data into dimension table"""
    transformed_data = []
    
    for record in raw_data:
        transformed_record = {
            'customer_id': record['customer_id'],
            'customer_name': record['customer_name'].strip(),
            'contact_person': record['contact_person'].strip() if record['contact_person'] else None,
            'email': record['email'].lower().strip() if record['email'] else None,
            'phone': standardize_phone(record['phone']) if record['phone'] else None,
            'address': record['address'].strip() if record['address'] else None,
            'customer_type': record['customer_type'].upper().strip(),
            'region': extract_region_from_address(record['address']) if record['address'] else None,
            'created_at': record['created_at'],
            'registration_year': record['created_at'].year,
            'registration_month': record['created_at'].month,
            'registration_quarter': get_quarter(record['created_at']),
            'updated_at': record['updated_at'],
            'days_since_update': (datetime.now() - record['updated_at']).days,
            'is_active_customer': determine_active_status(record),
            'etl_batch_id': self.batch_id,
            'etl_timestamp': datetime.now()
        }
        
        transformed_data.append(transformed_record)
    
    return transformed_data

def determine_active_status(record):
    """Determine if customer is active based on business rules"""
    days_since_update = (datetime.now() - record['updated_at']).days
    return days_since_update <= 90  # Active if updated within 90 days
```

#### Load Phase
```sql
-- Load customer dimension data
INSERT INTO dwd_customer_dimension (
    customer_id, customer_name, contact_person, email, phone,
    address, customer_type, region, created_at, registration_year,
    registration_month, registration_quarter, updated_at, days_since_update,
    is_active_customer, etl_batch_id, etl_timestamp
) VALUES (
    :customer_id, :customer_name, :contact_person, :email, :phone,
    :address, :customer_type, :region, :created_at, :registration_year,
    :registration_month, :registration_quarter, :updated_at, :days_since_update,
    :is_active_customer, :etl_batch_id, :etl_timestamp
)
ON CONFLICT (customer_id) DO UPDATE SET
    customer_name = VALUES(customer_name),
    contact_person = VALUES(contact_person),
    email = VALUES(email),
    phone = VALUES(phone),
    address = VALUES(address),
    customer_type = VALUES(customer_type),
    region = VALUES(region),
    updated_at = VALUES(updated_at),
    days_since_update = VALUES(days_since_update),
    is_active_customer = VALUES(is_active_customer),
    etl_batch_id = VALUES(etl_batch_id),
    etl_timestamp = VALUES(etl_timestamp);
```

---

### 4. Product Dimension ETL Process

#### Extract Phase
```sql
-- Extract product data
SELECT 
    product_id,
    product_name,
    category,
    unit_price
FROM products
WHERE updated_at >= :last_etl_timestamp
   OR created_at >= :last_etl_timestamp;
```

#### Transform Phase
```python
def transform_product_dimension_data(raw_data):
    """Transform product data into dimension table"""
    transformed_data = []
    
    for record in raw_data:
        transformed_record = {
            'product_id': record['product_id'],
            'product_name': record['product_name'].strip(),
            'category': record['category'].upper().strip(),
            'unit_price': round(record['unit_price'], 2),
            'price_range': get_price_range(record['unit_price']),
            'etl_batch_id': self.batch_id,
            'etl_timestamp': datetime.now()
        }
        
        transformed_data.append(transformed_record)
    
    return transformed_data

def get_price_range(unit_price):
    """Determine price range based on unit price"""
    if unit_price < 50:
        return 'Low'
    elif unit_price < 200:
        return 'Medium'
    elif unit_price < 1000:
        return 'High'
    else:
        return 'Premium'
```

#### Load Phase
```sql
-- Load product dimension data
INSERT INTO dwd_product_dimension (
    product_id, product_name, category, unit_price, price_range,
    etl_batch_id, etl_timestamp
) VALUES (
    :product_id, :product_name, :category, :unit_price, :price_range,
    :etl_batch_id, :etl_timestamp
)
ON CONFLICT (product_id) DO UPDATE SET
    product_name = VALUES(product_name),
    category = VALUES(category),
    unit_price = VALUES(unit_price),
    price_range = VALUES(price_range),
    etl_batch_id = VALUES(etl_batch_id),
    etl_timestamp = VALUES(etl_timestamp);
```

---

## DWD to DWS ETL Logic

### 1. Customer Summary ETL Process

#### Extract Phase
```sql
-- Extract customer transaction data for aggregation
SELECT 
    t.customer_id,
    COUNT(t.sale_id) as total_transactions,
    SUM(t.total_amount) as total_spent,
    AVG(t.total_amount) as avg_transaction_value,
    MAX(t.total_amount) as max_transaction_value,
    MIN(t.total_amount) as min_transaction_value,
    SUM(t.quantity_sold) as total_quantity_purchased,
    MIN(t.sale_date) as first_transaction_date,
    MAX(t.sale_date) as last_transaction_date,
    COUNT(DISTINCT t.product_id) as unique_products_purchased
FROM dwd_transaction_detail t
WHERE t.sale_date >= :last_etl_timestamp
GROUP BY t.customer_id;
```

#### Transform Phase
```python
def transform_customer_summary_data(raw_data):
    """Transform customer transaction data into summary"""
    transformed_data = []
    
    for record in raw_data:
        # Calculate derived metrics
        days_since_last_transaction = (datetime.now() - record['last_transaction_date']).days
        customer_lifetime_days = (record['last_transaction_date'] - record['first_transaction_date']).days
        transaction_frequency = customer_lifetime_days / record['total_transactions'] if record['total_transactions'] > 0 else 0
        is_active_customer = days_since_last_transaction <= 90
        customer_value_tier = get_customer_value_tier(record['total_spent'])
        
        transformed_record = {
            'customer_id': record['customer_id'],
            'total_transactions': record['total_transactions'],
            'total_spent': round(record['total_spent'], 2),
            'avg_transaction_value': round(record['avg_transaction_value'], 2),
            'max_transaction_value': round(record['max_transaction_value'], 2),
            'min_transaction_value': round(record['min_transaction_value'], 2),
            'total_quantity_purchased': record['total_quantity_purchased'],
            'first_transaction_date': record['first_transaction_date'],
            'last_transaction_date': record['last_transaction_date'],
            'days_since_last_transaction': days_since_last_transaction,
            'transaction_frequency_days': round(transaction_frequency, 2),
            'customer_lifetime_days': customer_lifetime_days,
            'is_active_customer': is_active_customer,
            'customer_value_tier': customer_value_tier,
            'etl_batch_id': self.batch_id,
            'etl_timestamp': datetime.now()
        }
        
        transformed_data.append(transformed_record)
    
    return transformed_data

def get_customer_value_tier(total_spent):
    """Determine customer value tier"""
    if total_spent < 1000:
        return 'Bronze'
    elif total_spent < 5000:
        return 'Silver'
    elif total_spent < 20000:
        return 'Gold'
    else:
        return 'Platinum'
```

#### Load Phase
```sql
-- Load customer summary data
INSERT INTO dws_customer_summary (
    customer_id, total_transactions, total_spent, avg_transaction_value,
    max_transaction_value, min_transaction_value, total_quantity_purchased,
    first_transaction_date, last_transaction_date, days_since_last_transaction,
    transaction_frequency_days, customer_lifetime_days, is_active_customer,
    customer_value_tier, etl_batch_id, etl_timestamp
) VALUES (
    :customer_id, :total_transactions, :total_spent, :avg_transaction_value,
    :max_transaction_value, :min_transaction_value, :total_quantity_purchased,
    :first_transaction_date, :last_transaction_date, :days_since_last_transaction,
    :transaction_frequency_days, :customer_lifetime_days, :is_active_customer,
    :customer_value_tier, :etl_batch_id, :etl_timestamp
)
ON CONFLICT (customer_id) DO UPDATE SET
    total_transactions = VALUES(total_transactions),
    total_spent = VALUES(total_spent),
    avg_transaction_value = VALUES(avg_transaction_value),
    max_transaction_value = VALUES(max_transaction_value),
    min_transaction_value = VALUES(min_transaction_value),
    total_quantity_purchased = VALUES(total_quantity_purchased),
    last_transaction_date = VALUES(last_transaction_date),
    days_since_last_transaction = VALUES(days_since_last_transaction),
    transaction_frequency_days = VALUES(transaction_frequency_days),
    customer_lifetime_days = VALUES(customer_lifetime_days),
    is_active_customer = VALUES(is_active_customer),
    customer_value_tier = VALUES(customer_value_tier),
    etl_batch_id = VALUES(etl_batch_id),
    etl_timestamp = VALUES(etl_timestamp);
```

---

### 2. Product Summary ETL Process

#### Extract Phase
```sql
-- Extract product performance data
SELECT 
    t.product_id,
    COUNT(t.sale_id) as total_sales_count,
    SUM(t.quantity_sold) as total_quantity_sold,
    SUM(t.total_amount) as total_revenue,
    AVG(t.price_per_unit) as avg_sale_price,
    MAX(t.price_per_unit) as max_sale_price,
    MIN(t.price_per_unit) as min_sale_price,
    AVG(t.quantity_sold) as avg_quantity_per_sale,
    MIN(t.sale_date) as first_sale_date,
    MAX(t.sale_date) as last_sale_date,
    COUNT(DISTINCT t.customer_id) as unique_customers,
    i.stock_level as current_stock_level,
    i.stock_value as current_stock_value,
    i.stock_status as current_stock_status,
    i.is_low_stock as current_is_low_stock
FROM dwd_transaction_detail t
LEFT JOIN dwd_inventory_snapshot i ON t.product_id = i.product_id
WHERE t.sale_date >= :last_etl_timestamp
GROUP BY t.product_id, i.stock_level, i.stock_value, i.stock_status, i.is_low_stock;
```

#### Transform Phase
```python
def transform_product_summary_data(raw_data):
    """Transform product performance data into summary"""
    transformed_data = []
    
    for record in raw_data:
        # Calculate derived metrics
        days_since_last_sale = (datetime.now() - record['last_sale_date']).days
        turnover_ratio = record['total_quantity_sold'] / record['current_stock_level'] if record['current_stock_level'] > 0 else 0
        product_performance_tier = get_product_performance_tier(record['total_revenue'])
        
        transformed_record = {
            'product_id': record['product_id'],
            'total_sales_count': record['total_sales_count'],
            'total_quantity_sold': record['total_quantity_sold'],
            'total_revenue': round(record['total_revenue'], 2),
            'avg_sale_price': round(record['avg_sale_price'], 2),
            'max_sale_price': round(record['max_sale_price'], 2),
            'min_sale_price': round(record['min_sale_price'], 2),
            'avg_quantity_per_sale': round(record['avg_quantity_per_sale'], 2),
            'first_sale_date': record['first_sale_date'],
            'last_sale_date': record['last_sale_date'],
            'days_since_last_sale': days_since_last_sale,
            'unique_customers': record['unique_customers'],
            'current_stock_level': record['current_stock_level'],
            'current_stock_value': round(record['current_stock_value'], 2),
            'current_stock_status': record['current_stock_status'],
            'current_is_low_stock': record['current_is_low_stock'],
            'turnover_ratio': round(turnover_ratio, 4),
            'product_performance_tier': product_performance_tier,
            'etl_batch_id': self.batch_id,
            'etl_timestamp': datetime.now()
        }
        
        transformed_data.append(transformed_record)
    
    return transformed_data

def get_product_performance_tier(total_revenue):
    """Determine product performance tier"""
    if total_revenue < 1000:
        return 'Low'
    elif total_revenue < 10000:
        return 'Medium'
    elif total_revenue < 50000:
        return 'High'
    else:
        return 'Top'
```

#### Load Phase
```sql
-- Load product summary data
INSERT INTO dws_product_summary (
    product_id, total_sales_count, total_quantity_sold, total_revenue,
    avg_sale_price, max_sale_price, min_sale_price, avg_quantity_per_sale,
    first_sale_date, last_sale_date, days_since_last_sale, unique_customers,
    current_stock_level, current_stock_value, current_stock_status,
    current_is_low_stock, turnover_ratio, product_performance_tier,
    etl_batch_id, etl_timestamp
) VALUES (
    :product_id, :total_sales_count, :total_quantity_sold, :total_revenue,
    :avg_sale_price, :max_sale_price, :min_sale_price, :avg_quantity_per_sale,
    :first_sale_date, :last_sale_date, :days_since_last_sale, :unique_customers,
    :current_stock_level, :current_stock_value, :current_stock_status,
    :current_is_low_stock, :turnover_ratio, :product_performance_tier,
    :etl_batch_id, :etl_timestamp
)
ON CONFLICT (product_id) DO UPDATE SET
    total_sales_count = VALUES(total_sales_count),
    total_quantity_sold = VALUES(total_quantity_sold),
    total_revenue = VALUES(total_revenue),
    avg_sale_price = VALUES(avg_sale_price),
    max_sale_price = VALUES(max_sale_price),
    min_sale_price = VALUES(min_sale_price),
    avg_quantity_per_sale = VALUES(avg_quantity_per_sale),
    last_sale_date = VALUES(last_sale_date),
    days_since_last_sale = VALUES(days_since_last_sale),
    unique_customers = VALUES(unique_customers),
    current_stock_level = VALUES(current_stock_level),
    current_stock_value = VALUES(current_stock_value),
    current_stock_status = VALUES(current_stock_status),
    current_is_low_stock = VALUES(current_is_low_stock),
    turnover_ratio = VALUES(turnover_ratio),
    product_performance_tier = VALUES(product_performance_tier),
    etl_batch_id = VALUES(etl_batch_id),
    etl_timestamp = VALUES(etl_timestamp);
```

---

### 3. Sales Summary ETL Process

#### Daily Sales Summary
```sql
-- Extract daily sales data
SELECT 
    DATE(sale_date) as sale_date,
    COUNT(*) as total_transactions,
    SUM(quantity_sold) as total_quantity_sold,
    SUM(total_amount) as total_revenue,
    AVG(total_amount) as avg_transaction_value,
    MAX(total_amount) as max_transaction_value,
    MIN(total_amount) as min_transaction_value,
    COUNT(DISTINCT customer_id) as unique_customers,
    COUNT(DISTINCT product_id) as unique_products,
    SUM(total_amount) / COUNT(DISTINCT customer_id) as revenue_per_customer,
    SUM(total_amount) / COUNT(DISTINCT product_id) as revenue_per_product
FROM dwd_transaction_detail
WHERE sale_date >= :last_etl_timestamp
GROUP BY DATE(sale_date);
```

#### Monthly Sales Summary
```sql
-- Extract monthly sales data
SELECT 
    YEAR(sale_date) as sale_year,
    MONTH(sale_date) as sale_month,
    QUARTER(sale_date) as sale_quarter,
    COUNT(*) as total_transactions,
    SUM(quantity_sold) as total_quantity_sold,
    SUM(total_amount) as total_revenue,
    AVG(total_amount) as avg_transaction_value,
    COUNT(DISTINCT customer_id) as unique_customers,
    COUNT(DISTINCT product_id) as unique_products
FROM dwd_transaction_detail
WHERE sale_date >= :last_etl_timestamp
GROUP BY YEAR(sale_date), MONTH(sale_date), QUARTER(sale_date);
```

---

## Error Handling and Recovery

### 1. Error Handling Framework
```python
class ETLErrorHandler:
    def __init__(self):
        self.error_log = []
        self.retry_count = 0
        self.max_retries = 3
        
    def handle_error(self, error, context):
        """Handle ETL errors with appropriate recovery strategies"""
        error_record = {
            'timestamp': datetime.now(),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context,
            'retry_count': self.retry_count
        }
        
        self.error_log.append(error_record)
        
        # Determine recovery strategy
        if isinstance(error, DataQualityError):
            return self.handle_data_quality_error(error, context)
        elif isinstance(error, ConnectionError):
            return self.handle_connection_error(error, context)
        elif isinstance(error, ValidationError):
            return self.handle_validation_error(error, context)
        else:
            return self.handle_generic_error(error, context)
    
    def handle_data_quality_error(self, error, context):
        """Handle data quality errors"""
        # Log error and continue with next record
        self.log_error(error, context)
        return 'CONTINUE'
    
    def handle_connection_error(self, error, context):
        """Handle connection errors with retry"""
        if self.retry_count < self.max_retries:
            self.retry_count += 1
            time.sleep(2 ** self.retry_count)  # Exponential backoff
            return 'RETRY'
        else:
            self.log_error(error, context)
            return 'FAIL'
    
    def handle_validation_error(self, error, context):
        """Handle validation errors"""
        # Attempt to fix data and retry
        fixed_data = self.attempt_data_fix(context)
        if fixed_data:
            return 'RETRY_WITH_FIXED_DATA'
        else:
            self.log_error(error, context)
            return 'FAIL'
    
    def handle_generic_error(self, error, context):
        """Handle generic errors"""
        self.log_error(error, context)
        return 'FAIL'
```

### 2. Data Quality Validation
```python
class DataQualityValidator:
    def __init__(self):
        self.validation_rules = self.load_validation_rules()
    
    def validate_transaction_data(self, record):
        """Validate transaction data quality"""
        errors = []
        
        # Required field validation
        if not record.get('sale_id'):
            errors.append('Missing sale_id')
        if not record.get('product_id'):
            errors.append('Missing product_id')
        if not record.get('total_amount'):
            errors.append('Missing total_amount')
        
        # Data type validation
        if not isinstance(record.get('quantity_sold'), int):
            errors.append('Invalid quantity_sold type')
        if not isinstance(record.get('price_per_unit'), (int, float)):
            errors.append('Invalid price_per_unit type')
        
        # Business rule validation
        if record.get('quantity_sold', 0) <= 0:
            errors.append('Invalid quantity_sold value')
        if record.get('price_per_unit', 0) <= 0:
            errors.append('Invalid price_per_unit value')
        
        # Calculation validation
        calculated_total = record.get('quantity_sold', 0) * record.get('price_per_unit', 0)
        if abs(calculated_total - record.get('total_amount', 0)) > 0.01:
            errors.append('Total amount calculation mismatch')
        
        return errors
    
    def validate_inventory_data(self, record):
        """Validate inventory data quality"""
        errors = []
        
        # Required field validation
        if not record.get('product_id'):
            errors.append('Missing product_id')
        if record.get('stock_level') is None:
            errors.append('Missing stock_level')
        
        # Business rule validation
        if record.get('stock_level', 0) < 0:
            errors.append('Invalid stock_level value')
        
        return errors
```

---

## Performance Optimization

### 1. Wide Table Performance Benefits
- **Reduced JOINs**: Single table queries eliminate complex JOINs
- **Better Caching**: Improved data locality in wide tables
- **Parallel Processing**: Optimized for distributed computing
- **Index Efficiency**: Simplified indexing strategies

### 2. ETL Performance Optimization
```python
class ETLPerformanceOptimizer:
    def __init__(self):
        self.batch_size = 10000
        self.parallel_workers = 4
        
    def optimize_extract_phase(self, query, params):
        """Optimize data extraction"""
        # Use batch processing for large datasets
        # Implement parallel extraction for multiple tables
        # Use appropriate indexes for faster queries
        
        return optimized_query
    
    def optimize_transform_phase(self, data):
        """Optimize data transformation"""
        # Use vectorized operations
        # Implement parallel processing
        # Cache frequently used calculations
        
        return optimized_data
    
    def optimize_load_phase(self, data, target_table):
        """Optimize data loading"""
        # Use bulk insert operations
        # Implement parallel loading
        # Use appropriate loading strategies (UPSERT, MERGE)
        
        return optimized_load_operation
```

### 3. Monitoring and Alerting
```python
class ETLMonitor:
    def __init__(self):
        self.metrics = {}
        self.alerts = []
    
    def track_etl_performance(self, job_name, start_time, end_time, record_count):
        """Track ETL job performance"""
        duration = end_time - start_time
        throughput = record_count / duration.total_seconds() if duration.total_seconds() > 0 else 0
        
        self.metrics[job_name] = {
            'duration': duration,
            'record_count': record_count,
            'throughput': throughput,
            'timestamp': datetime.now()
        }
        
        # Check for performance issues
        if duration.total_seconds() > 3600:  # 1 hour threshold
            self.alerts.append({
                'type': 'PERFORMANCE',
                'message': f'ETL job {job_name} took {duration} to complete',
                'severity': 'HIGH'
            })
    
    def track_data_quality(self, table_name, quality_score):
        """Track data quality metrics"""
        if quality_score < 90:
            self.alerts.append({
                'type': 'QUALITY',
                'message': f'Data quality score for {table_name} is {quality_score}%',
                'severity': 'MEDIUM'
            })
```

---

## Summary

This ETL processing logic is specifically optimized for the wide table architecture, providing:

### Key Features
- **Wide Table Optimization**: Processes multiple source tables into optimized wide tables
- **Foreign Key Strategy**: Maintains referential integrity without redundant data
- **Performance Benefits**: Leverages wide table advantages for better ETL performance
- **Quality Assurance**: Comprehensive data validation and error handling
- **Monitoring**: Real-time performance and quality monitoring

### Wide Table ETL Benefits
- **Simplified Processing**: Fewer target tables to process
- **Better Performance**: Optimized for wide table structure
- **Reduced Complexity**: Simpler ETL logic and maintenance
- **Enhanced Quality**: Focused quality checks on wide table data

This ETL framework ensures efficient data processing while maintaining high data quality standards in the wide table architecture.