# Data Lineage and Flow Documentation - Wide Table Architecture

## Overview
This document describes the complete data lineage from source business tables through the optimized wide table DWD (Data Warehouse Detail) layer to DWS (Data Warehouse Summary) layer, including data transformations, dependencies, and flow patterns for the new architecture.

## Data Architecture Layers

```
Source Layer (ODS) → DWD Layer (Wide Tables) → DWS Layer → Application Layer
     ↓                    ↓                      ↓            ↓
  Raw Data         Optimized Wide Tables    Aggregated   Business
  (customers,      (dwd_transaction_detail, Data         Intelligence
   products,        dwd_inventory_snapshot,  (dws_*)      & Reporting
   inventory,       dwd_customer_dimension,
   orders,          dwd_product_dimension)
   sales)
```

---

## Source to DWD Layer Mapping - Wide Table Design

### 1. Transaction Data Flow (Core Wide Table)
```
sales + orders → dwd_transaction_detail
```

#### Source Tables: sales + orders
- **Primary Keys**: sale_id, order_id
- **Update Frequency**: Real-time
- **Data Volume**: ~1M+ records

#### Target Table: dwd_transaction_detail
- **Primary Key**: dwd_transaction_id
- **Update Frequency**: Real-time
- **Data Volume**: ~1M+ records
- **Design Type**: Wide Table (Core Fact Table)

#### Transformation Rules
| Source Field | Target Field | Transformation Logic |
|--------------|--------------|---------------------|
| sales.sale_id | sale_id | Direct mapping |
| sales.product_id | product_id | Direct mapping (Foreign Key) |
| orders.customer_id | customer_id | Derived from order relationship (Foreign Key) |
| sales.quantity_sold | quantity_sold | Direct mapping |
| sales.price_per_unit | price_per_unit | Direct mapping |
| sales.total_amount | total_amount | Direct mapping |
| sales.total_amount | calculated_total | quantity_sold * price_per_unit |
| sales.sale_date | sale_date | Direct mapping |
| sales.sale_date | sale_year | YEAR(sale_date) |
| sales.sale_date | sale_month | MONTH(sale_date) |
| sales.sale_date | sale_quarter | QUARTER(sale_date) |
| sales.sale_date | sale_week | WEEK(sale_date) |
| sales.sale_date | sale_day_of_week | DAYOFWEEK(sale_date) |
| sales.total_amount | sale_value_range | CASE WHEN total_amount < 100 THEN 'Low' WHEN total_amount < 500 THEN 'Medium' WHEN total_amount < 1000 THEN 'High' ELSE 'Premium' END |
| orders.order_id | order_id | Derived from order relationship |
| orders.order_date | order_date | Derived from order relationship |
| orders.status | order_status | Derived from order relationship |
| orders.payment_method | payment_method | Derived from order relationship |
| orders.shipping_address | shipping_address | Derived from order relationship |

#### Data Quality Checks
- Sale ID uniqueness validation
- Amount calculation validation (total_amount = quantity_sold * price_per_unit)
- Date validation (sale_date <= current_date)
- Foreign key referential integrity
- Order-Sale relationship consistency

---

### 2. Inventory Data Flow (Snapshot Wide Table)
```
inventory + products → dwd_inventory_snapshot
```

#### Source Tables: inventory + products
- **Primary Keys**: product_id
- **Update Frequency**: Real-time
- **Data Volume**: ~50K records

#### Target Table: dwd_inventory_snapshot
- **Primary Key**: dwd_inventory_id
- **Update Frequency**: Real-time
- **Data Volume**: ~50K records
- **Design Type**: Wide Table (Snapshot Fact Table)

#### Transformation Rules
| Source Field | Target Field | Transformation Logic |
|--------------|--------------|---------------------|
| inventory.product_id | product_id | Direct mapping (Foreign Key) |
| inventory.stock_level | stock_level | Direct mapping |
| inventory.last_updated | last_updated | Direct mapping |
| inventory.stock_level | stock_status | CASE WHEN stock_level > 10 THEN 'In Stock' WHEN stock_level > 0 THEN 'Low Stock' ELSE 'Out of Stock' END |
| inventory.last_updated | days_since_update | DATEDIFF(DAY, last_updated, GETDATE()) |
| inventory.last_updated | is_stale_data | DATEDIFF(DAY, last_updated, GETDATE()) > 7 |
| inventory.stock_level, products.unit_price | stock_value | stock_level * unit_price |
| inventory.product_id | reorder_point | Calculated based on historical sales velocity |
| inventory.stock_level, reorder_point | is_low_stock | stock_level < reorder_point |

#### Data Quality Checks
- Stock level validation (non-negative)
- Product ID referential integrity
- Stock value calculation validation
- Data freshness monitoring
- Reorder point calculation validation

---

### 3. Customer Dimension Data Flow
```
customers → dwd_customer_dimension
```

