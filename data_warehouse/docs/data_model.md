# Data Model Design
# 数据模型设计文档

## Overview
This document describes the data model design for the Shanghai Transport Card data warehouse, including both the operational database (Supabase PostgreSQL) and the data warehouse (Databricks Delta Lake).

## Architecture Overview

```
Source Data (Supabase PostgreSQL)
    ↓
Staging Layer (Databricks Delta Lake)
    ↓
Dimension Tables (Databricks Delta Lake)
    ↓
Fact Tables (Databricks Delta Lake)
    ↓
Marts (Business Metrics Tables)
    ↓
Power BI Reports
```

## Operational Database Schema (Supabase PostgreSQL)

### 1. users Table
**Purpose**: Store user information and card details

| Column Name | Data Type | Constraints | Description |
|------------|-----------|-------------|-------------|
| user_id | BIGSERIAL | PRIMARY KEY | Unique user identifier |
| card_number | VARCHAR(50) | UNIQUE, NOT NULL | Transport card number |
| card_type | VARCHAR(20) | NOT NULL | Card type: Regular, Student, Senior |
| is_verified | BOOLEAN | DEFAULT FALSE | Whether user is verified |
| created_at | TIMESTAMP | DEFAULT NOW() | Registration timestamp |
| updated_at | TIMESTAMP | DEFAULT NOW() | Last update timestamp |

**Indexes**:
- `idx_users_card_number` ON users(card_number)
- `idx_users_card_type` ON users(card_type)

### 2. stations Table
**Purpose**: Store station/stop information

| Column Name | Data Type | Constraints | Description |
|------------|-----------|-------------|-------------|
| station_id | BIGSERIAL | PRIMARY KEY | Unique station identifier |
| station_name | VARCHAR(100) | NOT NULL | Station name |
| station_type | VARCHAR(20) | NOT NULL | Station type: Metro, Bus |
| latitude | DECIMAL(10, 8) | | Geographic latitude |
| longitude | DECIMAL(11, 8) | | Geographic longitude |
| district | VARCHAR(50) | | Administrative district |
| created_at | TIMESTAMP | DEFAULT NOW() | Creation timestamp |

**Indexes**:
- `idx_stations_name` ON stations(station_name)
- `idx_stations_type` ON stations(station_type)
- `idx_stations_location` ON stations(latitude, longitude)

### 3. routes Table
**Purpose**: Store route/line information

| Column Name | Data Type | Constraints | Description |
|------------|-----------|-------------|-------------|
| route_id | BIGSERIAL | PRIMARY KEY | Unique route identifier |
| route_name | VARCHAR(100) | NOT NULL | Route name (e.g., "Line 1", "Bus 123") |
| route_type | VARCHAR(20) | NOT NULL | Route type: Metro, Bus |
| start_station_id | BIGINT | FOREIGN KEY | Starting station ID |
| end_station_id | BIGINT | FOREIGN KEY | Ending station ID |
| created_at | TIMESTAMP | DEFAULT NOW() | Creation timestamp |

**Indexes**:
- `idx_routes_name` ON routes(route_name)
- `idx_routes_type` ON routes(route_type)

**Foreign Keys**:
- `fk_routes_start_station` REFERENCES stations(station_id)
- `fk_routes_end_station` REFERENCES stations(station_id)

### 4. transactions Table
**Purpose**: Store transaction records

| Column Name | Data Type | Constraints | Description |
|------------|-----------|-------------|-------------|
| transaction_id | BIGSERIAL | PRIMARY KEY | Unique transaction identifier |
| user_id | BIGINT | NOT NULL, FOREIGN KEY | User identifier |
| station_id | BIGINT | NOT NULL, FOREIGN KEY | Station identifier |
| route_id | BIGINT | FOREIGN KEY | Route identifier (nullable) |
| transaction_date | DATE | NOT NULL | Transaction date |
| transaction_time | TIME | NOT NULL | Transaction time |
| amount | DECIMAL(10, 2) | NOT NULL | Transaction amount |
| transaction_type | VARCHAR(20) | NOT NULL | Transaction type: Entry, Exit, Transfer |
| created_at | TIMESTAMP | DEFAULT NOW() | Creation timestamp |

