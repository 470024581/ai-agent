# DWS Layer (Data Warehouse Summary) Schema Design - Data Cube Approach

## Overview
The DWS layer adopts a **data cube design** optimized for analytical queries, featuring 2 core cube tables that directly correspond to the DWD wide tables. This design performs light aggregation of cross-dimensional metrics without further splitting, ensuring flexibility for the application layer while avoiding dimension explosion.

## Design Philosophy

### Core Principles
- **Data Cube Design**: Pre-calculate cross-dimensional aggregations
- **Avoid Dimension Explosion**: Only core business dimensions, time dimensions calculated at application layer
- **Light Aggregation**: Focus on essential metrics without complex derivations
- **Application Layer Flexibility**: Support dynamic time dimension calculations
- **Permanent Storage**: Business data is permanently stored without retention periods

### Why This Design?

#### 1. **Performance Optimization**
- **Pre-calculated Aggregations**: Reduce computation overhead for common analytical queries
- **Fast BI Queries**: Optimized for business intelligence tools and dashboards
- **Reduced JOINs**: Minimize complex joins in analytical queries
- **Better Caching**: Cohesive datasets improve cache hit rates

#### 2. **Avoid Dimension Explosion**
- **Core Dimensions Only**: Focus on essential business dimensions
- **Dynamic Time Calculation**: Year/month/quarter calculated at application layer
- **Storage Efficiency**: Reduce cube storage requirements
- **Maintenance Simplicity**: Fewer dimension combinations to maintain

#### 3. **Application Layer Flexibility**
- **Dynamic Time Granularity**: Support any time dimension calculation
- **Custom Aggregations**: Allow application-specific metric calculations
- **Query Flexibility**: Enable various analytical patterns
- **Future-Proof**: Accommodate new analytical requirements

---

## DWS Table Structure

### Core Cube Tables

#### Table: dws_sales_cube
**Purpose**: Sales data cube with core dimension aggregations
**Source**: dwd_sales_detail
**Update Frequency**: Daily
**Design Rationale**: Single source for all sales-related analytical queries

##### Structure
| Column | Type | Constraints | Description | Calculation Logic |
|--------|------|-------------|-------------|-------------------|
| sale_date | DATE | PRIMARY KEY | Sale date (only date dimension) | dwd_sales_detail.sale_date |
| customer_id | TEXT | PRIMARY KEY | Customer foreign key | dwd_sales_detail.customer_id |
| customer_type | VARCHAR(20) | PRIMARY KEY | Customer type | Derived from dim_customer |
| region | VARCHAR(50) | PRIMARY KEY | Geographic region | Derived from dim_customer |
| product_id | TEXT | PRIMARY KEY | Product foreign key | dwd_sales_detail.product_id |
| category | VARCHAR(100) | PRIMARY KEY | Product category | Derived from dim_product |
| price_range | VARCHAR(20) | PRIMARY KEY | Price range | Derived from dim_product |
| sale_value_range | VARCHAR(20) | PRIMARY KEY | Sale value range | dwd_sales_detail.sale_value_range |
| transaction_count | INTEGER | NOT NULL | Number of transactions | COUNT(*) |
| total_revenue | DECIMAL(15,2) | NOT NULL | Total revenue | SUM(total_amount) |
| total_quantity | INTEGER | NOT NULL | Total quantity sold | SUM(quantity_sold) |
| avg_transaction_value | DECIMAL(12,2) | NOT NULL | Average transaction value | AVG(total_amount) |
| max_transaction_value | DECIMAL(12,2) | NOT NULL | Maximum transaction value | MAX(total_amount) |
| min_transaction_value | DECIMAL(12,2) | NOT NULL | Minimum transaction value | MIN(total_amount) |
| etl_batch_id | VARCHAR(50) | NOT NULL | ETL batch ID | Generated |
| etl_timestamp | DATETIME | NOT NULL | ETL timestamp | CURRENT_TIMESTAMP |

##### Business Rules
- Sale value ranges: Low (<100), Medium (100-500), High (500-1000), Premium (>1000)
- Price ranges: Low (<50), Medium (50-200), High (200-1000), Premium (>1000)
- Customer types: Individual, Corporate, VIP
- Regions: North, South, East, West, Central

##### Analytics Capabilities
- **Sales Analysis**: Revenue and quantity analysis by all dimensions
- **Customer Analysis**: Customer behavior and segmentation
- **Product Analysis**: Product performance across categories
- **Geographic Analysis**: Regional sales performance
- **Value Analysis**: Transaction value distribution analysis

---

#### Table: dws_inventory_cube
**Purpose**: Inventory data cube with core dimension aggregations
**Source**: dwd_inventory_detail
**Update Frequency**: Daily
**Design Rationale**: Single source for all inventory-related analytical queries

