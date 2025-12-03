# dbt Staging Models Guide
# dbt Staging 模型指南

This guide covers creating and running staging models in dbt.

## Overview

Staging models are the first transformation layer in the data warehouse. They:
- Clean and standardize raw data from source tables
- Apply basic data quality filters
- Standardize data types and formats
- Remove invalid or corrupted records
- Are materialized as **views** for efficiency

## Staging Models Created

### 1. stg_users
**Purpose**: Clean user and card data

**Transformations**:
- Trim whitespace from card_type
- Set default value for is_verified (FALSE if NULL)
- Filter out records with NULL primary/required fields

**Source**: `workspace.public.users`
**Target**: `workspace.staging.stg_users` (view)

### 2. stg_stations
**Purpose**: Clean station data

**Transformations**:
- Trim whitespace from station_name and station_type
- Cast coordinates to DECIMAL(10, 6)
- Validate Shanghai coordinate ranges (lat: 30-32, lon: 120-122)
- Filter out records with invalid coordinates

**Source**: `workspace.public.stations`
**Target**: `workspace.staging.stg_stations` (view)

### 3. stg_routes
**Purpose**: Clean route/line data

**Transformations**:
- Trim whitespace from route_name and route_type
- Filter out records with NULL required fields

**Source**: `workspace.public.routes`
**Target**: `workspace.staging.stg_routes` (view)

### 4. stg_transactions
**Purpose**: Clean transaction data

**Transformations**:
- Cast transaction_date to DATE
- Cast transaction_time to TIMESTAMP
- Create transaction_datetime by combining date and time
- Cast amount to DECIMAL(10, 2)
- Filter out records with:
  - NULL required fields
  - Invalid dates (before 2024-01-01)
  - Negative amounts
- Trim whitespace from transaction_type

**Source**: `workspace.public.transactions`
**Target**: `workspace.staging.stg_transactions` (view)

### 5. stg_topups
**Purpose**: Clean top-up data

**Transformations**:
- Cast topup_date to DATE
- Cast topup_time to TIMESTAMP
- Create topup_datetime by combining date and time
- Cast amount to DECIMAL(10, 2)
- Filter out records with:
  - NULL required fields
  - Invalid dates (before 2024-01-01)
  - Non-positive amounts (must be > 0)
- Trim whitespace from payment_method

**Source**: `workspace.public.topups`
**Target**: `workspace.staging.stg_topups` (view)

## Data Quality Tests

The `schema.yml` file defines tests for each staging model:

### Common Tests
- **unique**: Ensures primary keys are unique
- **not_null**: Ensures required fields are not NULL
- **accepted_values**: Validates enum/categorical values
- **relationships**: Validates foreign key relationships

### Example Tests

**stg_users**:
- user_id: unique, not_null
- card_number: not_null
- card_type: not_null, accepted_values
- is_verified: not_null

**stg_transactions**:
- transaction_id: unique, not_null
- user_id: not_null, relationships to stg_users
- station_id: relationships to stg_stations
- route_id: relationships to stg_routes
- transaction_date: not_null
- amount: not_null
- transaction_type: not_null, accepted_values

## Running Staging Models

### Step 1: Navigate to dbt Directory

```bash
cd data_warehouse/dbt
```

### Step 2: Run All Staging Models

```bash
dbt run --select staging.*
```

Expected output:
```
Running with dbt=1.7.0
Found 5 models, 0 tests, 0 snapshots, 0 analyses, 0 macros, 0 operations, 0 seed files, 5 sources, 0 exposures, 0 metrics

Concurrency: 4 threads (target='dev')

1 of 5 START sql view model staging.stg_users ........................ [RUN]
2 of 5 START sql view model staging.stg_stations ..................... [RUN]
3 of 5 START sql view model staging.stg_routes ....................... [RUN]
1 of 5 OK created sql view model staging.stg_users ................... [OK in 0.50s]
2 of 5 OK created sql view model staging.stg_stations ................ [OK in 0.52s]
3 of 5 OK created sql view model staging.stg_routes .................. [OK in 0.48s]
4 of 5 START sql view model staging.stg_transactions ................. [RUN]
5 of 5 START sql view model staging.stg_topups ....................... [RUN]
4 of 5 OK created sql view model staging.stg_transactions ............ [OK in 0.55s]
5 of 5 OK created sql view model staging.stg_topups .................. [OK in 0.53s]

Completed successfully

Done. PASS=5 WARN=0 ERROR=0 SKIP=0 TOTAL=5
```

