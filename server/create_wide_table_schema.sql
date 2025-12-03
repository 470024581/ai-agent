-- Wide Table Architecture Table Creation Scripts

-- DIM Layer (Dimension Layer) Tables

-- Customer Dimension Table
CREATE TABLE IF NOT EXISTS dim_customer (
    customer_id TEXT PRIMARY KEY,
    customer_name TEXT NOT NULL,
    contact_person TEXT,
    email TEXT,
    phone TEXT,
    address TEXT,
    customer_type TEXT,
    region TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    days_since_update INTEGER,
    is_active_customer BOOLEAN,
    etl_batch_id TEXT,
    etl_timestamp TIMESTAMP
);

-- Product Dimension Table
CREATE TABLE IF NOT EXISTS dim_product (
    product_id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    category TEXT,
    unit_price DECIMAL(12,2),
    price_range TEXT,
    etl_batch_id TEXT,
    etl_timestamp TIMESTAMP
);

-- DWD Layer (Data Warehouse Detail Layer) Tables

-- Sales Detail Wide Table
CREATE TABLE IF NOT EXISTS dwd_sales_detail (
    sale_id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    customer_id TEXT,
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

-- Inventory Detail Wide Table
CREATE TABLE IF NOT EXISTS dwd_inventory_detail (
    product_id TEXT PRIMARY KEY,
    stock_level INTEGER NOT NULL,
    last_updated TIMESTAMP NOT NULL,
    stock_status TEXT,
    days_since_update INTEGER,
    is_stale_data BOOLEAN,
    stock_value DECIMAL(15,2),
    reorder_point INTEGER,
    is_low_stock BOOLEAN,
    turnover_ratio DECIMAL(10,4),
    data_quality_score INTEGER,
    etl_batch_id TEXT,
    etl_timestamp TIMESTAMP
);

-- DWS Layer (Data Warehouse Summary Layer) Tables

-- Sales Data Cube
CREATE TABLE IF NOT EXISTS dws_sales_cube (
    sale_date DATE,
    product_id TEXT,
    customer_id TEXT,
    category TEXT,
    price_range TEXT,
    sale_value_range TEXT,
    transaction_count INTEGER,
    total_quantity_sold INTEGER,
    total_revenue DECIMAL(15,2),
    avg_transaction_value DECIMAL(15,2),
    unique_products INTEGER,
    unique_customers INTEGER,
    etl_batch_id TEXT,
    etl_timestamp TIMESTAMP,
    PRIMARY KEY (sale_date, product_id, customer_id)
);

-- Inventory Data Cube
CREATE TABLE IF NOT EXISTS dws_inventory_cube (
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
    etl_batch_id TEXT,
    etl_timestamp TIMESTAMP,
    PRIMARY KEY (last_updated_date, product_id)
);

-- Create indexes for query performance optimization

-- DWD Layer Indexes
CREATE INDEX IF NOT EXISTS idx_sales_customer_date 
ON dwd_sales_detail (customer_id, sale_date);

CREATE INDEX IF NOT EXISTS idx_sales_product_date 
ON dwd_sales_detail (product_id, sale_date);

CREATE INDEX IF NOT EXISTS idx_inventory_product_status 
ON dwd_inventory_detail (product_id, stock_status);

-- DWS Layer Indexes
CREATE INDEX IF NOT EXISTS idx_sales_cube_date_category 
ON dws_sales_cube (sale_date, category);

CREATE INDEX IF NOT EXISTS idx_sales_cube_product_date 
ON dws_sales_cube (product_id, sale_date);

CREATE INDEX IF NOT EXISTS idx_sales_cube_customer_date 
ON dws_sales_cube (customer_id, sale_date);

CREATE INDEX IF NOT EXISTS idx_sales_cube_customer_type 
ON dws_sales_cube (customer_id, sale_date, category);

CREATE INDEX IF NOT EXISTS idx_inventory_cube_date_category 
ON dws_inventory_cube (last_updated_date, category);

-- Create views for easier querying

-- Sales Analysis View
CREATE VIEW IF NOT EXISTS v_sales_analysis AS
SELECT 
    s.sale_date,
    s.customer_id,
    c.customer_name,
    c.customer_type,
    c.region,
    s.product_id,
    p.product_name,
    p.category,
    p.price_range,
    s.quantity_sold,
    s.price_per_unit,
    s.total_amount,
    s.sale_value_range,
    s.data_quality_score
FROM dwd_sales_detail s
LEFT JOIN dim_customer c ON s.customer_id = c.customer_id
LEFT JOIN dim_product p ON s.product_id = p.product_id;

-- Inventory Analysis View
CREATE VIEW IF NOT EXISTS v_inventory_analysis AS
SELECT 
    i.product_id,
    p.product_name,
    p.category,
    p.price_range,
    i.stock_level,
    i.stock_status,
    i.stock_value,
    i.is_low_stock,
    i.is_stale_data,
    i.turnover_ratio,
    i.data_quality_score,
    i.last_updated
FROM dwd_inventory_detail i
LEFT JOIN dim_product p ON i.product_id = p.product_id;

-- Sales Cube Summary View
CREATE VIEW IF NOT EXISTS v_sales_cube_summary AS
SELECT 
    sale_date,
    customer_id,
    category,
    SUM(transaction_count) as total_transactions,
    SUM(total_revenue) as total_revenue,
    SUM(total_quantity_sold) as total_quantity_sold,
    AVG(avg_transaction_value) as avg_transaction_value,
    SUM(unique_customers) as unique_customers,
    SUM(unique_products) as unique_products
FROM dws_sales_cube
GROUP BY sale_date, customer_id, category;

-- Inventory Cube Summary View
CREATE VIEW IF NOT EXISTS v_inventory_cube_summary AS
SELECT 
    last_updated_date,
    category,
    price_range,
    stock_status,
    SUM(product_count) as total_products,
    SUM(total_stock_level) as total_stock_level,
    SUM(total_stock_value) as total_stock_value,
    AVG(avg_stock_level) as avg_stock_level,
    AVG(avg_stock_value) as avg_stock_value,
    AVG(avg_turnover_ratio) as avg_turnover_ratio
FROM dws_inventory_cube
GROUP BY last_updated_date, category, price_range, stock_status;
