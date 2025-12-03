# dbt Dimension Models Guide
# dbt 维度表模型指南

This guide covers creating and running dimension models in dbt.

## Overview

Dimension models are the second transformation layer in the data warehouse. They:
- Add surrogate keys for better performance and flexibility
- Provide descriptive attributes for analysis
- Support slowly changing dimensions (SCD) if needed
- Are materialized as **tables** for query performance
- Form the foundation for fact tables and marts

## Dimension Models Created

### 1. dim_user
**Purpose**: User dimension with card information

**Key Features**:
- Surrogate key: `user_key` (hash of user_id)
- Business key: `user_id`
- Attributes: card_number, card_type, is_verified
- Timestamps: created_at, updated_at, dbt_updated_at

**Source**: `workspace.staging.stg_users`
**Target**: `workspace.dimensions.dim_user` (table)

**Use Cases**:
- User segmentation by card type
- Verified vs non-verified user analysis
- User cohort analysis

### 2. dim_station
**Purpose**: Station dimension with geographic information

**Key Features**:
- Surrogate key: `station_key` (hash of station_id)
- Business key: `station_id`
- Attributes: station_name, station_type, latitude, longitude
- Timestamps: created_at, dbt_updated_at

**Source**: `workspace.staging.stg_stations`
**Target**: `workspace.dimensions.dim_station` (table)

**Use Cases**:
- Station flow analysis
- Geographic analysis (heat maps)
- Station type comparison

### 3. dim_route
**Purpose**: Route/line dimension

**Key Features**:
- Surrogate key: `route_key` (hash of route_id)
- Business key: `route_id`
- Attributes: route_name, route_type
- Timestamps: created_at, dbt_updated_at

**Source**: `workspace.staging.stg_routes`
**Target**: `workspace.dimensions.dim_route` (table)

**Use Cases**:
- Route popularity analysis
- Route type comparison (Metro vs Bus)
- Route performance metrics

### 4. dim_time
**Purpose**: Time dimension with date attributes

**Key Features**:
- Surrogate key: `date_key` (YYYYMMDD format, e.g., 20240101)
- Date value: `date_day`
- Day attributes: day_of_week, day_of_week_name, day_of_month, day_of_year
- Week attributes: week_of_year
- Month attributes: month_number, month_name
- Quarter and year attributes
- Flags: is_weekend, is_holiday

**Source**: Generated using `dbt_utils.date_spine` (2024-01-01 to 2025-12-31)
**Target**: `workspace.dimensions.dim_time` (table)

**Use Cases**:
- Time-based analysis (daily, weekly, monthly trends)
- Weekend vs weekday comparison
- Seasonal analysis
- Holiday impact analysis

## Surrogate Keys

Surrogate keys are generated using `dbt_utils.generate_surrogate_key()`:

```sql
{{ dbt_utils.generate_surrogate_key(['user_id']) }} AS user_key
```

**Benefits**:
- Consistent key format across dimensions
- Better join performance (hash-based)
- Flexibility for slowly changing dimensions (SCD)
- Decouples dimension keys from source system keys

## Data Quality Tests

The `schema.yml` file defines tests for each dimension model:

### Common Tests
- **unique**: Ensures surrogate keys and business keys are unique
- **not_null**: Ensures required fields are not NULL
- **accepted_values**: Validates enum/categorical values

### Example Tests

**dim_user**:
- user_key: unique, not_null
- user_id: unique, not_null
- card_number: not_null
- card_type: not_null, accepted_values

**dim_time**:
- date_key: unique, not_null
- date_day: unique, not_null
- All date attributes: not_null

## Running Dimension Models

### Step 1: Navigate to dbt Directory

```bash
cd data_warehouse/dbt
```

### Step 2: Run All Dimension Models

```bash
dbt run --select dimensions.*
```

Expected output:
```
Running with dbt=1.7.0
Found 9 models, 25 tests, 0 snapshots, 0 analyses, 0 macros, 0 operations, 0 seed files, 5 sources, 0 exposures, 0 metrics

Concurrency: 4 threads (target='dev')

1 of 4 START sql table model dimensions.dim_user ..................... [RUN]
2 of 4 START sql table model dimensions.dim_station .................. [RUN]
3 of 4 START sql table model dimensions.dim_route .................... [RUN]
4 of 4 START sql table model dimensions.dim_time ..................... [RUN]
1 of 4 OK created sql table model dimensions.dim_user ................ [OK in 2.50s]
2 of 4 OK created sql table model dimensions.dim_station ............. [OK in 2.52s]
3 of 4 OK created sql table model dimensions.dim_route ............... [OK in 2.48s]
4 of 4 OK created sql table model dimensions.dim_time ................ [OK in 3.15s]

Completed successfully

Done. PASS=4 WARN=0 ERROR=0 SKIP=0 TOTAL=4
```

