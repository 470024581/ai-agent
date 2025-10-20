# DWD Layer (Data Warehouse Detail) Schema Design - Optimized Wide Table Approach

## Overview
The DWD layer adopts a **wide table design** optimized for big data analytics, featuring 2 core fact tables and 2 dimension tables. This design prioritizes query performance over storage efficiency, following the "storage for computation" principle common in big data environments.

## Design Philosophy

### Core Principles
- **Wide Table Design**: Minimize JOIN operations for better query performance
- **Foreign Key Strategy**: Maintain referential integrity without redundant dimension data
- **Big Data Optimization**: Optimize for analytical workloads over transactional consistency
- **Buffer Strategy**: Use 30-day data buffer or recalculation mechanisms for data freshness

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

#### Table: dwd_transaction_detail
**Purpose**: Comprehensive transaction fact table containing all sales and order data
**Source**: sales table + orders table (via customer_id relationship)
**Update Frequency**: Real-time
**Retention**: 7 years
**Design Rationale**: Single source of truth for all transaction-related analytics

##### Structure
| Column | Type | Constraints | Description | Source Mapping |
|--------|------|-------------|-------------|----------------|
| dwd_transaction_id | BIGINT | PRIMARY KEY | DWD transaction identifier | Generated |
| sale_id | TEXT | NOT NULL | Original sale ID | sales.sale_id |
| product_id | TEXT | NOT NULL | Product foreign key | sales.product_id |
| customer_id | TEXT | NULL | Customer foreign key | Derived from orders.customer_id |
| quantity_sold | INTEGER | NOT NULL | Quantity sold | sales.quantity_sold |
| price_per_unit | DECIMAL(12,2) | NOT NULL | Price per unit | sales.price_per_unit |
| total_amount | DECIMAL(15,2) | NOT NULL | Total amount | sales.total_amount |
| calculated_total | DECIMAL(15,2) | NOT NULL | Calculated total | quantity_sold * price_per_unit |
| sale_date | DATETIME | NOT NULL | Sale date | sales.sale_date |
| sale_year | INTEGER | NOT NULL | Sale year | YEAR(sale_date) |
| sale_month | INTEGER | NOT NULL | Sale month | MONTH(sale_date) |
| sale_quarter | INTEGER | NOT NULL | Sale quarter | QUARTER(sale_date) |
| sale_week | INTEGER | NOT NULL | Sale week | WEEK(sale_date) |
| sale_day_of_week | INTEGER | NOT NULL | Day of week | DAYOFWEEK(sale_date) |
| sale_value_range | VARCHAR(20) | NOT NULL | Sale value band | Derived from total_amount |
| order_id | TEXT | NULL | Related order ID | orders.order_id |
| order_date | DATETIME | NULL | Order date | orders.order_date |
| order_status | VARCHAR(20) | NULL | Order status | orders.status |
| payment_method | VARCHAR(30) | NULL | Payment method | orders.payment_method |
| shipping_address | TEXT | NULL | Shipping address | orders.shipping_address |
| data_quality_score | INTEGER | NOT NULL | Data quality score | Calculated |
| etl_batch_id | VARCHAR(50) | NOT NULL | ETL batch ID | Generated |
| etl_timestamp | DATETIME | NOT NULL | ETL timestamp | CURRENT_TIMESTAMP |

##### Business Rules
- Transaction ID format: TXN-{sale_id}
- Sale value ranges: Low (<100), Medium (100-500), High (500-1000), Premium (>1000)
- Data quality score based on completeness and consistency
- Customer ID derived from order relationship when available

##### Analytics Capabilities
- **Sales Analysis**: Complete sales performance tracking
- **Customer Analysis**: Customer transaction behavior
- **Product Analysis**: Product performance metrics
- **Temporal Analysis**: Time-based trend analysis
- **Order Analysis**: Order fulfillment tracking

---

