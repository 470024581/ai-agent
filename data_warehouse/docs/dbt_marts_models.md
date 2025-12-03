# dbt Marts Models Guide
# dbt Marts 汇总表模型指南

This guide covers creating and running marts models in dbt.

## Overview

Marts models are the final transformation layer in the data warehouse. They:
- Provide business-ready metrics and KPIs
- Pre-aggregate data for fast dashboard queries
- Answer specific business questions
- Are optimized for end-user consumption
- Are materialized as **tables** for query performance

Marts models are the layer that Power BI and other BI tools connect to.

## Marts Models Created

### 1. daily_active_users
**Purpose**: Daily user activity metrics and trends

**Key Metrics**:
- Active users (unique count)
- Total transactions
- Total amount
- Average transactions per user
- Average amount per transaction
- Entry/exit transaction breakdown
- Weekend flag

**Grain**: One row per date

**Source**: `fact_transactions` + `dim_time`
**Target**: `workspace.marts.daily_active_users` (table)

**Business Questions Answered**:
- How many users are active each day?
- What's the daily transaction volume?
- How does activity differ on weekends vs weekdays?
- What's the average user engagement?

**Example Query**:
```sql
-- Last 30 days active users trend
SELECT 
    date,
    active_users,
    total_transactions,
    avg_transactions_per_user
FROM workspace.marts.daily_active_users
WHERE date >= CURRENT_DATE - INTERVAL 30 DAYS
ORDER BY date DESC;
```

### 2. daily_topup_summary
**Purpose**: Daily top-up metrics with payment method breakdown

**Key Metrics**:
- Total top-ups
- Unique users who topped up
- Total amount
- Average amount per top-up
- Average amount per user
- Payment method breakdown (Cash, Card, Mobile, Online)
- Weekend flag

**Grain**: One row per date

**Source**: `fact_topups` + `dim_time`
**Target**: `workspace.marts.daily_topup_summary` (table)

**Business Questions Answered**:
- What's the daily top-up volume?
- Which payment methods are most popular?
- How does top-up behavior differ on weekends?
- What's the average top-up amount?

**Example Query**:
```sql
-- Top-up trends by payment method
SELECT 
    date,
    total_topups,
    cash_topups,
    card_topups,
    mobile_topups,
    online_topups
FROM workspace.marts.daily_topup_summary
WHERE date >= CURRENT_DATE - INTERVAL 30 DAYS
ORDER BY date DESC;
```

### 3. station_flow_daily
**Purpose**: Daily station traffic metrics

**Key Metrics**:
- Total transactions per station
- Unique users per station
- Entry/exit breakdown
- Total amount
- Station attributes (name, type)
- Weekend flag

**Grain**: One row per date per station

**Source**: `fact_transactions` + `dim_station` + `dim_time`
**Target**: `workspace.marts.station_flow_daily` (table)

**Business Questions Answered**:
- Which stations are busiest?
- How does traffic vary by day of week?
- What's the entry/exit ratio at each station?
- Which station types have highest usage?

**Example Query**:
```sql
-- Top 10 busiest stations yesterday
SELECT 
    station_name,
    station_type,
    total_transactions,
    unique_users,
    entry_count,
    exit_count
FROM workspace.marts.station_flow_daily
WHERE date = CURRENT_DATE - INTERVAL 1 DAY
ORDER BY total_transactions DESC
LIMIT 10;
```

### 4. user_card_type_summary
**Purpose**: User segmentation by card type

**Key Metrics**:
- Total users per card type
- Verified users count
- Total transactions
- Total transaction amount
- Average transactions per user
- Total top-ups
- Total top-up amount
- Average top-up per user

**Grain**: One row per card type

**Source**: `dim_user` + `fact_transactions` + `fact_topups`
**Target**: `workspace.marts.user_card_type_summary` (table)

