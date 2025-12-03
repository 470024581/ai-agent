# dbt Cloud Quick Start Guide
# dbt Cloud 快速开始指南

This is a simplified guide to get started with dbt Cloud quickly.

## 5-Minute Setup

### 1. Create Account (2 minutes)

1. Go to https://cloud.getdbt.com
2. Click "Start Free Trial"
3. Sign up with email or Google/GitHub
4. Create organization: "Shanghai Transport"

### 2. Create Project (1 minute)

1. Click "New Project"
2. Name: "Shanghai Transport DW"
3. Choose setup method:
   - **With Git**: Connect GitHub/GitLab repository
   - **Without Git**: Upload `data_warehouse/dbt` folder as zip

### 3. Configure Connection (2 minutes)

1. Click "Add Connection" → "Databricks"
2. Fill in (get from `.env` file):
   ```
   Host: [DATABRICKS_SERVER_HOSTNAME]
   HTTP Path: [DATABRICKS_HTTP_PATH]
   Token: [DATABRICKS_TOKEN]
   Catalog: workspace
   Schema: staging
   ```
3. Click "Test Connection" → Should see ✅
4. Click "Save"

## 10-Minute Full Setup

### 4. Create Environments (3 minutes)

**Development**:
- Name: `Development`
- Type: Development
- Connection: Databricks
- dbt Version: `1.7`
- Threads: `4`

**Production**:
- Name: `Production`
- Type: Deployment
- Connection: Databricks
- dbt Version: `1.7`
- Threads: `8`

### 5. Create Job (5 minutes)

1. Click "Jobs" → "Create Job"
2. Name: `Daily Pipeline - Production`
3. Environment: `Production`
4. Commands:
   ```bash
   dbt deps
   dbt run --select staging+ dimensions+ facts+ marts+
   dbt test
   ```
5. Schedule: `0 2 * * *` (Daily at 2:00 AM)
6. Notifications: Enable "Email on Failure"
7. Click "Save"

### 6. Test Run (2 minutes)

1. Click "Run Now"
2. Wait for completion (~5-10 minutes)
3. Verify: ✅ All models completed, ✅ All tests passed

## What You Get

After setup, you automatically get:

✅ **Automated Daily Runs**
- Runs every day at 2:00 AM UTC
- Refreshes all data warehouse layers
- Runs all data quality tests

✅ **Hosted Documentation**
- Data lineage graph (DAG)
- Model and column descriptions
- Always up-to-date
- Shareable URL

✅ **Monitoring & Alerts**
- Email notifications on failure
- Job history and logs
- Performance metrics

✅ **No Infrastructure**
- No servers to manage
- No maintenance required
- Automatic scaling

## Quick Reference

### View Documentation
1. Go to dbt Cloud
2. Click "Documentation"
3. Share URL with team

### View Job History
1. Go to "Jobs"
2. Click "Daily Pipeline - Production"
3. See all past runs

### Trigger Manual Run
1. Go to "Jobs"
2. Click "Run Now"
3. Monitor progress

### Check Run Logs
1. Click on any run
2. View real-time logs
3. Debug issues

## Troubleshooting

### Connection Failed
- ✅ Check SQL Warehouse is running
- ✅ Verify token is valid
- ✅ Test in Databricks SQL Editor

### Job Failed
- ✅ Click on failed run
- ✅ Review error message
- ✅ Check logs for details

### Tests Failed
- ✅ Click on failed test
- ✅ Run test SQL in Databricks
- ✅ Investigate data quality

## Next Steps

1. ✅ Wait for first scheduled run (tomorrow at 2:00 AM)
2. ✅ Verify run completed successfully
3. ✅ Review documentation
4. ➡️ Connect Power BI (Step 15)

## Need Help?

- 📖 Detailed Guide: `docs/dbt_cloud_scheduling.md`
- ✅ Checklist: `docs/dbt_cloud_checklist.md`
- 🔧 Troubleshooting: `docs/troubleshooting.md`
- 💬 dbt Docs: https://docs.getdbt.com/docs/dbt-cloud

