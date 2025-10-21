# Data Lineage and Flow Documentation - Optimized Wide Table Architecture

## Overview
This document describes the complete data lineage from source business tables through the optimized wide table DWD (Data Warehouse Detail) layer to DWS (Data Warehouse Summary) layer, including data transformations, dependencies, and flow patterns for the new architecture.

## Data Architecture Layers

```
Source Layer (ODS) → DIM Layer → DWD Layer (Wide Tables) → DWS Layer (Data Cubes) → Application Layer
     ↓                ↓              ↓                        ↓                      ↓
  Raw Data        Dimension      Optimized Wide Tables    Data Cubes            Business
  (customers,     Tables        (dwd_sales_detail,        (dws_sales_cube,      Intelligence
   products,      (dim_customer, dwd_inventory_detail)    dws_inventory_cube)   & Reporting
   inventory,      dim_product)
   sales)
```

---

## Source to DIM Layer Mapping

### 1. Customer Dimension Data Flow
```
customers → dim_customer
```

#### Source Table: customers
- **Primary Key**: customer_id
- **Update Frequency**: Daily
- **Data Volume**: ~100K records

#### Target Table: dim_customer
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
| updated_at | updated_at | Direct mapping |
| updated_at | days_since_update | DATEDIFF(DAY, updated_at, GETDATE()) |
| customer_type, days_since_update | is_active_customer | Derived business logic |

---

### 2. Product Dimension Data Flow
```
products → dim_product
```

#### Source Table: products
- **Primary Key**: product_id
- **Update Frequency**: Daily
- **Data Volume**: ~50K records

#### Target Table: dim_product
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

---

### 1. Sales Detail Data Flow (Core Wide Table)
```
sales → dwd_sales_detail
```

#### Source Table: sales
- **Primary Key**: sale_id
- **Update Frequency**: Real-time
- **Data Volume**: ~1M+ records

#### Target Table: dwd_sales_detail
- **Primary Key**: dwd_sales_id
- **Update Frequency**: Real-time
- **Data Volume**: ~1M+ records
- **Design Type**: Wide Table (Core Fact Table)

#### Transformation Rules
| Source Field | Target Field | Transformation Logic |
|--------------|--------------|---------------------|
| sales.sale_id | sale_id | Direct mapping |
| sales.product_id | product_id | Direct mapping (Foreign Key) |
| sales.customer_id | customer_id | Direct mapping (Foreign Key) |
| sales.quantity_sold | quantity_sold | Direct mapping |
| sales.price_per_unit | price_per_unit | Direct mapping |
| sales.total_amount | total_amount | Direct mapping |
| sales.total_amount | calculated_total | quantity_sold * price_per_unit |
| sales.sale_date | sale_date | Direct mapping |
| sales.total_amount | sale_value_range | CASE WHEN total_amount < 100 THEN 'Low' WHEN total_amount < 500 THEN 'Medium' WHEN total_amount < 1000 THEN 'High' ELSE 'Premium' END |

#### Data Quality Checks
- Sale ID uniqueness validation
- Amount calculation validation (total_amount = quantity_sold * price_per_unit)
- Date validation (sale_date <= current_date)
- Foreign key referential integrity

---

### 2. Inventory Detail Data Flow (Snapshot Wide Table)
```
inventory + products → dwd_inventory_detail
```

#### Source Tables: inventory + products
- **Primary Keys**: product_id
- **Update Frequency**: Real-time
- **Data Volume**: ~50K records

#### Target Table: dwd_inventory_detail
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
| inventory.product_id | turnover_ratio | Calculated from sales velocity |

#### Data Quality Checks
- Stock level validation (non-negative)
- Product ID referential integrity
- Stock value calculation validation
- Data freshness monitoring
- Reorder point calculation validation

## DWD to DWS Layer Mapping - Data Cube Design

### 1. Sales Data Cube Flow
```
dwd_sales_detail + dim_customer + dim_product → dws_sales_cube
```

#### Source Tables
- **dwd_sales_detail**: Sales facts
- **dim_customer**: Customer dimensions
- **dim_product**: Product dimensions

#### Target Table: dws_sales_cube
- **Aggregation Level**: Core dimensions + date dimension
- **Update Frequency**: Daily
- **Key Metrics**: Transaction count, total revenue, total quantity, avg/max/min transaction values