##### Structure
| Column | Type | Constraints | Description | Calculation Logic |
|--------|------|-------------|-------------|-------------------|
| last_updated_date | DATE | PRIMARY KEY | Last update date (only date dimension) | dwd_inventory_detail.last_updated |
| product_id | TEXT | PRIMARY KEY | Product foreign key | dwd_inventory_detail.product_id |
| category | VARCHAR(100) | PRIMARY KEY | Product category | Derived from dim_product |
| price_range | VARCHAR(20) | PRIMARY KEY | Price range | Derived from dim_product |
| stock_status | VARCHAR(20) | PRIMARY KEY | Stock status | dwd_inventory_detail.stock_status |
| is_low_stock | BOOLEAN | PRIMARY KEY | Low stock flag | dwd_inventory_detail.is_low_stock |
| is_stale_data | BOOLEAN | PRIMARY KEY | Stale data flag | dwd_inventory_detail.is_stale_data |
| product_count | INTEGER | NOT NULL | Number of products | COUNT(*) |
| total_stock_level | INTEGER | NOT NULL | Total stock level | SUM(stock_level) |
| total_stock_value | DECIMAL(15,2) | NOT NULL | Total stock value | SUM(stock_value) |
| avg_stock_level | DECIMAL(8,2) | NOT NULL | Average stock level | AVG(stock_level) |
| avg_stock_value | DECIMAL(12,2) | NOT NULL | Average stock value | AVG(stock_value) |
| avg_turnover_ratio | DECIMAL(8,4) | NOT NULL | Average turnover ratio | AVG(turnover_ratio) |
| etl_batch_id | VARCHAR(50) | NOT NULL | ETL batch ID | Generated |
| etl_timestamp | DATETIME | NOT NULL | ETL timestamp | CURRENT_TIMESTAMP |

##### Business Rules
- Stock status: In Stock (>10), Low Stock (1-10), Out of Stock (0)
- Price ranges: Low (<50), Medium (50-200), High (200-1000), Premium (>1000)
- Low stock: Stock level below reorder point
- Stale data: Data not updated for more than 7 days

##### Analytics Capabilities
- **Inventory Management**: Stock level monitoring and optimization
- **Supply Chain**: Reorder point and turnover analysis
- **Financial**: Stock value analysis and valuation
- **Operational**: Low stock alerts and stale data monitoring

---

## Application Layer Time Dimension Calculation

### Dynamic Time Aggregation Examples

#### Monthly Sales Analysis
```sql
-- Application layer: Monthly sales aggregation
SELECT 
    YEAR(sale_date) as sale_year,
    MONTH(sale_date) as sale_month,
    customer_type,
    category,
    SUM(total_revenue) as monthly_revenue,
    SUM(total_quantity) as monthly_quantity,
    SUM(transaction_count) as monthly_transactions,
    AVG(avg_transaction_value) as monthly_avg_transaction_value
FROM dws_sales_cube
WHERE sale_date >= '2024-01-01' AND sale_date < '2025-01-01'
GROUP BY YEAR(sale_date), MONTH(sale_date), customer_type, category
ORDER BY sale_year, sale_month, monthly_revenue DESC;
```

#### Quarterly Performance Analysis
```sql
-- Application layer: Quarterly performance analysis
SELECT 
    YEAR(sale_date) as sale_year,
    QUARTER(sale_date) as sale_quarter,
    region,
    SUM(total_revenue) as quarterly_revenue,
    SUM(transaction_count) as quarterly_transactions,
    COUNT(DISTINCT customer_id) as unique_customers,
    COUNT(DISTINCT product_id) as unique_products
FROM dws_sales_cube
WHERE sale_date >= '2024-01-01'
GROUP BY YEAR(sale_date), QUARTER(sale_date), region
ORDER BY sale_year, sale_quarter, quarterly_revenue DESC;
```

#### Weekly Inventory Analysis
```sql
-- Application layer: Weekly inventory analysis
SELECT 
    YEAR(last_updated_date) as update_year,
    WEEK(last_updated_date) as update_week,
    category,
    stock_status,
    SUM(total_stock_value) as weekly_stock_value,
    AVG(avg_turnover_ratio) as weekly_avg_turnover,
    COUNT(*) as product_count
FROM dws_inventory_cube
WHERE last_updated_date >= '2024-01-01'
GROUP BY YEAR(last_updated_date), WEEK(last_updated_date), category, stock_status
ORDER BY update_year, update_week, weekly_stock_value DESC;
```