**Indexes**:
- `idx_transactions_user_id` ON transactions(user_id)
- `idx_transactions_station_id` ON transactions(station_id)
- `idx_transactions_date` ON transactions(transaction_date)
- `idx_transactions_user_date` ON transactions(user_id, transaction_date)

**Foreign Keys**:
- `fk_transactions_user` REFERENCES users(user_id)
- `fk_transactions_station` REFERENCES stations(station_id)
- `fk_transactions_route` REFERENCES routes(route_id)

### 5. topups Table
**Purpose**: Store top-up records

| Column Name | Data Type | Constraints | Description |
|------------|-----------|-------------|-------------|
| topup_id | BIGSERIAL | PRIMARY KEY | Unique top-up identifier |
| user_id | BIGINT | NOT NULL, FOREIGN KEY | User identifier |
| topup_date | DATE | NOT NULL | Top-up date |
| topup_time | TIME | NOT NULL | Top-up time |
| amount | DECIMAL(10, 2) | NOT NULL | Top-up amount |
| payment_method | VARCHAR(20) | | Payment method: Cash, Card, Mobile |
| created_at | TIMESTAMP | DEFAULT NOW() | Creation timestamp |

**Indexes**:
- `idx_topups_user_id` ON topups(user_id)
- `idx_topups_date` ON topups(topup_date)
- `idx_topups_user_date` ON topups(user_id, topup_date)

**Foreign Keys**:
- `fk_topups_user` REFERENCES users(user_id)

## Data Warehouse Schema (Databricks Delta Lake)

### Staging Layer

The staging layer contains cleaned and standardized data from the operational database.

#### stg_users
- Source: `users` table
- Purpose: Cleaned user data
- Key transformations:
  - Standardize card_type values
  - Handle NULL values
  - Data type conversions

#### stg_stations
- Source: `stations` table
- Purpose: Cleaned station data
- Key transformations:
  - Validate coordinates
  - Standardize station names
  - Handle missing location data

#### stg_routes
- Source: `routes` table
- Purpose: Cleaned route data
- Key transformations:
  - Validate route relationships
  - Standardize route names

#### stg_transactions
- Source: `transactions` table
- Purpose: Cleaned transaction data
- Partition: `transaction_date`
- Key transformations:
  - Validate transaction amounts (must be positive)
  - Validate transaction times
  - Handle missing route_id
  - Data type conversions

#### stg_topups
- Source: `topups` table
- Purpose: Cleaned top-up data
- Partition: `topup_date`
- Key transformations:
  - Validate top-up amounts (minimum 10 RMB)
  - Standardize payment methods
  - Data type conversions

### Dimension Tables

#### dim_user
- Source: `stg_users`
- Materialization: Table
- Surrogate Key: `user_key` (generated)
- Natural Key: `user_id`
- Attributes:
  - user_key (surrogate key)
  - user_id
  - card_number
  - card_type
  - is_verified
  - created_at
  - updated_at

#### dim_station
- Source: `stg_stations`
- Materialization: Table
- Surrogate Key: `station_key` (generated)
- Natural Key: `station_id`
- Attributes:
  - station_key (surrogate key)
  - station_id
  - station_name
  - station_type
  - latitude
  - longitude
  - district

#### dim_route
- Source: `stg_routes`
- Materialization: Table
- Surrogate Key: `route_key` (generated)
- Natural Key: `route_id`
- Attributes:
  - route_key (surrogate key)
  - route_id
  - route_name
  - route_type
  - start_station_id
  - end_station_id

