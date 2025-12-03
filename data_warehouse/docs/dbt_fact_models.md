# dbt Fact Models Guide
# dbt 事实表模型指南

This guide covers creating and running fact models in dbt.

## Overview

Fact models are the core of the data warehouse. They:
- Store measurable business events (transactions, top-ups)
- Link to dimension tables via foreign keys
- Contain measures (amounts, counts) for analysis
- Are partitioned by date for query performance
- Are materialized as **tables** for optimal performance

## Fact Models Created

### 1. fact_transactions
**Purpose**: Store all transaction events with full dimensional context

**Key Features**:
- Surrogate key: `transaction_key` (hash of transaction_id)
- Business key: `transaction_id`
- Dimension foreign keys:
  - `user_key` → dim_user
  - `station_key` → dim_station
  - `route_key` → dim_route
  - `date_key` → dim_time
- Degenerate dimensions: transaction_date, transaction_datetime
- Measures: amount
- Attributes: transaction_type
- Partitioned by: `transaction_date`

**Source**: `workspace.staging.stg_transactions`
**Target**: `workspace.facts.fact_transactions` (table, partitioned)

**Grain**: One row per transaction

**Use Cases**:
- Daily/weekly/monthly transaction analysis
- Station flow analysis
- Route usage analysis
- User behavior analysis
- Revenue analysis

### 2. fact_topups
**Purpose**: Store all top-up events with dimensional context

**Key Features**:
- Surrogate key: `topup_key` (hash of topup_id)
- Business key: `topup_id`
- Dimension foreign keys:
  - `user_key` → dim_user
  - `date_key` → dim_time
- Degenerate dimensions: topup_date, topup_datetime
- Measures: amount
- Attributes: payment_method
- Partitioned by: `topup_date`

**Source**: `workspace.staging.stg_topups`
**Target**: `workspace.facts.fact_topups` (table, partitioned)

**Grain**: One row per top-up

**Use Cases**:
- Top-up trend analysis
- Payment method analysis
- User recharge behavior
- Revenue forecasting

## Star Schema Design

The fact tables form the center of a star schema:

```
       dim_user
           |
           |
    dim_station --- fact_transactions --- dim_time
           |
           |
       dim_route


       dim_user
           |
           |
      fact_topups --- dim_time
```

## Partitioning Strategy

Both fact tables are partitioned by date:

**fact_transactions**: Partitioned by `transaction_date`
**fact_topups**: Partitioned by `topup_date`

**Benefits**:
- Faster queries with date filters
- Efficient data loading (only recent partitions)
- Better query performance for time-based analysis
- Easier data maintenance and archival

**Query Example**:
```sql
-- This query only scans one partition
SELECT * 
FROM workspace.facts.fact_transactions
WHERE transaction_date = '2024-01-15';
```

## Degenerate Dimensions

Degenerate dimensions are dimensional attributes stored in the fact table:

**fact_transactions**:
- `transaction_date` - For partitioning and filtering
- `transaction_datetime` - Full timestamp for detailed analysis
- `transaction_type` - Categorical attribute

**fact_topups**:
- `topup_date` - For partitioning and filtering
- `topup_datetime` - Full timestamp for detailed analysis
- `payment_method` - Categorical attribute

**Why store in fact table?**
- High cardinality (many unique values)
- Only used with this fact table
- Avoids creating unnecessary dimension tables

## Data Quality Tests

The `schema.yml` file defines tests for each fact model:

### Common Tests
- **unique**: Ensures surrogate keys and business keys are unique
- **not_null**: Ensures required fields are not NULL
- **relationships**: Validates foreign key relationships to dimensions
- **accepted_values**: Validates categorical values

### Example Tests

**fact_transactions**:
- transaction_key: unique, not_null
- transaction_id: unique, not_null
- user_key: not_null, relationships to dim_user
- station_key: relationships to dim_station
- route_key: relationships to dim_route
- date_key: not_null, relationships to dim_time
- amount: not_null
- transaction_type: not_null, accepted_values

**fact_topups**:
- topup_key: unique, not_null
- topup_id: unique, not_null
- user_key: not_null, relationships to dim_user
- date_key: not_null, relationships to dim_time
- amount: not_null
- payment_method: not_null, accepted_values

## Running Fact Models

### Step 1: Navigate to dbt Directory

```bash
cd data_warehouse/dbt
```

### Step 2: Run All Fact Models

```bash
dbt run --select facts.*
```

Expected output:
```
Running with dbt=1.7.0
Found 11 models, 40 tests, 0 snapshots, 0 analyses, 0 macros, 0 operations, 0 seed files, 5 sources, 0 exposures, 0 metrics

Concurrency: 4 threads (target='dev')

1 of 2 START sql table model facts.fact_transactions ................ [RUN]
2 of 2 START sql table model facts.fact_topups ...................... [RUN]
1 of 2 OK created sql table model facts.fact_transactions ........... [OK in 5.50s]
2 of 2 OK created sql table model facts.fact_topups ................. [OK in 5.25s]

Completed successfully

Done. PASS=2 WARN=0 ERROR=0 SKIP=0 TOTAL=2
```

### Step 3: Run Tests

```bash
dbt test --select facts.*
```

This will run all tests defined in `schema.yml` for fact models.

### Step 4: Run Full Pipeline (Staging → Dimensions → Facts)

```bash
# Run all models in dependency order
dbt run

# Or explicitly specify the order
dbt run --select staging.* dimensions.* facts.*
```

### Step 5: Verify Data

Query the fact tables in Databricks:

