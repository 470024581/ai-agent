# DWD Layer (Data Warehouse Detail) Schema Design - Optimized Wide Table Approach

## Overview
The DWD layer adopts a **wide table design** optimized for big data analytics, featuring 2 core fact tables. This design prioritizes query performance over storage efficiency, following the "storage for computation" principle common in big data environments.

## Design Philosophy

### Core Principles
- **Wide Table Design**: Minimize JOIN operations for better query performance
- **Foreign Key Strategy**: Maintain referential integrity without redundant dimension data
- **Big Data Optimization**: Optimize for analytical workloads over transactional consistency
- **Permanent Storage**: Business data is permanently stored without retention periods

### Why This Design?

#### 1. **Performance Optimization**
- **Reduced JOINs**: Wide tables eliminate complex multi-table joins
- **Faster Queries**: Pre-aggregated dimensions reduce computation overhead
- **Better Caching**: Larger, more cohesive datasets improve cache hit rates

#### 2. **Big Data Best Practices**
- **Storage for Computation**: Trade storage cost for computational efficiency
- **Batch Processing**: Optimized for ETL batch operations and analytical queries
- **Scalability**: Design scales horizontally with data volume

#### 3. **Data Consistency Strategy**
- **Foreign Key Only**: Store only foreign keys in fact tables, not dimension names
- **Display-Time Resolution**: Resolve dimension names at query/display time
- **Audit Trail**: Maintain complete data lineage and quality tracking

---

## DWD Table Structure

### Core Fact Tables

#### Table: dwd_sales_detail
**Purpose**: Comprehensive sales fact table containing all sales data
**Source**: sales table
**Update Frequency**: Real-time
**Design Rationale**: Single source of truth for all sales-related analytics

##### Structure
| Column | Type | Constraints | Description | Source Mapping |
|--------|------|-------------|-------------|----------------|
| dwd_sales_id | BIGINT | PRIMARY KEY | DWD sales identifier | Generated |
| sale_id | TEXT | NOT NULL | Original sale ID | sales.sale_id |
| product_id | TEXT | NOT NULL | Product foreign key | sales.product_id |
| customer_id | TEXT | NULL | Customer foreign key | sales.customer_id |
| quantity_sold | INTEGER | NOT NULL | Quantity sold | sales.quantity_sold |
| price_per_unit | DECIMAL(12,2) | NOT NULL | Price per unit | sales.price_per_unit |
| total_amount | DECIMAL(15,2) | NOT NULL | Total amount | sales.total_amount |
| calculated_total | DECIMAL(15,2) | NOT NULL | Calculated total | quantity_sold * price_per_unit |
| sale_date | DATETIME | NOT NULL | Sale date | sales.sale_date |
| sale_value_range | VARCHAR(20) | NOT NULL | Sale value band | Derived from total_amount |
| data_quality_score | INTEGER | NOT NULL | Data quality score | Calculated |
| etl_batch_id | VARCHAR(50) | NOT NULL | ETL batch ID | Generated |
| etl_timestamp | DATETIME | NOT NULL | ETL timestamp | CURRENT_TIMESTAMP |

##### Business Rules
- Sales ID format: SLS-{sale_id}
- Sale value ranges: Low (<100), Medium (100-500), High (500-1000), Premium (>1000)
- Data quality score based on completeness and consistency
- Customer ID directly from sales table

##### Analytics Capabilities
- **Sales Analysis**: Complete sales performance tracking
- **Customer Analysis**: Customer transaction behavior
- **Product Analysis**: Product performance metrics
- **Temporal Analysis**: Time-based trend analysis

---

#### Table: dwd_inventory_detail
**Purpose**: Product inventory detail table with enhanced attributes
**Source**: inventory table + products table
**Update Frequency**: Real-time
**Design Rationale**: Single source for all inventory-related analytics

##### Structure
| Column | Type | Constraints | Description | Source Mapping |
|--------|------|-------------|-------------|----------------|
| dwd_inventory_id | BIGINT | PRIMARY KEY | DWD inventory identifier | Generated |
| product_id | TEXT | NOT NULL | Product foreign key | inventory.product_id |
| stock_level | INTEGER | NOT NULL | Current stock level | inventory.stock_level |
| last_updated | DATETIME | NOT NULL | Last update timestamp | inventory.last_updated |
| stock_status | VARCHAR(20) | NOT NULL | Stock status | Derived from stock_level |
| days_since_update | INTEGER | NULL | Days since update | DATEDIFF(DAY, last_updated, GETDATE()) |
| is_stale_data | BOOLEAN | NOT NULL | Stale data flag | days_since_update > 7 |
| stock_value | DECIMAL(15,2) | NOT NULL | Stock value | stock_level * unit_price |
| reorder_point | INTEGER | NULL | Reorder point | Derived business rule |
| is_low_stock | BOOLEAN | NOT NULL | Low stock flag | stock_level < reorder_point |
| turnover_ratio | DECIMAL(8,4) | NULL | Turnover ratio | Calculated from sales velocity |
| data_quality_score | INTEGER | NOT NULL | Data quality score | Calculated |
| etl_batch_id | VARCHAR(50) | NOT NULL | ETL batch ID | Generated |
| etl_timestamp | DATETIME | NOT NULL | ETL timestamp | CURRENT_TIMESTAMP |

##### Business Rules
- Stock status: In Stock (>10), Low Stock (1-10), Out of Stock (0)
- Reorder point calculation: Based on historical sales velocity
- Stock value calculation: stock_level * current_unit_price
- Data quality score based on update frequency and completeness

##### Analytics Capabilities
- **Inventory Management**: Stock level monitoring
- **Supply Chain**: Reorder point analysis
- **Financial**: Stock value analysis
- **Operational**: Low stock alerts