#### Table: dwd_inventory_snapshot
**Purpose**: Product inventory snapshot table with enhanced attributes
**Source**: inventory table + products table
**Update Frequency**: Real-time
**Retention**: 3 years
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

### Dimension Tables

#### Table: dwd_customer_dimension
**Purpose**: Customer dimension table for display-time resolution
**Source**: customers table
**Update Frequency**: Daily
**Retention**: 7 years

##### Structure
| Column | Type | Constraints | Description | Source Mapping |
|--------|------|-------------|-------------|----------------|
| customer_id | TEXT | PRIMARY KEY | Customer identifier | customers.customer_id |
| customer_name | VARCHAR(200) | NOT NULL | Customer name | customers.customer_name |
| contact_person | VARCHAR(100) | NULL | Contact person | customers.contact_person |
| email | VARCHAR(100) | NULL | Email address | customers.email |
| phone | VARCHAR(20) | NULL | Phone number | customers.phone |
| address | TEXT | NULL | Address | customers.address |
| customer_type | VARCHAR(20) | NOT NULL | Customer type | customers.customer_type |
| region | VARCHAR(50) | NULL | Geographic region | Derived from address |
| created_at | DATETIME | NOT NULL | Creation timestamp | customers.created_at |
| registration_year | INTEGER | NOT NULL | Registration year | YEAR(created_at) |
| registration_month | INTEGER | NOT NULL | Registration month | MONTH(created_at) |
| registration_quarter | INTEGER | NOT NULL | Registration quarter | QUARTER(created_at) |
| updated_at | DATETIME | NOT NULL | Update timestamp | customers.updated_at |
| days_since_update | INTEGER | NULL | Days since update | DATEDIFF(DAY, updated_at, GETDATE()) |
| is_active_customer | BOOLEAN | NOT NULL | Active customer flag | Derived |
| etl_batch_id | VARCHAR(50) | NOT NULL | ETL batch ID | Generated |
| etl_timestamp | DATETIME | NOT NULL | ETL timestamp | CURRENT_TIMESTAMP |

---

#### Table: dwd_product_dimension
**Purpose**: Product dimension table for display-time resolution
**Source**: products table
**Update Frequency**: Daily
**Retention**: 7 years

##### Structure
| Column | Type | Constraints | Description | Source Mapping |
|--------|------|-------------|-------------|----------------|
| product_id | TEXT | PRIMARY KEY | Product identifier | products.product_id |
| product_name | VARCHAR(200) | NOT NULL | Product name | products.product_name |
| category | VARCHAR(100) | NOT NULL | Product category | products.category |
| unit_price | DECIMAL(12,2) | NOT NULL | Unit price | products.unit_price |
| price_range | VARCHAR(20) | NOT NULL | Price range | Derived from unit_price |
| etl_batch_id | VARCHAR(50) | NOT NULL | ETL batch ID | Generated |
| etl_timestamp | DATETIME | NOT NULL | ETL timestamp | CURRENT_TIMESTAMP |

---

## Data Integration Strategy

### ETL Processing Logic

#### Transaction Detail ETL
```python
def process_transaction_detail():
    # Extract sales data
    sales_data = extract_sales_data()
    
    # Extract related order data
    order_data = extract_order_data()
    
    # Transform and enrich
    for sale in sales_data:
        # Find related order
        related_order = find_order_by_customer_and_date(sale.customer_id, sale.sale_date)
        
        # Create transaction record
        transaction = {
            'sale_id': sale.sale_id,
            'product_id': sale.product_id,
            'customer_id': related_order.customer_id if related_order else None,
            'quantity_sold': sale.quantity_sold,
            'price_per_unit': sale.price_per_unit,
            'total_amount': sale.total_amount,
            'calculated_total': sale.quantity_sold * sale.price_per_unit,
            'sale_date': sale.sale_date,
            'order_id': related_order.order_id if related_order else None,
            'order_date': related_order.order_date if related_order else None,
            'order_status': related_order.status if related_order else None,
            'payment_method': related_order.payment_method if related_order else None,
            'shipping_address': related_order.shipping_address if related_order else None,
            # Add time dimensions
            'sale_year': sale.sale_date.year,
            'sale_month': sale.sale_date.month,
            'sale_quarter': get_quarter(sale.sale_date),
            'sale_week': sale.sale_date.isocalendar()[1],
            'sale_day_of_week': sale.sale_date.weekday(),
            'sale_value_range': get_value_range(sale.total_amount),
            'data_quality_score': calculate_quality_score(sale),
            'etl_batch_id': get_current_batch_id(),
            'etl_timestamp': datetime.now()
        }
        
        # Load to DWD
        load_transaction_detail(transaction)
```