### Step 3: Run Tests

```bash
dbt test --select dimensions.*
```

This will run all tests defined in `schema.yml` for dimension models.

### Step 4: Run Staging and Dimensions Together

```bash
# Run staging first, then dimensions
dbt run --select staging.* dimensions.*

# Or use + to include dependencies
dbt run --select +dimensions.*
```

### Step 5: Verify Data

Query the dimension tables in Databricks:

```sql
-- Check row counts
SELECT 'dim_user' AS table_name, COUNT(*) AS row_count 
FROM workspace.dimensions.dim_user
UNION ALL
SELECT 'dim_station', COUNT(*) FROM workspace.dimensions.dim_station
UNION ALL
SELECT 'dim_route', COUNT(*) FROM workspace.dimensions.dim_route
UNION ALL
SELECT 'dim_time', COUNT(*) FROM workspace.dimensions.dim_time;

-- Sample data from dim_user
SELECT * FROM workspace.dimensions.dim_user LIMIT 10;

-- Check dim_time date range
SELECT 
    MIN(date_day) AS start_date,
    MAX(date_day) AS end_date,
    COUNT(*) AS total_days
FROM workspace.dimensions.dim_time;

-- Check weekend distribution
SELECT 
    is_weekend,
    COUNT(*) AS count
FROM workspace.dimensions.dim_time
GROUP BY is_weekend;

-- Check card type distribution
SELECT 
    card_type,
    COUNT(*) AS count
FROM workspace.dimensions.dim_user
GROUP BY card_type;
```

## Slowly Changing Dimensions (SCD)

Currently, dimension models use **Type 1 SCD** (overwrite):
- Updates overwrite existing records
- No history tracking

**Future Enhancement**: Implement Type 2 SCD for tracking history:
- Add `valid_from` and `valid_to` dates
- Add `is_current` flag
- Use dbt snapshots for history tracking

Example Type 2 SCD structure:
```sql
-- Future enhancement
CREATE TABLE dim_user_scd2 (
    user_key STRING,
    user_id INT,
    card_type STRING,
    valid_from DATE,
    valid_to DATE,
    is_current BOOLEAN
);
```

## Troubleshooting

### Error: dbt_utils not found

**Error**: `Compilation Error: dbt_utils.generate_surrogate_key is undefined`

**Solution**:
- Install dbt packages: `dbt deps`
- Verify `packages.yml` contains dbt_utils

### Error: date_spine fails

**Error**: `date_spine macro failed`

**Solution**:
- Ensure dbt_utils is installed
- Check date format in dim_time.sql
- Verify Databricks SQL syntax compatibility

### Error: Dimension table empty

**Error**: Dimension table created but has 0 rows

**Solution**:
- Check staging models have data: `SELECT COUNT(*) FROM workspace.staging.stg_users;`
- Run staging models first: `dbt run --select staging.*`
- Check for errors in dbt logs

### Performance Issues

**Issue**: Dimension models take too long to run

**Solutions**:
- Check Databricks cluster is running
- Increase cluster size if needed
- Add indexes on business keys (in Databricks)
- Use partitioning for large dimensions

## Best Practices

### 1. Use Surrogate Keys
- Always generate surrogate keys for dimensions
- Use consistent key generation method (hash-based)
- Keep business keys for reference

### 2. Add Metadata Columns
- Add `dbt_updated_at` timestamp
- Add `created_at` from source
- Consider adding `dbt_valid_from` for SCD Type 2

### 3. Document Attributes
- Document all columns in schema.yml
- Explain business meaning of attributes
- Document any transformations or calculations

### 4. Test Thoroughly
- Test surrogate key uniqueness
- Test business key uniqueness
- Test not_null for required fields
- Test accepted_values for categorical fields

### 5. Optimize for Queries
- Materialize as tables (not views)
- Add appropriate indexes in Databricks
- Consider partitioning for very large dimensions

## Next Steps

After dimension models are created and tested:

1. ✅ Verify all dimension models run successfully
2. ✅ Verify all tests pass
3. ✅ Check data quality in Databricks
4. ➡️ Proceed to **Step 11: Create Fact Models** (see `dbt_fact_models.md`)

## Additional Resources

- [dbt Dimensional Modeling](https://docs.getdbt.com/guides/best-practices/how-we-structure/4-marts)
- [Kimball Dimensional Modeling](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/)
- [dbt_utils Documentation](https://github.com/dbt-labs/dbt-utils)