```sql
-- Check row counts
SELECT 'fact_transactions' AS table_name, COUNT(*) AS row_count 
FROM workspace.facts.fact_transactions
UNION ALL
SELECT 'fact_topups', COUNT(*) FROM workspace.facts.fact_topups;

-- Sample data from fact_transactions
SELECT * FROM workspace.facts.fact_transactions LIMIT 10;

-- Check transaction type distribution
SELECT 
    transaction_type,
    COUNT(*) AS count,
    SUM(amount) AS total_amount,
    AVG(amount) AS avg_amount
FROM workspace.facts.fact_transactions
GROUP BY transaction_type;

-- Check daily transaction volume
SELECT 
    transaction_date,
    COUNT(*) AS transaction_count,
    SUM(amount) AS total_amount
FROM workspace.facts.fact_transactions
GROUP BY transaction_date
ORDER BY transaction_date DESC
LIMIT 30;

-- Check top-up payment method distribution
SELECT 
    payment_method,
    COUNT(*) AS count,
    SUM(amount) AS total_amount,
    AVG(amount) AS avg_amount
FROM workspace.facts.fact_topups
GROUP BY payment_method;

-- Verify dimension joins
SELECT 
    u.card_type,
    s.station_type,
    COUNT(*) AS transaction_count,
    SUM(f.amount) AS total_amount
FROM workspace.facts.fact_transactions f
JOIN workspace.dimensions.dim_user u ON f.user_key = u.user_key
JOIN workspace.dimensions.dim_station s ON f.station_key = s.station_key
GROUP BY u.card_type, s.station_type;
```

### Step 6: Check Partitions

```sql
-- Check partitions for fact_transactions
SHOW PARTITIONS workspace.facts.fact_transactions;

-- Check partition sizes
SELECT 
    transaction_date,
    COUNT(*) AS row_count
FROM workspace.facts.fact_transactions
GROUP BY transaction_date
ORDER BY transaction_date;
```

## Performance Optimization

### 1. Partitioning
- Already implemented by date
- Queries with date filters will be faster
- Example: `WHERE transaction_date >= '2024-01-01'`

### 2. Clustering (Future Enhancement)
Add clustering for frequently filtered columns:

```sql
-- In Databricks
ALTER TABLE workspace.facts.fact_transactions
CLUSTER BY (user_key, station_key);
```

### 3. Z-Ordering (Databricks Specific)
Optimize for multiple filter columns:

```sql
OPTIMIZE workspace.facts.fact_transactions
ZORDER BY (user_key, station_key, transaction_type);
```

### 4. Incremental Models (Future Enhancement)
For large fact tables, use incremental materialization:

```sql
{{
    config(
        materialized='incremental',
        unique_key='transaction_id',
        incremental_strategy='merge'
    )
}}

-- Only process new/updated records
WHERE transaction_date > (SELECT MAX(transaction_date) FROM {{ this }})
```

## Troubleshooting

### Error: Dimension not found

**Error**: `Table or view not found: workspace.dimensions.dim_user`

**Solution**:
- Run dimension models first: `dbt run --select dimensions.*`
- Or run full pipeline: `dbt run --select +facts.*` (includes dependencies)

### Error: Relationship test failed

**Error**: `FAIL 1 relationships_fact_transactions_user_key__user_key__ref_dim_user_`

**Solution**:
- Check for orphaned records in staging tables
- Verify dimension tables are populated
- Investigate missing dimension records:
  ```sql
  SELECT DISTINCT t.user_id
  FROM workspace.staging.stg_transactions t
  LEFT JOIN workspace.dimensions.dim_user u ON t.user_id = u.user_id
  WHERE u.user_id IS NULL;
  ```

### Error: Partition creation failed

**Error**: `Cannot create partitioned table`

**Solution**:
- Verify Databricks supports partitioning (it does)
- Check partition column exists and is correct type
- Ensure partition column has valid values

### Performance Issues

**Issue**: Fact table queries are slow

**Solutions**:
- Check partitions are being used: `EXPLAIN SELECT ...`
- Add clustering or Z-ordering
- Optimize table: `OPTIMIZE workspace.facts.fact_transactions`
- Consider incremental materialization for large tables

## Best Practices

### 1. Define Clear Grain
- Each fact table should have a clear grain (one row per X)
- Document grain in schema.yml
- Ensure all measures are additive at that grain

### 2. Use Surrogate Keys
- Generate surrogate keys for fact records
- Keep business keys for reference
- Use consistent key generation method

### 3. Partition Large Tables
- Partition by date for time-series data
- Choose partition column based on query patterns
- Balance partition size (not too small, not too large)

### 4. Test Foreign Keys
- Always test relationships to dimensions
- Investigate and fix orphaned records
- Consider adding data quality checks in staging

### 5. Add Metadata
- Add dbt_updated_at timestamp
- Add created_at from source
- Consider adding data quality flags

### 6. Optimize for Queries
- Materialize as tables (not views)
- Use partitioning and clustering
- Run OPTIMIZE regularly in Databricks

## Next Steps

After fact models are created and tested:

1. ✅ Verify all fact models run successfully
2. ✅ Verify all tests pass
3. ✅ Check data quality in Databricks
4. ✅ Verify dimension joins work correctly
5. ➡️ Proceed to **Step 12: Create Marts Models** (see `dbt_marts_models.md`)

## Additional Resources

- [dbt Fact Tables](https://docs.getdbt.com/guides/best-practices/how-we-structure/4-marts)
- [Kimball Fact Tables](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/facts/)
- [Databricks Partitioning](https://docs.databricks.com/delta/table-properties.html)
- [Databricks Z-Ordering](https://docs.databricks.com/delta/data-skipping.html)

