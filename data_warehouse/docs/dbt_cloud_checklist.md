# dbt Cloud Setup Checklist
# dbt Cloud 设置检查清单

Use this checklist to ensure you complete all steps for dbt Cloud setup.

## Pre-Setup Checklist

- [ ] dbt models tested locally and working
- [ ] All tests passing: `dbt test`
- [ ] Databricks connection details documented
- [ ] Databricks personal access token created
- [ ] SQL Warehouse running and accessible

## Step 1: Account Setup

- [ ] Created dbt Cloud account at https://cloud.getdbt.com
- [ ] Verified email address
- [ ] Created organization: "Shanghai Transport"
- [ ] Noted organization ID for reference

## Step 2: Project Setup

- [ ] Created new project: "Shanghai Transport DW"
- [ ] Connected Git repository (if using Git)
  - [ ] Authorized dbt Cloud to access repository
  - [ ] Selected correct repository
  - [ ] Set subdirectory: `data_warehouse/dbt`
- [ ] OR uploaded dbt project manually (if not using Git)
- [ ] Verified project files are visible in dbt Cloud

## Step 3: Connection Configuration

- [ ] Added Databricks connection
- [ ] Entered connection details:
  - [ ] Host: `your-workspace.cloud.databricks.com`
  - [ ] HTTP Path: `/sql/1.0/warehouses/...`
  - [ ] Catalog: `workspace`
  - [ ] Schema: `staging`
  - [ ] Token: Personal access token
- [ ] Tested connection successfully
- [ ] Saved connection

## Step 4: Environments

### Development Environment
- [ ] Created Development environment
- [ ] Selected Databricks connection
- [ ] Set dbt version: `1.7`
- [ ] Set threads: `4`
- [ ] Saved environment

### Production Environment
- [ ] Created Production environment
- [ ] Selected Databricks connection
- [ ] Set dbt version: `1.7`
- [ ] Set threads: `8`
- [ ] Set target name: `prod`
- [ ] Added environment variables (if needed)
- [ ] Saved environment

## Step 5: Job Configuration

- [ ] Created job: "Daily Pipeline - Production"
- [ ] Selected Production environment
- [ ] Added commands:
  - [ ] `dbt deps`
  - [ ] `dbt run --select staging+ dimensions+ facts+ marts+`
  - [ ] `dbt test`
- [ ] Set timeout: `60` minutes
- [ ] Enabled "Generate Docs"
- [ ] Configured schedule:
  - [ ] Cron: `0 2 * * *` (Daily at 2:00 AM UTC)
  - [ ] Verified timezone
- [ ] Set up notifications:
  - [ ] Email on failure
  - [ ] Slack on failure (optional)
- [ ] Saved job

## Step 6: Test Run

- [ ] Triggered manual run: "Run Now"
- [ ] Monitored run progress
- [ ] Verified all models completed: 16/16
- [ ] Verified all tests passed: 100/100
- [ ] Checked run duration (should be < 10 minutes)
- [ ] Reviewed logs for any warnings

## Step 7: Documentation

- [ ] Accessed documentation in dbt Cloud
- [ ] Verified data lineage graph displays correctly
- [ ] Checked all models are documented
- [ ] Verified column descriptions are visible
- [ ] Copied documentation URL
- [ ] Shared URL with team (optional)

## Step 8: Monitoring Setup

- [ ] Verified email notifications are working
- [ ] Verified Slack notifications are working (if configured)
- [ ] Added job to monitoring dashboard (optional)
- [ ] Documented job schedule in team calendar

## Step 9: First Scheduled Run

- [ ] Waited for first scheduled run (next day at 2:00 AM)
- [ ] Verified run completed successfully
- [ ] Checked notification was received
- [ ] Reviewed run duration and performance

## Step 10: Ongoing Maintenance

- [ ] Set calendar reminder to review job history weekly
- [ ] Documented troubleshooting steps for team
- [ ] Created runbook for common issues
- [ ] Scheduled monthly review of job performance

## Verification Queries

Run these queries in Databricks to verify everything is working:

```sql
-- 1. Check all schemas exist
SHOW SCHEMAS IN workspace;

-- Expected: staging, dimensions, facts, marts

-- 2. Check all models exist
SHOW TABLES IN workspace.staging;
SHOW TABLES IN workspace.dimensions;
SHOW TABLES IN workspace.facts;
SHOW TABLES IN workspace.marts;

-- Expected: 5 + 4 + 2 + 5 = 16 tables/views

-- 3. Check data freshness
SELECT 
    'staging' AS layer,
    'stg_transactions' AS model,
    MAX(created_at) AS last_updated
FROM workspace.staging.stg_transactions
UNION ALL
SELECT 
    'facts',
    'fact_transactions',
    MAX(created_at)
FROM workspace.facts.fact_transactions
UNION ALL
SELECT 
    'marts',
    'daily_active_users',
    MAX(date)
FROM workspace.marts.daily_active_users;

-- Expected: Recent timestamps (within last 24 hours)

-- 4. Check row counts
SELECT 
    'stg_transactions' AS table_name,
    COUNT(*) AS row_count
FROM workspace.staging.stg_transactions
UNION ALL
SELECT 
    'fact_transactions',
    COUNT(*)
FROM workspace.facts.fact_transactions
UNION ALL
SELECT 
    'daily_active_users',
    COUNT(*)
FROM workspace.marts.daily_active_users;

-- Expected: Non-zero counts, fact_transactions ≈ stg_transactions
```

## Success Criteria

✅ **Setup is successful if**:
- All checklist items are completed
- Manual test run completed successfully
- First scheduled run completed successfully
- Documentation is accessible and up-to-date
- Notifications are working
- All verification queries return expected results

## Troubleshooting

If any step fails, refer to:
- `docs/dbt_cloud_scheduling.md` - Detailed setup guide
- `docs/troubleshooting.md` - Common issues and solutions
- dbt Cloud support: https://docs.getdbt.com/docs/dbt-support

## Next Steps

After completing this checklist:
1. ✅ Monitor first week of scheduled runs
2. ✅ Optimize job performance if needed
3. ➡️ Proceed to Step 15: Power BI Connection and Reports
4. ➡️ Set up monitoring and alerts (Step 16)

## Notes

Use this space to document any custom configurations or issues encountered:

```
Date: ___________
Notes:
- 
- 
- 
```