#### Year-over-Year Growth Analysis
```sql
-- Application layer: Year-over-year growth analysis
WITH current_year AS (
    SELECT 
        customer_type,
        SUM(total_revenue) as current_revenue,
        SUM(transaction_count) as current_transactions
    FROM dws_sales_cube
    WHERE YEAR(sale_date) = 2024
    GROUP BY customer_type
),
previous_year AS (
    SELECT 
        customer_type,
        SUM(total_revenue) as previous_revenue,
        SUM(transaction_count) as previous_transactions
    FROM dws_sales_cube
    WHERE YEAR(sale_date) = 2023
    GROUP BY customer_type
)
SELECT 
    c.customer_type,
    c.current_revenue,
    p.previous_revenue,
    ((c.current_revenue - p.previous_revenue) / p.previous_revenue * 100) as revenue_growth_pct,
    c.current_transactions,
    p.previous_transactions,
    ((c.current_transactions - p.previous_transactions) / p.previous_transactions * 100) as transaction_growth_pct
FROM current_year c
LEFT JOIN previous_year p ON c.customer_type = p.customer_type
ORDER BY revenue_growth_pct DESC;
```

---

## ETL Processing Logic

### Sales Cube ETL
```python
def process_sales_cube():
    # Extract sales data from DWD
    sales_data = extract_sales_detail_data()
    
    # Get dimension data for enrichment
    customer_dim = extract_customer_dimension()
    product_dim = extract_product_dimension()
    
    # Group by core dimensions
    cube_data = {}
    for sale in sales_data:
        # Get dimension attributes
        customer_info = customer_dim.get(sale.customer_id, {})
        product_info = product_dim.get(sale.product_id, {})
        
        # Create cube key
        cube_key = (
            sale.sale_date.date(),
            sale.customer_id,
            customer_info.get('customer_type', 'Unknown'),
            customer_info.get('region', 'Unknown'),
            sale.product_id,
            product_info.get('category', 'Unknown'),
            product_info.get('price_range', 'Unknown'),
            sale.sale_value_range
        )
        
        if cube_key not in cube_data:
            cube_data[cube_key] = {
                'sale_date': sale.sale_date.date(),
                'customer_id': sale.customer_id,
                'customer_type': customer_info.get('customer_type', 'Unknown'),
                'region': customer_info.get('region', 'Unknown'),
                'product_id': sale.product_id,
                'category': product_info.get('category', 'Unknown'),
                'price_range': product_info.get('price_range', 'Unknown'),
                'sale_value_range': sale.sale_value_range,
                'transaction_count': 0,
                'total_revenue': 0,
                'total_quantity': 0,
                'transaction_values': []
            }
        
        # Aggregate metrics
        cube_data[cube_key]['transaction_count'] += 1
        cube_data[cube_key]['total_revenue'] += sale.total_amount
        cube_data[cube_key]['total_quantity'] += sale.quantity_sold
        cube_data[cube_key]['transaction_values'].append(sale.total_amount)
    
    # Calculate derived metrics and load
    for cube_key, data in cube_data.items():
        cube_record = {
            'sale_date': data['sale_date'],
            'customer_id': data['customer_id'],
            'customer_type': data['customer_type'],
            'region': data['region'],
            'product_id': data['product_id'],
            'category': data['category'],
            'price_range': data['price_range'],
            'sale_value_range': data['sale_value_range'],
            'transaction_count': data['transaction_count'],
            'total_revenue': data['total_revenue'],
            'total_quantity': data['total_quantity'],
            'avg_transaction_value': data['total_revenue'] / data['transaction_count'],
            'max_transaction_value': max(data['transaction_values']),
            'min_transaction_value': min(data['transaction_values']),
            'etl_batch_id': get_current_batch_id(),
            'etl_timestamp': datetime.now()
        }
        
        # Load to DWS
        load_sales_cube(cube_record)
```

