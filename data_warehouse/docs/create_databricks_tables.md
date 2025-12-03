# Create Databricks Tables Guide
# 创建 Databricks 表结构指南

**Note**: Since you're using dbt Cloud, table creation will be handled by dbt models. This guide explains the table structure that dbt will create.

## Overview

With dbt Cloud, you don't need to manually create tables. dbt models will:
1. Read from source tables (synced by Airbyte)
2. Create staging views/tables (cleaned data)
3. Create dimension tables
4. Create fact tables (with partitioning)
5. Create marts tables (business metrics)

## Source Tables (Already Exist)

Airbyte has already created these tables in Databricks:
- `users`
- `stations`
- `routes`
- `transactions`
- `topups`

**Location**: `hive_metastore.shanghai_transport` (or your configured schema)

## Target Tables (Created by dbt)

dbt will create these tables automatically when you run `dbt run`:

### Staging Layer (Views or Tables)

Created by `dbt/models/staging/*.sql`:
- `stg_users` - Cleaned user data
- `stg_stations` - Cleaned station data
- `stg_routes` - Cleaned route data
- `stg_transactions` - Cleaned transaction data (partitioned by date)
- `stg_topups` - Cleaned top-up data (partitioned by date)

### Dimension Tables

Created by `dbt/models/dimensions/*.sql`:
- `dim_user` - User dimension with surrogate keys
- `dim_station` - Station dimension
- `dim_route` - Route dimension
- `dim_time` - Time dimension (date, week, month, etc.)

### Fact Tables

Created by `dbt/models/facts/*.sql`:
- `fact_transactions` - Transaction fact table (partitioned by transaction_date)
- `fact_topups` - Top-up fact table (partitioned by topup_date)

### Marts Tables

Created by `dbt/models/marts/*.sql`:
- `daily_active_users` - Daily active user metrics
- `daily_topup_summary` - Daily top-up summary
- `station_flow_daily` - Daily station traffic
- `user_trip_history` - User travel patterns
- `user_retention` - User retention analysis

## Table Creation Process

### Step 1: dbt Reads Source Tables

dbt models reference source tables using `{{ source() }}` function:

```sql
-- In staging models
SELECT * FROM {{ source('raw', 'users') }}
```

### Step 2: dbt Creates Staging Tables

dbt runs staging models to create cleaned data:

```bash
dbt run --select staging.*
```

### Step 3: dbt Creates Dimensions

dbt runs dimension models:

```bash
dbt run --select dimensions.*
```

### Step 4: dbt Creates Facts

dbt runs fact models (with incremental logic):

```bash
dbt run --select facts.*
```

### Step 5: dbt Creates Marts

dbt runs marts models:

```bash
dbt run --select marts.*
```

## Verification After dbt Run

After running dbt models, verify tables were created:

```sql
-- Check staging tables
SHOW TABLES IN hive_metastore.shanghai_transport LIKE 'stg_%';

-- Check dimension tables
SHOW TABLES IN hive_metastore.shanghai_transport LIKE 'dim_%';

-- Check fact tables
SHOW TABLES IN hive_metastore.shanghai_transport LIKE 'fact_%';

-- Check marts tables
SHOW TABLES IN hive_metastore.shanghai_transport LIKE 'daily_%';

-- Verify table structure
DESCRIBE EXTENDED hive_metastore.shanghai_transport.dim_user;
DESCRIBE EXTENDED hive_metastore.shanghai_transport.fact_transactions;

-- Check partitions (for fact tables)
SHOW PARTITIONS hive_metastore.shanghai_transport.fact_transactions;
```

## Table Properties

### Fact Tables (Partitioned)

Fact tables are partitioned by date for performance:

```sql
-- fact_transactions is partitioned by transaction_date
-- Each partition contains one day of data
-- This enables efficient querying by date range
```

### Delta Lake Features

All tables use Delta Lake format, which provides:
- ACID transactions
- Time travel (query historical versions)
- Schema evolution
- Optimized performance

## Manual Table Creation (Not Recommended)

If you need to manually create tables (not recommended with dbt), you can use the SQL in `sql/databricks_schema.sql` as reference. However, **dbt Cloud will handle this automatically**.

## Next Steps

1. ✅ Understand table structure
2. ✅ Set up dbt Cloud connection to Databricks
3. ➡️ Proceed to **Step 8: dbt Project Initialization** (see `dbt_setup.md`)

## Additional Resources

- [dbt Documentation](https://docs.getdbt.com/)
- [dbt Databricks Profile](https://docs.getdbt.com/reference/warehouse-profiles/databricks-profile)
- [Delta Lake Partitioning](https://docs.databricks.com/delta/partitioning.html)

