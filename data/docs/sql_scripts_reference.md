# SQL Scripts Reference

This document contains SQL scripts referenced in the wide table design solution.

## Table Creation Scripts

### DWD Layer Tables

#### dwd_sales_detail
```sql
-- Sales Wide Table
CREATE TABLE dwd_sales_detail (
    sale_id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,  -- Foreign key
    customer_id TEXT NULL,     -- Foreign key
    quantity_sold INTEGER NOT NULL,
    price_per_unit DECIMAL(12,2) NOT NULL,
    total_amount DECIMAL(15,2) NOT NULL,
    sale_date DATE NOT NULL,
    calculated_total DECIMAL(15,2) NOT NULL,
    sale_value_range TEXT,
    data_quality_score INTEGER,
    etl_batch_id TEXT,
    etl_timestamp TIMESTAMP
);
```

#### dwd_inventory_detail
```sql
-- Inventory Wide Table
CREATE TABLE dwd_inventory_detail (
    product_id TEXT PRIMARY KEY,
    stock_level INTEGER NOT NULL,
    last_updated TIMESTAMP NOT NULL,
    stock_status TEXT,
    days_since_update INTEGER,
    is_stale_data BOOLEAN,
    stock_value DECIMAL(15,2),
    reorder_point INTEGER,
    is_low_stock BOOLEAN,
    data_quality_score INTEGER,
    etl_batch_id TEXT,
    etl_timestamp TIMESTAMP
);
```

### DWS Layer Tables (Data Cubes)

#### dws_sales_cube
```sql
-- Sales Data Cube
CREATE TABLE dws_sales_cube (
    sale_date DATE,
    product_id TEXT,
    customer_id TEXT,
    category TEXT,
    price_range TEXT,
    customer_type TEXT,
    region TEXT,
    sale_value_range TEXT,
    transaction_count INTEGER,
    total_quantity_sold INTEGER,
    total_revenue DECIMAL(15,2),
    avg_transaction_value DECIMAL(15,2),
    unique_customers INTEGER,
    unique_products INTEGER,
    PRIMARY KEY (sale_date, product_id, customer_id)
);
```

#### dws_inventory_cube
```sql
-- Inventory Data Cube
CREATE TABLE dws_inventory_cube (
    last_updated_date DATE,
    product_id TEXT,
    category TEXT,
    price_range TEXT,
    stock_status TEXT,
    is_low_stock BOOLEAN,
    is_stale_data BOOLEAN,
    product_count INTEGER,
    total_stock_level INTEGER,
    total_stock_value DECIMAL(15,2),
    avg_stock_level DECIMAL(10,2),
    avg_stock_value DECIMAL(15,2),
    avg_turnover_ratio DECIMAL(10,4),
    PRIMARY KEY (last_updated_date, product_id)
);
```

## Index Creation Scripts

### DWD Layer Indexes
```sql
-- Composite index optimization for DWD tables
CREATE INDEX idx_sales_customer_date 
ON dwd_sales_detail (customer_id, sale_date);

CREATE INDEX idx_sales_product_date 
ON dwd_sales_detail (product_id, sale_date);

CREATE INDEX idx_inventory_product_status 
ON dwd_inventory_detail (product_id, stock_status);
```

### DWS Layer Indexes
```sql
-- Index optimization for data cubes
CREATE INDEX idx_sales_cube_date_category 
ON dws_sales_cube (sale_date, category);

CREATE INDEX idx_sales_cube_product_date 
ON dws_sales_cube (product_id, sale_date);

CREATE INDEX idx_inventory_cube_date_category 
ON dws_inventory_cube (last_updated_date, category);
```

## Partition Scripts

### DWD Layer Partitions
```sql
-- Partition by time for DWD tables
CREATE TABLE dwd_sales_detail (
    -- Field definitions
) PARTITIONED BY (
    sale_year INTEGER,
    sale_month INTEGER
);

-- Partition by product category for inventory
CREATE TABLE dwd_inventory_detail (
    -- Field definitions
) PARTITIONED BY (
    product_category VARCHAR(100)
);
```

### DWS Layer Partitions
```sql
-- Partition data cubes by date for optimal performance
CREATE TABLE dws_sales_cube (
    -- Field definitions
) PARTITIONED BY (
    sale_date DATE
);

CREATE TABLE dws_inventory_cube (
    -- Field definitions
) PARTITIONED BY (
    last_updated_date DATE
);
```

## Query Examples

### Customer Analysis Queries
```sql
-- Customer purchase behavior analysis (DWD layer)
SELECT 
    customer_id,
    COUNT(*) as purchase_frequency,
    SUM(total_amount) as total_spent,
    AVG(total_amount) as avg_purchase_value,
    COUNT(DISTINCT product_id) as product_diversity,
    MAX(sale_date) as last_purchase_date
FROM dwd_sales_detail
WHERE sale_date >= '2024-01-01'
GROUP BY customer_id
ORDER BY total_spent DESC;

-- Instant customer analytics with data cube
SELECT 
    customer_id,
    customer_type,
    region,
    SUM(transaction_count) as total_transactions,
    SUM(total_revenue) as total_spent,
    AVG(avg_transaction_value) as avg_purchase_value
FROM dws_sales_cube
WHERE sale_date >= '2024-01-01'
GROUP BY customer_id, customer_type, region
ORDER BY total_spent DESC;
```