### Inventory Cube ETL
```python
def process_inventory_cube():
    # Extract inventory data from DWD
    inventory_data = extract_inventory_detail_data()
    
    # Get product dimension data
    product_dim = extract_product_dimension()
    
    # Group by core dimensions
    cube_data = {}
    for inventory in inventory_data:
        # Get product attributes
        product_info = product_dim.get(inventory.product_id, {})
        
        # Create cube key
        cube_key = (
            inventory.last_updated.date(),
            inventory.product_id,
            product_info.get('category', 'Unknown'),
            product_info.get('price_range', 'Unknown'),
            inventory.stock_status,
            inventory.is_low_stock,
            inventory.is_stale_data
        )
        
        if cube_key not in cube_data:
            cube_data[cube_key] = {
                'last_updated_date': inventory.last_updated.date(),
                'product_id': inventory.product_id,
                'category': product_info.get('category', 'Unknown'),
                'price_range': product_info.get('price_range', 'Unknown'),
                'stock_status': inventory.stock_status,
                'is_low_stock': inventory.is_low_stock,
                'is_stale_data': inventory.is_stale_data,
                'product_count': 0,
                'total_stock_level': 0,
                'total_stock_value': 0,
                'stock_levels': [],
                'stock_values': [],
                'turnover_ratios': []
            }
        
        # Aggregate metrics
        cube_data[cube_key]['product_count'] += 1
        cube_data[cube_key]['total_stock_level'] += inventory.stock_level
        cube_data[cube_key]['total_stock_value'] += inventory.stock_value
        cube_data[cube_key]['stock_levels'].append(inventory.stock_level)
        cube_data[cube_key]['stock_values'].append(inventory.stock_value)
        cube_data[cube_key]['turnover_ratios'].append(inventory.turnover_ratio or 0)
    
    # Calculate derived metrics and load
    for cube_key, data in cube_data.items():
        cube_record = {
            'last_updated_date': data['last_updated_date'],
            'product_id': data['product_id'],
            'category': data['category'],
            'price_range': data['price_range'],
            'stock_status': data['stock_status'],
            'is_low_stock': data['is_low_stock'],
            'is_stale_data': data['is_stale_data'],
            'product_count': data['product_count'],
            'total_stock_level': data['total_stock_level'],
            'total_stock_value': data['total_stock_value'],
            'avg_stock_level': data['total_stock_level'] / data['product_count'],
            'avg_stock_value': data['total_stock_value'] / data['product_count'],
            'avg_turnover_ratio': sum(data['turnover_ratios']) / len(data['turnover_ratios']),
            'etl_batch_id': get_current_batch_id(),
            'etl_timestamp': datetime.now()
        }
        
        # Load to DWS
        load_inventory_cube(cube_record)
```

---

## Query Performance Examples

### Sales Analytics Query
```sql
-- Top performing products by category (using cube)
SELECT 
    category,
    product_id,
    SUM(total_revenue) as total_revenue,
    SUM(total_quantity) as total_quantity,
    SUM(transaction_count) as total_transactions,
    AVG(avg_transaction_value) as avg_transaction_value
FROM dws_sales_cube
WHERE sale_date >= '2024-01-01'
GROUP BY category, product_id
ORDER BY category, total_revenue DESC;

-- Customer segmentation analysis
SELECT 
    customer_type,
    region,
    SUM(total_revenue) as total_revenue,
    SUM(transaction_count) as total_transactions,
    COUNT(DISTINCT customer_id) as unique_customers,
    COUNT(DISTINCT product_id) as unique_products
FROM dws_sales_cube
WHERE sale_date >= '2024-01-01'
GROUP BY customer_type, region
ORDER BY total_revenue DESC;
```

### Inventory Analytics Query
```sql
-- Inventory status by category
SELECT 
    category,
    stock_status,
    SUM(total_stock_value) as total_stock_value,
    SUM(product_count) as product_count,
    AVG(avg_turnover_ratio) as avg_turnover_ratio
FROM dws_inventory_cube
WHERE last_updated_date >= '2024-01-01'
GROUP BY category, stock_status
ORDER BY category, total_stock_value DESC;

-- Low stock analysis
SELECT 
    category,
    price_range,
    SUM(product_count) as low_stock_products,
    SUM(total_stock_value) as low_stock_value,
    AVG(avg_turnover_ratio) as avg_turnover_ratio
FROM dws_inventory_cube
WHERE is_low_stock = true AND last_updated_date >= '2024-01-01'
GROUP BY category, price_range
ORDER BY low_stock_value DESC;
```

---

## Benefits of This DWS Design

### 1. **Performance Benefits**
- **Pre-calculated Aggregations**: Reduce computation overhead for analytical queries
- **Fast BI Queries**: Optimized for business intelligence tools and dashboards
- **Reduced JOINs**: Minimize complex joins in analytical queries
- **Better Caching**: Cohesive datasets improve cache hit rates

### 2. **Avoid Dimension Explosion**
- **Core Dimensions Only**: Focus on essential business dimensions
- **Dynamic Time Calculation**: Year/month/quarter calculated at application layer
- **Storage Efficiency**: Reduce cube storage requirements
- **Maintenance Simplicity**: Fewer dimension combinations to maintain

### 3. **Application Layer Flexibility**
- **Dynamic Time Granularity**: Support any time dimension calculation
- **Custom Aggregations**: Allow application-specific metric calculations
- **Query Flexibility**: Enable various analytical patterns
- **Future-Proof**: Accommodate new analytical requirements

### 4. **Business Benefits**
- **Fast Insights**: Quick access to key performance indicators
- **Comprehensive Analysis**: Support for various analytical patterns
- **Data Consistency**: Standardized metrics across the organization
- **Scalable Architecture**: Design scales with business growth

This optimized DWS design provides high-performance analytical capabilities while avoiding dimension explosion and maintaining flexibility for the application layer.