#### Inventory Snapshot ETL
```python
def process_inventory_snapshot():
    # Extract inventory and product data
    inventory_data = extract_inventory_data()
    product_data = extract_product_data()
    
    # Transform and enrich
    for inventory in inventory_data:
        product = get_product_by_id(inventory.product_id)
        
        snapshot = {
            'product_id': inventory.product_id,
            'stock_level': inventory.stock_level,
            'last_updated': inventory.last_updated,
            'stock_status': get_stock_status(inventory.stock_level),
            'days_since_update': (datetime.now() - inventory.last_updated).days,
            'is_stale_data': (datetime.now() - inventory.last_updated).days > 7,
            'stock_value': inventory.stock_level * product.unit_price,
            'reorder_point': calculate_reorder_point(inventory.product_id),
            'is_low_stock': inventory.stock_level < calculate_reorder_point(inventory.product_id),
            'data_quality_score': calculate_quality_score(inventory),
            'etl_batch_id': get_current_batch_id(),
            'etl_timestamp': datetime.now()
        }
        
        # Load to DWD
        load_inventory_snapshot(snapshot)
```

---

## Query Performance Examples

### Customer Analysis Query
```sql
-- Customer transaction analysis (no JOINs needed)
SELECT 
    customer_id,
    COUNT(*) as transaction_count,
    SUM(total_amount) as total_spent,
    AVG(total_amount) as avg_transaction_value,
    MAX(sale_date) as last_transaction_date
FROM dwd_transaction_detail
WHERE sale_date >= '2024-01-01'
GROUP BY customer_id
ORDER BY total_spent DESC;

-- Display-time resolution for customer names
SELECT 
    t.customer_id,
    c.customer_name,
    c.customer_type,
    t.transaction_count,
    t.total_spent
FROM (
    SELECT customer_id, COUNT(*) as transaction_count, SUM(total_amount) as total_spent
    FROM dwd_transaction_detail
    WHERE sale_date >= '2024-01-01'
    GROUP BY customer_id
) t
LEFT JOIN dwd_customer_dimension c ON t.customer_id = c.customer_id
ORDER BY t.total_spent DESC;
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
FROM dwd_transaction_detail
WHERE sale_date >= '2024-01-01'
GROUP BY product_id
ORDER BY total_revenue DESC;

-- Combined with inventory analysis
SELECT 
    t.product_id,
    p.product_name,
    p.category,
    t.total_revenue,
    i.stock_level,
    i.stock_value,
    CASE 
        WHEN i.stock_level > 0 THEN t.total_quantity / i.stock_level
        ELSE 0 
    END as turnover_ratio
FROM (
    SELECT product_id, SUM(total_amount) as total_revenue, SUM(quantity_sold) as total_quantity
    FROM dwd_transaction_detail
    WHERE sale_date >= '2024-01-01'
    GROUP BY product_id
) t
LEFT JOIN dwd_product_dimension p ON t.product_id = p.product_id
LEFT JOIN dwd_inventory_snapshot i ON t.product_id = i.product_id
ORDER BY t.total_revenue DESC;
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