#### Source Table: customers
- **Primary Key**: customer_id
- **Update Frequency**: Daily
- **Data Volume**: ~100K records

#### Target Table: dwd_customer_dimension
- **Primary Key**: customer_id
- **Update Frequency**: Daily
- **Data Volume**: ~100K records
- **Design Type**: Dimension Table (Display-time Resolution)

#### Transformation Rules
| Source Field | Target Field | Transformation Logic |
|--------------|--------------|---------------------|
| customer_id | customer_id | Direct mapping |
| customer_name | customer_name | Direct mapping |
| contact_person | contact_person | Direct mapping |
| email | email | LOWER(TRIM(email)) |
| phone | phone | Standardize phone format |
| address | address | Direct mapping |
| address | region | Geographic region mapping |
| customer_type | customer_type | UPPER(customer_type) |
| created_at | created_at | Direct mapping |
| created_at | registration_year | YEAR(created_at) |
| created_at | registration_month | MONTH(created_at) |
| created_at | registration_quarter | QUARTER(created_at) |
| updated_at | updated_at | Direct mapping |
| updated_at | days_since_update | DATEDIFF(DAY, updated_at, GETDATE()) |
| customer_type, days_since_update | is_active_customer | Derived business logic |

#### Data Quality Checks
- Email format validation
- Phone number standardization
- Address normalization
- Customer type validation
- Data completeness scoring

---

### 4. Product Dimension Data Flow
```
products → dwd_product_dimension
```

#### Source Table: products
- **Primary Key**: product_id
- **Update Frequency**: Daily
- **Data Volume**: ~50K records

#### Target Table: dwd_product_dimension
- **Primary Key**: product_id
- **Update Frequency**: Daily
- **Data Volume**: ~50K records
- **Design Type**: Dimension Table (Display-time Resolution)

#### Transformation Rules
| Source Field | Target Field | Transformation Logic |
|--------------|--------------|---------------------|
| product_id | product_id | Direct mapping |
| product_name | product_name | TRIM(product_name) |
| category | category | UPPER(TRIM(category)) |
| unit_price | unit_price | ROUND(unit_price, 2) |
| unit_price | price_range | CASE WHEN unit_price < 50 THEN 'Low' WHEN unit_price < 200 THEN 'Medium' WHEN unit_price < 1000 THEN 'High' ELSE 'Premium' END |

#### Data Quality Checks
- Product ID uniqueness validation
- Price validation (unit_price > 0)
- Category standardization
- Product name completeness

---

## DWD to DWS Layer Mapping

### 1. Customer Analytics Summary
```
dwd_transaction_detail + dwd_customer_dimension → dws_customer_summary
```

#### Source Tables
- **dwd_transaction_detail**: Transaction facts
- **dwd_customer_dimension**: Customer dimensions

#### Target Table: dws_customer_summary
- **Aggregation Level**: Customer level
- **Update Frequency**: Daily
- **Key Metrics**: Total transactions, total spent, avg transaction value, customer lifetime value

#### Aggregation Logic
| Metric | Calculation Logic | Source Tables |
|--------|------------------|---------------|
| total_transactions | COUNT(dwd_transaction_detail.sale_id) | dwd_transaction_detail |
| total_spent | SUM(dwd_transaction_detail.total_amount) | dwd_transaction_detail |
| avg_transaction_value | AVG(dwd_transaction_detail.total_amount) | dwd_transaction_detail |
| customer_lifetime_days | DATEDIFF(DAY, MIN(sale_date), MAX(sale_date)) | dwd_transaction_detail |
| is_active_customer | days_since_last_transaction <= 90 | Calculated |
| customer_value_tier | Based on total_spent ranges | Calculated |

---

### 2. Product Performance Summary
```
dwd_transaction_detail + dwd_inventory_snapshot + dwd_product_dimension → dws_product_summary
```

#### Source Tables
- **dwd_transaction_detail**: Sales facts
- **dwd_inventory_snapshot**: Inventory facts
- **dwd_product_dimension**: Product dimensions

#### Target Table: dws_product_summary
- **Aggregation Level**: Product level
- **Update Frequency**: Daily
- **Key Metrics**: Total sales, total revenue, inventory turnover, stock status

#### Aggregation Logic
| Metric | Calculation Logic | Source Tables |
|--------|------------------|---------------|
| total_sales_count | COUNT(dwd_transaction_detail.sale_id) | dwd_transaction_detail |
| total_revenue | SUM(dwd_transaction_detail.total_amount) | dwd_transaction_detail |
| current_stock_level | dwd_inventory_snapshot.stock_level | dwd_inventory_snapshot |
| turnover_ratio | total_quantity_sold / current_stock_level | Calculated |
| product_performance_tier | Based on total_revenue ranges | Calculated |

---

### 3. Sales Analytics Summary
```
dwd_transaction_detail → dws_sales_summary_daily/monthly
```

#### Source Table
- **dwd_transaction_detail**: All transaction facts