**Business Questions Answered**:
- How do different card types compare in usage?
- Which card type has highest engagement?
- What's the verification rate by card type?
- How do top-up patterns differ by card type?

**Example Query**:
```sql
-- Card type comparison
SELECT 
    card_type,
    total_users,
    verified_users,
    avg_transactions_per_user,
    avg_topup_per_user
FROM workspace.marts.user_card_type_summary
ORDER BY total_users DESC;
```

### 5. route_usage_summary
**Purpose**: Route popularity and usage metrics

**Key Metrics**:
- Total transactions per route
- Unique users per route
- Total amount
- Average transactions per day
- First and last transaction dates
- Route attributes (name, type)

**Grain**: One row per route

**Source**: `fact_transactions` + `dim_route`
**Target**: `workspace.marts.route_usage_summary` (table)

**Business Questions Answered**:
- Which routes are most popular?
- How do Metro vs Bus routes compare?
- What's the daily usage pattern for each route?
- Which routes have highest revenue?

**Example Query**:
```sql
-- Top 10 most popular routes
SELECT 
    route_name,
    route_type,
    total_transactions,
    unique_users,
    avg_transactions_per_day
FROM workspace.marts.route_usage_summary
ORDER BY total_transactions DESC
LIMIT 10;
```

## Data Quality Tests

The `schema.yml` file defines tests for each marts model:

### Common Tests
- **unique**: Ensures grain is maintained (e.g., one row per date)
- **not_null**: Ensures required fields are not NULL
- **Data consistency**: Metrics should be >= 0

## Running Marts Models

### Step 1: Navigate to dbt Directory

```bash
cd data_warehouse/dbt
```

### Step 2: Run All Marts Models

```bash
dbt run --select marts.*
```

Expected output:
```
Running with dbt=1.7.0
Found 16 models, 60 tests, 0 snapshots, 0 analyses, 0 macros, 0 operations, 0 seed files, 5 sources, 0 exposures, 0 metrics

Concurrency: 4 threads (target='dev')

1 of 5 START sql table model marts.daily_active_users ............... [RUN]
2 of 5 START sql table model marts.daily_topup_summary .............. [RUN]
3 of 5 START sql table model marts.station_flow_daily ............... [RUN]
4 of 5 START sql table model marts.user_card_type_summary ........... [RUN]
5 of 5 START sql table model marts.route_usage_summary .............. [RUN]
1 of 5 OK created sql table model marts.daily_active_users .......... [OK in 3.50s]
2 of 5 OK created sql table model marts.daily_topup_summary ......... [OK in 3.45s]
3 of 5 OK created sql table model marts.station_flow_daily .......... [OK in 4.20s]
4 of 5 OK created sql table model marts.user_card_type_summary ...... [OK in 3.80s]
5 of 5 OK created sql table model marts.route_usage_summary ......... [OK in 3.60s]

Completed successfully

Done. PASS=5 WARN=0 ERROR=0 SKIP=0 TOTAL=5
```

### Step 3: Run Tests

```bash
dbt test --select marts.*
```

### Step 4: Run Full Pipeline

```bash
# Run all models in dependency order
dbt run

# Run all tests
dbt test
```

### Step 5: Verify Data

Query the marts tables in Databricks:

```sql
-- Check row counts
SELECT 'daily_active_users' AS table_name, COUNT(*) AS row_count 
FROM workspace.marts.daily_active_users
UNION ALL
SELECT 'daily_topup_summary', COUNT(*) FROM workspace.marts.daily_topup_summary
UNION ALL
SELECT 'station_flow_daily', COUNT(*) FROM workspace.marts.station_flow_daily
UNION ALL
SELECT 'user_card_type_summary', COUNT(*) FROM workspace.marts.user_card_type_summary
UNION ALL
SELECT 'route_usage_summary', COUNT(*) FROM workspace.marts.route_usage_summary;

-- Sample daily active users
SELECT * FROM workspace.marts.daily_active_users
ORDER BY date DESC LIMIT 10;

-- Card type comparison
SELECT * FROM workspace.marts.user_card_type_summary
ORDER BY total_users DESC;

-- Top stations by traffic
SELECT 
    station_name,
    SUM(total_transactions) AS total_transactions
FROM workspace.marts.station_flow_daily
GROUP BY station_name
ORDER BY total_transactions DESC
LIMIT 10;
```