---

## Data Integration Strategy

### ETL Processing Logic

#### Sales Detail ETL
```python
def process_sales_detail():
    # Extract sales data
    sales_data = extract_sales_data()
    
    # Transform and enrich
    for sale in sales_data:
        sales_record = {
            'sale_id': sale.sale_id,
            'product_id': sale.product_id,
            'customer_id': sale.customer_id,
            'quantity_sold': sale.quantity_sold,
            'price_per_unit': sale.price_per_unit,
            'total_amount': sale.total_amount,
            'calculated_total': sale.quantity_sold * sale.price_per_unit,
            'sale_date': sale.sale_date,
            'sale_value_range': get_value_range(sale.total_amount),
            'data_quality_score': calculate_quality_score(sale),
            'etl_batch_id': get_current_batch_id(),
            'etl_timestamp': datetime.now()
        }
        
        # Load to DWD
        load_sales_detail(sales_record)
```

#### Inventory Detail ETL
```python
def process_inventory_detail():
    # Extract inventory and product data
    inventory_data = extract_inventory_data()
    product_data = extract_product_data()
    
    # Transform and enrich
    for inventory in inventory_data:
        product = get_product_by_id(inventory.product_id)
        
        inventory_record = {
            'product_id': inventory.product_id,
            'stock_level': inventory.stock_level,
            'last_updated': inventory.last_updated,
            'stock_status': get_stock_status(inventory.stock_level),
            'days_since_update': (datetime.now() - inventory.last_updated).days,
            'is_stale_data': (datetime.now() - inventory.last_updated).days > 7,
            'stock_value': inventory.stock_level * product.unit_price,
            'reorder_point': calculate_reorder_point(inventory.product_id),
            'is_low_stock': inventory.stock_level < calculate_reorder_point(inventory.product_id),
            'turnover_ratio': calculate_turnover_ratio(inventory.product_id),
            'data_quality_score': calculate_quality_score(inventory),
            'etl_batch_id': get_current_batch_id(),
            'etl_timestamp': datetime.now()
        }
        
        # Load to DWD
        load_inventory_detail(inventory_record)
```

---

## Query Performance Examples

### Sales Analysis Query
```sql
-- Customer sales analysis (no JOINs needed)
SELECT 
    customer_id,
    COUNT(*) as sales_count,
    SUM(total_amount) as total_spent,
    AVG(total_amount) as avg_sale_value,
    MAX(sale_date) as last_sale_date
FROM dwd_sales_detail
WHERE sale_date >= '2024-01-01'
GROUP BY customer_id
ORDER BY total_spent DESC;

-- Display-time resolution for customer names (with DIM layer)
SELECT 
    s.customer_id,
    c.customer_name,
    c.customer_type,
    s.sales_count,
    s.total_spent
FROM (
    SELECT customer_id, COUNT(*) as sales_count, SUM(total_amount) as total_spent
    FROM dwd_sales_detail
    WHERE sale_date >= '2024-01-01'
    GROUP BY customer_id
) s
LEFT JOIN dim_customer c ON s.customer_id = c.customer_id
ORDER BY s.total_spent DESC;
```

### Product Performance Query
```sql
-- Product performance analysis
SELECT 
    product_id,
    COUNT(*) as sales_count,
    SUM(quantity_sold) as total_quantity,
    SUM(total_amount) as total_revenue,
    AVG(price_per_unit) as avg_price
FROM dwd_sales_detail
WHERE sale_date >= '2024-01-01'
GROUP BY product_id
ORDER BY total_revenue DESC;

-- Combined with inventory analysis
SELECT 
    s.product_id,
    p.product_name,
    p.category,
    s.total_revenue,
    i.stock_level,
    i.stock_value,
    i.turnover_ratio
FROM (
    SELECT product_id, SUM(total_amount) as total_revenue, SUM(quantity_sold) as total_quantity
    FROM dwd_sales_detail
    WHERE sale_date >= '2024-01-01'
    GROUP BY product_id
) s
LEFT JOIN dim_product p ON s.product_id = p.product_id
LEFT JOIN dwd_inventory_detail i ON s.product_id = i.product_id
ORDER BY s.total_revenue DESC;
```

---

## Data Quality and Monitoring

### Quality Rules
1. **Completeness**: Check for null values in required fields
2. **Consistency**: Validate foreign key relationships
3. **Accuracy**: Cross-reference calculated fields
4. **Timeliness**: Monitor data freshness
5. **Validity**: Business rule validation

### Monitoring Metrics
- **Data Freshness**: Time since last update
- **Quality Score**: Overall data quality rating
- **Volume Metrics**: Record counts and growth rates
- **Error Rates**: Failed transformations and rejections

---

## Benefits of This Design

### 1. **Performance Benefits**
- **Reduced JOINs**: Wide tables minimize complex joins
- **Faster Queries**: Pre-calculated dimensions improve performance
- **Better Caching**: Larger, cohesive datasets improve cache efficiency
- **Parallel Processing**: Optimized for distributed computing

### 2. **Operational Benefits**
- **Simplified ETL**: Fewer tables to maintain and process
- **Easier Debugging**: Clear data lineage and audit trails
- **Flexible Analytics**: Support for various analytical patterns
- **Scalable Architecture**: Design scales with data volume

### 3. **Business Benefits**
- **Faster Insights**: Reduced query response times
- **Comprehensive Analysis**: Single source for transaction analytics
- **Data Consistency**: Foreign key strategy maintains integrity
- **Future-Proof**: Design accommodates new analytical requirements

This optimized DWD design provides a solid foundation for high-performance analytical processing while maintaining data integrity and supporting comprehensive business intelligence needs.