### Step 3: Run Tests

```bash
dbt test --select staging.*
```

This will run all tests defined in `schema.yml` for staging models.

Expected output:
```
Running with dbt=1.7.0
Found 5 models, 25 tests, 0 snapshots, 0 analyses, 0 macros, 0 operations, 0 seed files, 5 sources, 0 exposures, 0 metrics

Concurrency: 4 threads (target='dev')

1 of 25 START test not_null_stg_users_user_id ........................ [RUN]
2 of 25 START test unique_stg_users_user_id .......................... [RUN]
...
25 of 25 OK passed .............................................. [PASS in 0.45s]

Completed successfully

Done. PASS=25 WARN=0 ERROR=0 SKIP=0 TOTAL=25
```

### Step 4: Run Specific Model

```bash
# Run single model
dbt run --select stg_users

# Run model and its downstream dependencies
dbt run --select stg_users+

# Run model and its upstream dependencies
dbt run --select +stg_users
```

### Step 5: Verify Data

Query the staging views in Databricks:

```sql
-- Check row counts
SELECT 'stg_users' AS table_name, COUNT(*) AS row_count FROM workspace.staging.stg_users
UNION ALL
SELECT 'stg_stations', COUNT(*) FROM workspace.staging.stg_stations
UNION ALL
SELECT 'stg_routes', COUNT(*) FROM workspace.staging.stg_routes
UNION ALL
SELECT 'stg_transactions', COUNT(*) FROM workspace.staging.stg_transactions
UNION ALL
SELECT 'stg_topups', COUNT(*) FROM workspace.staging.stg_topups;

-- Sample data from stg_transactions
SELECT * FROM workspace.staging.stg_transactions LIMIT 10;

-- Check data quality
SELECT 
    transaction_type,
    COUNT(*) AS count,
    MIN(amount) AS min_amount,
    MAX(amount) AS max_amount,
    AVG(amount) AS avg_amount
FROM workspace.staging.stg_transactions
GROUP BY transaction_type;
```

## Troubleshooting

### Error: Source not found

**Error**: `Source 'raw.users' not found`

**Solution**:
- Verify source tables exist in `workspace.public`
- Check `models/sources.yml` configuration
- Run `dbt debug` to verify connection

### Error: Schema not found

**Error**: `Schema 'workspace.staging' not found`

**Solution**:
- Create schema: `CREATE SCHEMA IF NOT EXISTS workspace.staging;`
- Or run `python scripts/create_schemas.py`

### Error: Test failed

**Error**: `FAIL 1 not_null_stg_transactions_amount`

**Solution**:
- Check source data quality
- Review staging model SQL filters
- Investigate failed records:
  ```sql
  SELECT * FROM workspace.public.transactions WHERE amount IS NULL;
  ```

### Error: Relationship test failed

**Error**: `FAIL 1 relationships_stg_transactions_user_id__user_id__ref_stg_users_`

**Solution**:
- Ensure parent model (stg_users) runs before child model (stg_transactions)
- Check for orphaned records in source data
- Run models in order: `dbt run --select stg_users stg_transactions`

## Best Practices

### 1. Keep Staging Models Simple
- Focus on cleaning and standardization
- Avoid complex business logic
- Don't join tables (do that in dimension/fact models)

### 2. Use Consistent Naming
- Prefix all staging models with `stg_`
- Use singular table names (e.g., `stg_user`, not `stg_users`)
- Match source table names

### 3. Document Everything
- Add descriptions to models and columns in `schema.yml`
- Document data quality assumptions
- Explain transformation logic in SQL comments

### 4. Test Thoroughly
- Add tests for all primary keys (unique, not_null)
- Add tests for foreign keys (relationships)
- Add tests for categorical fields (accepted_values)
- Add custom tests for business rules

### 5. Filter Invalid Data
- Remove records with NULL required fields
- Filter out invalid dates/times
- Validate numeric ranges
- Trim whitespace from strings

## Next Steps

After staging models are created and tested:

1. ✅ Verify all staging models run successfully
2. ✅ Verify all tests pass
3. ✅ Check data quality in Databricks
4. ➡️ Proceed to **Step 10: Create Dimension Models** (see `dbt_dimension_models.md`)

## Additional Resources

- [dbt Staging Best Practices](https://docs.getdbt.com/guides/best-practices/how-we-structure/2-staging)
- [dbt Tests](https://docs.getdbt.com/docs/build/tests)
- [dbt Jinja Reference](https://docs.getdbt.com/reference/dbt-jinja-functions)