## Performance Optimization

### 1. Pre-Aggregation
- Marts tables are pre-aggregated for fast queries
- No need to aggregate in Power BI or other BI tools
- Queries return results instantly

### 2. Materialization
- All marts materialized as tables (not views)
- Tables are refreshed on schedule (e.g., daily)
- Balance freshness vs query performance

### 3. Incremental Updates (Future Enhancement)
For large marts, consider incremental updates:

```sql
{{
    config(
        materialized='incremental',
        unique_key='date'
    )
}}

-- Only process new dates
WHERE date > (SELECT MAX(date) FROM {{ this }})
```

## Troubleshooting

### Error: Fact table not found

**Error**: `Table or view not found: workspace.facts.fact_transactions`

**Solution**:
- Run fact models first: `dbt run --select facts.*`
- Or run full pipeline: `dbt run`

### Error: Division by zero

**Error**: `Division by zero in avg_transactions_per_user`

**Solution**:
- Add NULL handling in SQL:
  ```sql
  CASE 
    WHEN COUNT(DISTINCT user_key) > 0 
    THEN COUNT(*) / COUNT(DISTINCT user_key)
    ELSE 0 
  END AS avg_transactions_per_user
  ```

### Performance Issues

**Issue**: Marts queries are slow

**Solutions**:
- Check fact tables have data
- Verify joins are efficient
- Add indexes in Databricks (if needed)
- Consider partitioning large marts tables

## Best Practices

### 1. Design for Business Users
- Use clear, business-friendly column names
- Pre-calculate complex metrics
- Document what each metric means

### 2. Optimize for Common Queries
- Identify most common dashboard queries
- Pre-aggregate at appropriate grain
- Balance granularity vs performance

### 3. Keep Marts Simple
- Each marts table should answer specific questions
- Avoid overly complex joins or calculations
- Consider creating multiple simple marts vs one complex mart

### 4. Document Metrics
- Document calculation logic in schema.yml
- Explain business meaning of each metric
- Provide example queries

### 5. Test Data Quality
- Add tests for key metrics
- Ensure metrics are consistent across marts
- Validate against known totals

## Next Steps

After marts models are created and tested:

1. ✅ Verify all marts models run successfully
2. ✅ Verify all tests pass
3. ✅ Check data quality in Databricks
4. ✅ Validate metrics against business expectations
5. ➡️ Proceed to **Step 13: dbt Tests and Documentation** (see `dbt_tests.md`)

## Power BI Integration

These marts tables are ready for Power BI:

**Connection Setup**:
1. In Power BI Desktop, select "Get Data" > "Databricks"
2. Connect to `workspace.marts` schema
3. Import marts tables (or use DirectQuery)

**Recommended Tables for Power BI**:
- `daily_active_users` - For time-series dashboards
- `daily_topup_summary` - For revenue dashboards
- `station_flow_daily` - For geographic/station dashboards
- `user_card_type_summary` - For user segmentation
- `route_usage_summary` - For route analysis

**Dashboard Ideas**:
- Daily active users trend line
- Top-up revenue by payment method (pie chart)
- Station heat map (using latitude/longitude from dim_station)
- Card type comparison (bar chart)
- Route popularity ranking (table)

## Additional Resources

- [dbt Marts Best Practices](https://docs.getdbt.com/guides/best-practices/how-we-structure/4-marts)
- [Kimball Dimensional Modeling](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/)
- [Power BI Databricks Connector](https://docs.microsoft.com/en-us/power-bi/connect-data/desktop-connect-databricks)