#### Target Tables
- **dws_sales_summary_daily**: Daily aggregation
- **dws_sales_summary_monthly**: Monthly aggregation

#### Aggregation Logic
| Metric | Calculation Logic | Source Tables |
|--------|------------------|---------------|
| total_transactions | COUNT(dwd_transaction_detail.sale_id) | dwd_transaction_detail |
| total_revenue | SUM(dwd_transaction_detail.total_amount) | dwd_transaction_detail |
| unique_customers | COUNT(DISTINCT dwd_transaction_detail.customer_id) | dwd_transaction_detail |
| unique_products | COUNT(DISTINCT dwd_transaction_detail.product_id) | dwd_transaction_detail |
| revenue_growth_rate | Calculated vs previous period | Calculated |

---

### 4. Inventory Management Summary
```
dwd_inventory_snapshot + dwd_product_dimension → dws_inventory_summary
```

#### Source Tables
- **dwd_inventory_snapshot**: Inventory facts
- **dwd_product_dimension**: Product dimensions

#### Target Table: dws_inventory_summary
- **Aggregation Level**: Product level
- **Update Frequency**: Daily
- **Key Metrics**: Stock levels, stock values, reorder points, turnover ratios

#### Aggregation Logic
| Metric | Calculation Logic | Source Tables |
|--------|------------------|---------------|
| current_stock_level | dwd_inventory_snapshot.stock_level | dwd_inventory_snapshot |
| current_stock_value | dwd_inventory_snapshot.stock_value | dwd_inventory_snapshot |
| stock_status | dwd_inventory_snapshot.stock_status | dwd_inventory_snapshot |
| is_low_stock | dwd_inventory_snapshot.is_low_stock | dwd_inventory_snapshot |
| inventory_turnover_ratio | Calculated from sales data | Calculated |

---

### 5. Category Performance Summary
```
dwd_transaction_detail + dwd_product_dimension → dws_category_performance
```

#### Source Tables
- **dwd_transaction_detail**: Sales facts
- **dwd_product_dimension**: Product dimensions

#### Target Table: dws_category_performance
- **Aggregation Level**: Category level
- **Update Frequency**: Daily
- **Key Metrics**: Category revenue, product counts, market share

#### Aggregation Logic
| Metric | Calculation Logic | Source Tables |
|--------|------------------|---------------|
| total_products | COUNT(DISTINCT dwd_product_dimension.product_id) | dwd_product_dimension |
| total_revenue | SUM(dwd_transaction_detail.total_amount) | dwd_transaction_detail |
| avg_transaction_value | AVG(dwd_transaction_detail.total_amount) | dwd_transaction_detail |
| market_share_percentage | Calculated vs total revenue | Calculated |

---

## Data Flow Patterns

### 1. Real-time Transaction Processing
```
Sales Event → dwd_transaction_detail → dws_sales_summary_daily
Order Event → dwd_transaction_detail → dws_customer_summary
```

### 2. Batch Inventory Processing
```
Inventory Update → dwd_inventory_snapshot → dws_inventory_summary
Product Update → dwd_product_dimension → dws_product_summary
```

### 3. Daily Aggregation Processing
```
dwd_transaction_detail → dws_customer_summary (Daily)
dwd_transaction_detail → dws_product_summary (Daily)
dwd_inventory_snapshot → dws_inventory_summary (Daily)
```

### 4. Monthly Aggregation Processing
```
dwd_transaction_detail → dws_sales_summary_monthly (Monthly)
dwd_transaction_detail → dws_category_performance (Monthly)
```

---

## Data Dependencies and Scheduling

### ETL Schedule
- **Real-time**: dwd_transaction_detail, dwd_inventory_snapshot
- **Daily**: dwd_customer_dimension, dwd_product_dimension, all DWS tables
- **Monthly**: dws_sales_summary_monthly, dws_category_performance

### Dependency Chain
1. **Source → DWD**: Independent parallel processing
2. **DWD → DWS**: Sequential processing based on dependencies
3. **DWS → Application**: Real-time or near real-time

### Data Freshness Requirements
- **Transaction Data**: < 5 minutes
- **Inventory Data**: < 15 minutes
- **Customer/Product Data**: < 24 hours
- **Summary Data**: < 2 hours

---

## Performance Optimization

### Wide Table Benefits
- **Reduced JOINs**: Single table queries for most analytics
- **Better Caching**: Improved data locality
- **Parallel Processing**: Optimized for distributed computing
- **Index Efficiency**: Simplified indexing strategies

### Query Performance Patterns
- **Customer Analysis**: Single table query on dwd_transaction_detail
- **Product Analysis**: Single table query on dwd_transaction_detail
- **Inventory Analysis**: Single table query on dwd_inventory_snapshot
- **Cross-domain Analysis**: Minimal JOINs between wide tables

This optimized data lineage design leverages the wide table architecture to provide high-performance analytical capabilities while maintaining clear data flow patterns and dependencies.