#### Aggregation Logic
| Metric | Calculation Logic | Source Tables |
|--------|------------------|---------------|
| transaction_count | COUNT(*) | dwd_sales_detail |
| total_revenue | SUM(total_amount) | dwd_sales_detail |
| total_quantity | SUM(quantity_sold) | dwd_sales_detail |
| avg_transaction_value | AVG(total_amount) | dwd_sales_detail |
| max_transaction_value | MAX(total_amount) | dwd_sales_detail |
| min_transaction_value | MIN(total_amount) | dwd_sales_detail |

#### Core Dimensions
- **Time**: sale_date (only date dimension)
- **Customer**: customer_id, customer_type, region
- **Product**: product_id, category, price_range
- **Sales**: sale_value_range

---

### 2. Inventory Data Cube Flow
```
dwd_inventory_detail + dim_product → dws_inventory_cube
```

#### Source Tables
- **dwd_inventory_detail**: Inventory facts
- **dim_product**: Product dimensions

#### Target Table: dws_inventory_cube
- **Aggregation Level**: Core dimensions + date dimension
- **Update Frequency**: Daily
- **Key Metrics**: Product count, total stock level/value, avg stock metrics, avg turnover ratio

#### Aggregation Logic
| Metric | Calculation Logic | Source Tables |
|--------|------------------|---------------|
| product_count | COUNT(*) | dwd_inventory_detail |
| total_stock_level | SUM(stock_level) | dwd_inventory_detail |
| total_stock_value | SUM(stock_value) | dwd_inventory_detail |
| avg_stock_level | AVG(stock_level) | dwd_inventory_detail |
| avg_stock_value | AVG(stock_value) | dwd_inventory_detail |
| avg_turnover_ratio | AVG(turnover_ratio) | dwd_inventory_detail |

#### Core Dimensions
- **Time**: last_updated_date (only date dimension)
- **Product**: product_id, category, price_range
- **Inventory**: stock_status, is_low_stock, is_stale_data

---

## Data Flow Patterns

### 1. Real-time Sales Processing
```
Sales Event → dwd_sales_detail → dws_sales_cube
```

### 2. Batch Inventory Processing
```
Inventory Update → dwd_inventory_detail → dws_inventory_cube
Product Update → dim_product → dws_inventory_cube
```

### 3. Daily Dimension Processing
```
Customer Update → dim_customer → dws_sales_cube
Product Update → dim_product → dws_sales_cube + dws_inventory_cube
```

### 4. Application Layer Time Aggregation
```
dws_sales_cube → Application Layer (Monthly/Quarterly/Yearly calculations)
dws_inventory_cube → Application Layer (Weekly/Monthly aggregations)
```

---

## Data Dependencies and Scheduling

### ETL Schedule
- **Real-time**: dwd_sales_detail, dwd_inventory_detail
- **Daily**: dim_customer, dim_product, dws_sales_cube, dws_inventory_cube
- **Application Layer**: Dynamic time dimension calculations

### Dependency Chain
1. **Source → DIM**: Independent parallel processing
2. **Source → DWD**: Independent parallel processing
3. **DWD + DIM → DWS**: Sequential processing based on dependencies
4. **DWS → Application**: Real-time or near real-time

### Data Freshness Requirements
- **Sales Data**: < 5 minutes
- **Inventory Data**: < 15 minutes
- **Customer/Product Data**: < 24 hours
- **Cube Data**: < 2 hours
- **Application Layer**: Real-time calculation

---

## Performance Optimization

### Wide Table Benefits
- **Reduced JOINs**: Single table queries for most analytics
- **Better Caching**: Improved data locality
- **Parallel Processing**: Optimized for distributed computing
- **Index Efficiency**: Simplified indexing strategies

### Data Cube Benefits
- **Pre-calculated Aggregations**: Fast analytical queries
- **Avoid Dimension Explosion**: Only core dimensions stored
- **Application Layer Flexibility**: Dynamic time calculations
- **Storage Efficiency**: Reduced cube storage requirements

### Query Performance Patterns
- **Sales Analysis**: Single table query on dwd_sales_detail
- **Inventory Analysis**: Single table query on dwd_inventory_detail
- **Cross-domain Analysis**: Minimal JOINs between wide tables
- **Time Aggregation**: Application layer dynamic calculations
- **Cube Queries**: Pre-aggregated data for fast BI queries

This optimized data lineage design leverages the wide table and data cube architecture to provide high-performance analytical capabilities while maintaining clear data flow patterns and dependencies.