#### dim_time
- Source: Generated (using dbt-utils)
- Materialization: Table
- Surrogate Key: `date_key` (generated)
- Natural Key: `date_day`
- Attributes:
  - date_key (surrogate key)
  - date_day (date)
  - day_of_week (1-7)
  - day_name (Monday-Sunday)
  - week_number
  - month_number
  - month_name
  - quarter
  - year
  - is_weekend (boolean)
  - is_holiday (boolean, optional)

### Fact Tables

#### fact_transactions
- Source: `stg_transactions` joined with dimensions
- Materialization: Table (incremental)
- Partition: `transaction_date`
- Grain: One row per transaction
- Foreign Keys:
  - user_key → dim_user
  - station_key → dim_station
  - route_key → dim_route (nullable)
  - date_key → dim_time
- Measures:
  - transaction_amount
  - transaction_count (always 1)
- Attributes:
  - transaction_key (surrogate key)
  - transaction_id (natural key)
  - transaction_date
  - transaction_time
  - transaction_type

#### fact_topups
- Source: `stg_topups` joined with dimensions
- Materialization: Table (incremental)
- Partition: `topup_date`
- Grain: One row per top-up
- Foreign Keys:
  - user_key → dim_user
  - date_key → dim_time
- Measures:
  - topup_amount
  - topup_count (always 1)
- Attributes:
  - topup_key (surrogate key)
  - topup_id (natural key)
  - topup_date
  - topup_time
  - payment_method

### Marts (Business Metrics Tables)

#### daily_active_users
- Source: `fact_transactions`
- Materialization: Table
- Purpose: Daily active user metrics
- Columns:
  - date
  - active_users (COUNT DISTINCT user_key)
  - total_transactions
  - total_amount
  - avg_transaction_amount

#### daily_topup_summary
- Source: `fact_topups`
- Materialization: Table
- Purpose: Daily top-up summary
- Columns:
  - date
  - total_topups
  - total_amount
  - avg_topup_amount
  - unique_users

#### station_flow_daily
- Source: `fact_transactions`
- Materialization: Table
- Purpose: Daily station traffic
- Columns:
  - date
  - station_key
  - station_name
  - transaction_count
  - unique_users
  - total_amount

#### user_trip_history
- Source: `fact_transactions`
- Materialization: Table
- Purpose: User travel patterns
- Columns:
  - user_key
  - transaction_date
  - station_key
  - route_key
  - transaction_count
  - total_amount

#### user_retention
- Source: `fact_transactions`
- Materialization: Table
- Purpose: User retention analysis
- Columns:
  - cohort_month
  - period_number
  - active_users
  - retention_rate

## Entity Relationship Diagram

```
users (1) ────< (N) transactions
stations (1) ────< (N) transactions
routes (1) ────< (N) transactions
users (1) ────< (N) topups
routes (1) ────< (1) stations (start_station)
routes (1) ────< (1) stations (end_station)
```

## Data Flow

1. **Extract**: Data extracted from Supabase PostgreSQL
2. **Load**: Data loaded into Databricks staging tables (via Airbyte or custom script)
3. **Transform (Staging)**: Clean and standardize data in staging layer
4. **Transform (Dimensions)**: Build dimension tables with surrogate keys
5. **Transform (Facts)**: Build fact tables joining staging with dimensions
6. **Transform (Marts)**: Aggregate data into business metrics tables
7. **Visualize**: Power BI connects to marts tables for reporting

## Data Quality Considerations

1. **Referential Integrity**: All foreign keys must reference valid records
2. **Data Completeness**: Required fields must not be NULL
3. **Data Validity**: Values must be within acceptable ranges
4. **Data Consistency**: Same entity should have consistent attributes across tables
5. **Data Timeliness**: Data should be updated within acceptable time windows

## Performance Optimization

1. **Partitioning**: Fact tables partitioned by date for efficient querying
2. **Indexing**: Strategic indexes on foreign keys and frequently queried columns
3. **Materialization**: Use table materialization for frequently accessed marts
4. **Incremental Loading**: Use incremental models for fact tables
5. **Z-ordering**: Optimize Delta Lake tables with Z-ordering on frequently filtered columns