### Product Analysis Queries
```sql
-- Product sales performance analysis (DWD layer)
SELECT 
    product_id,
    COUNT(*) as sales_count,
    SUM(quantity_sold) as total_quantity,
    SUM(total_amount) as total_revenue,
    AVG(price_per_unit) as avg_price,
    COUNT(DISTINCT customer_id) as unique_customers,
    MAX(sale_date) as last_sale_date
FROM dwd_sales_detail
WHERE sale_date >= '2024-01-01'
GROUP BY product_id
ORDER BY total_revenue DESC;

-- Instant product analytics with data cube
SELECT 
    product_id,
    category,
    price_range,
    SUM(transaction_count) as sales_count,
    SUM(total_quantity_sold) as total_quantity,
    SUM(total_revenue) as total_revenue,
    AVG(avg_transaction_value) as avg_price,
    SUM(unique_customers) as unique_customers
FROM dws_sales_cube
WHERE sale_date >= '2024-01-01'
GROUP BY product_id, category, price_range
ORDER BY total_revenue DESC;
```

### Sales Analysis Queries
```sql
-- Daily sales trend analysis (DWD layer)
SELECT 
    sale_date,
    COUNT(*) as daily_transactions,
    SUM(total_amount) as daily_revenue,
    AVG(total_amount) as avg_transaction_value,
    COUNT(DISTINCT customer_id) as unique_customers,
    COUNT(DISTINCT product_id) as unique_products
FROM dwd_sales_detail
WHERE sale_date >= '2024-01-01'
GROUP BY sale_date
ORDER BY sale_date;

-- Instant sales trend with data cube
SELECT 
    sale_date,
    SUM(transaction_count) as daily_transactions,
    SUM(total_revenue) as daily_revenue,
    AVG(avg_transaction_value) as avg_transaction_value,
    SUM(unique_customers) as unique_customers,
    SUM(unique_products) as unique_products
FROM dws_sales_cube
WHERE sale_date >= '2024-01-01'
GROUP BY sale_date
ORDER BY sale_date;
```

### Display-time Association Queries
```sql
-- Associate dimension information at query time
SELECT 
    t.sale_id,
    t.product_id,
    p.product_name,  -- Display-time association
    t.customer_id,
    c.customer_name, -- Display-time association
    t.total_amount
FROM dwd_sales_detail t
LEFT JOIN dim_product p ON t.product_id = p.product_id
LEFT JOIN dim_customer c ON t.customer_id = c.customer_id
WHERE t.sale_date >= '2024-01-01';

-- Use data cube for instant analytics
SELECT 
    sale_date,
    category,
    total_revenue,
    unique_customers,
    avg_transaction_value
FROM dws_sales_cube
WHERE sale_date >= '2024-01-01'
ORDER BY total_revenue DESC;
```

## Data Quality Check Queries

### Completeness Checks
```sql
-- Check for missing sale_id
SELECT COUNT(*) as missing_sale_id_count
FROM dwd_sales_detail 
WHERE sale_id IS NULL OR sale_id = '';

-- Check for missing product_id
SELECT COUNT(*) as missing_product_id_count
FROM dwd_sales_detail 
WHERE product_id IS NULL OR product_id = '';

-- Check for missing total_amount
SELECT COUNT(*) as missing_total_amount_count
FROM dwd_sales_detail 
WHERE total_amount IS NULL;
```

### Consistency Checks
```sql
-- Check calculation consistency
SELECT COUNT(*) as calculation_mismatch_count
FROM dwd_sales_detail 
WHERE ABS(calculated_total - total_amount) > 0.01;

-- Check for negative quantities
SELECT COUNT(*) as negative_quantity_count
FROM dwd_sales_detail 
WHERE quantity_sold <= 0;

-- Check for negative prices
SELECT COUNT(*) as negative_price_count
FROM dwd_sales_detail 
WHERE price_per_unit <= 0;
```

### Time Validity Checks
```sql
-- Check for future sale dates
SELECT COUNT(*) as future_sale_date_count
FROM dwd_sales_detail 
WHERE sale_date > CURRENT_DATE;

-- Check for stale inventory data
SELECT COUNT(*) as stale_inventory_count
FROM dwd_inventory_detail 
WHERE is_stale_data = TRUE;
```

## Performance Monitoring Queries

### Slow Query Detection
```sql
-- Find queries taking longer than 5 seconds
SELECT 
    query_text,
    execution_time,
    timestamp
FROM query_log 
WHERE execution_time > 5000
ORDER BY execution_time DESC;
```

### Cache Hit Rate Monitoring
```sql
-- Monitor cache performance
SELECT 
    cache_name,
    hit_count,
    miss_count,
    hit_rate
FROM cache_statistics
ORDER BY hit_rate DESC;
```

### Index Usage Statistics
```sql
-- Monitor index usage
SELECT 
    table_name,
    index_name,
    usage_count,
    last_used
FROM index_usage_stats
ORDER BY usage_count DESC;
```

### Data Cube Performance Monitoring
```sql
-- Monitor data cube query performance
SELECT 
    cube_name,
    avg_query_time,
    query_count,
    last_refresh_time
FROM cube_performance_stats
ORDER BY avg_query_time DESC;
```

This SQL scripts reference provides all the necessary SQL code for implementing the wide table design solution, including table creation, indexing, partitioning, and monitoring queries.
