# dbt Cloud Scheduling Guide
# dbt Cloud 调度配置指南

This guide covers setting up dbt Cloud for scheduling and automating your dbt pipeline.

## Prerequisites

- ✅ dbt models created and tested locally (Steps 8-13 completed)
- ✅ Databricks connection configured
- ✅ dbt Cloud account created
- ✅ Environment variables documented

## Overview

dbt Cloud provides:
- Automated scheduling
- Built-in documentation hosting
- Job monitoring and alerts
- Integrated development environment (IDE)
- Version control integration

## Step 1: Create dbt Cloud Account

### 1.1 Sign Up

1. Visit https://cloud.getdbt.com
2. Click "Start Free Trial" or "Sign Up"
3. Choose authentication method:
   - Email/Password
   - Google
   - GitHub

### 1.2 Create Organization

1. Enter organization name: `Shanghai Transport`
2. Choose region: `US` or `EMEA` (closest to your Databricks)
3. Click "Create Organization"

### 1.3 Free Tier Limits

**Developer Plan (Free)**:
- 1 developer seat
- Unlimited read-only users
- 1 project
- 3,000 model runs/month
- Community support

**Sufficient for this project**: ✅

## Step 2: Create Project

### 2.1 Project Setup

1. Click "New Project"
2. Enter project name: `Shanghai Transport DW`
3. Click "Continue"

### 2.2 Connect Repository (Option A: Git - Recommended)

**If you have GitHub/GitLab repository**:

1. Click "Git Repository"
2. Choose provider: GitHub or GitLab
3. Authorize dbt Cloud to access your repository
4. Select repository: `your-username/ai-agent`
5. Set subdirectory: `data_warehouse/dbt`
6. Click "Continue"

**Benefits**:
- Version control
- Collaboration
- Automatic sync
- Code review workflow

### 2.3 Manual Upload (Option B: No Git)

**If you don't have Git repository**:

1. Click "Upload Project"
2. Zip your dbt project:
   ```bash
   cd data_warehouse
   zip -r dbt_project.zip dbt/
   ```
3. Upload `dbt_project.zip`
4. Click "Continue"

**Note**: You'll need to re-upload for any changes

## Step 3: Configure Connection

### 3.1 Add Databricks Connection

1. In project settings, click "Connections"
2. Click "Add Connection"
3. Select "Databricks"

### 3.2 Connection Details

Fill in the following information:

**Connection Name**: `Databricks Production`

**Account Settings**:
- **Host**: Your Databricks workspace URL
  - Example: `your-workspace.cloud.databricks.com`
  - Get from: Databricks → Settings → Workspace Settings
  
- **HTTP Path**: SQL Warehouse HTTP path
  - Example: `/sql/1.0/warehouses/abc123def456`
  - Get from: Databricks → SQL Warehouses → Your Warehouse → Connection Details
  
- **Catalog**: `workspace`
  
- **Schema**: `staging` (default, will be overridden by models)

**Authentication**:
- **Method**: Personal Access Token
- **Token**: Your Databricks personal access token
  - Get from: Databricks → User Settings → Access Tokens → Generate New Token
  - ⚠️ Save token securely, it's only shown once

**Advanced Settings** (Optional):
- **Connection Timeout**: `10` seconds
- **Retry Attempts**: `3`

### 3.3 Test Connection

1. Click "Test Connection"
2. Wait for success message: ✅ "Connection successful"
3. If failed, verify:
   - SQL Warehouse is running
   - Token is valid
   - Network connectivity

### 3.4 Save Connection

1. Click "Save"
2. Connection is now available for environments

## Step 4: Create Environments

### 4.1 Development Environment

**Purpose**: For development and testing

1. Click "Environments" in left sidebar
2. Click "Create Environment"
3. Configure:
   - **Name**: `Development`
   - **Type**: Development
   - **Connection**: Select "Databricks Production"
   - **Deployment Credentials**: Use your personal token
   - **dbt Version**: `1.7` (latest stable)
   - **Threads**: `4`

4. Click "Save"

### 4.2 Production Environment

**Purpose**: For scheduled production runs

1. Click "Create Environment"
2. Configure:
   - **Name**: `Production`
   - **Type**: Deployment
   - **Connection**: Select "Databricks Production"
   - **Deployment Credentials**: 
     - Option A: Use service account token (recommended)
     - Option B: Use your personal token
   - **dbt Version**: `1.7`
   - **Threads**: `8` (more threads for production)
   - **Target Name**: `prod`

3. **Environment Variables** (Optional):
   - Add if you use environment variables in profiles.yml
   - Example: `DATABRICKS_TOKEN`, `DATABRICKS_SERVER_HOSTNAME`

4. Click "Save"

## Step 5: Create Job

### 5.1 Create Production Job

1. Click "Jobs" in left sidebar
2. Click "Create Job"
3. Configure job settings:

**Job Name**: `Daily Pipeline - Production`

**Environment**: Select "Production"

**Commands**:
```bash
dbt deps
dbt run --select staging+ dimensions+ facts+ marts+
dbt test
```

**Explanation**:
- `dbt deps`: Install dbt packages (dbt_utils)
- `dbt run --select staging+ dimensions+ facts+ marts+`: Run all models in order
- `dbt test`: Run all tests

### 5.2 Advanced Settings

**Execution Settings**:
- **Run Timeout**: `60` minutes
- **Target Name**: `prod` (matches environment)
- **Threads**: `8`
- **Generate Docs**: ✅ Enable (automatically generate documentation)

**Run on Source Freshness**: ❌ Disable (we don't have source freshness checks yet)

**Defer to Previous Run**: ❌ Disable (for now)

### 5.3 Triggers

**Schedule**:
1. Click "Add Trigger"
2. Select "Schedule"
3. Configure:
   - **Run on Schedule**: ✅ Enable
   - **Cron Schedule**: `0 2 * * *` (Daily at 2:00 AM UTC)
   - Or use UI: "Every day at 2:00 AM"
   - **Timezone**: UTC (or your preferred timezone)

**Custom Cron Examples**:
- `0 2 * * *` - Daily at 2:00 AM
- `0 */6 * * *` - Every 6 hours
- `0 2 * * 1-5` - Weekdays at 2:00 AM
- `0 2 1 * *` - Monthly on 1st at 2:00 AM

**Git Trigger** (if using Git):
- ❌ Disable for production (only run on schedule)
- ✅ Enable for development (run on every commit)

### 5.4 Notifications

**Email Notifications**:
1. Click "Notifications"
2. Configure:
   - **On Success**: ✅ Enable (optional)
   - **On Failure**: ✅ Enable (recommended)
   - **Recipients**: Your email address

**Slack Notifications** (Optional):
1. Click "Add Slack Integration"
2. Authorize dbt Cloud to access Slack
3. Select Slack channel: `#data-alerts`
4. Configure:
   - **On Success**: ❌ Disable (reduce noise)
   - **On Failure**: ✅ Enable
   - **On Cancel**: ✅ Enable

### 5.5 Save Job

1. Review all settings
2. Click "Save"
3. Job is now created and scheduled

## Step 6: Manual Test Run

### 6.1 Trigger Manual Run

1. Go to "Jobs" page
2. Find "Daily Pipeline - Production"
3. Click "Run Now"
4. Confirm: "Run Job"

### 6.2 Monitor Run

1. Click on running job to see details
2. View real-time logs:
   - Command output
   - Model execution
   - Test results
3. Monitor progress:
   - Models: X/16 completed
   - Tests: X/100 passed

### 6.3 Check Results

**Success Indicators**:
- ✅ All models completed successfully
- ✅ All tests passed
- ✅ Documentation generated
- ✅ Run time within expected range

**If Failed**:
1. Click on failed step
2. Review error message
3. Check logs for details
4. Common issues:
   - Connection timeout → Check SQL Warehouse is running
   - Model error → Check SQL syntax
   - Test failure → Check data quality

## Step 7: View Documentation

### 7.1 Access Documentation

1. Click "Documentation" in left sidebar
2. Or click "View Docs" on successful job run
3. Documentation is automatically hosted at:
   - `https://cloud.getdbt.com/accounts/{account_id}/projects/{project_id}/docs`

### 7.2 Documentation Features

- **Data Lineage Graph**: Visual DAG of all models
- **Model Documentation**: Descriptions, columns, tests
- **Source Documentation**: Source table definitions
- **Search**: Find models, columns, descriptions
- **Always Up-to-Date**: Regenerated on every job run

### 7.3 Share Documentation

1. Click "Share" button
2. Copy link
3. Share with team members
4. Anyone with link can view (read-only)

## Step 8: Create Development Job (Optional)

### 8.1 Create Dev Job

**Purpose**: Test changes before production

1. Click "Create Job"
2. Configure:
   - **Name**: `Development - Test Run`
   - **Environment**: Development
   - **Commands**:
     ```bash
     dbt deps
     dbt run --select staging+ dimensions+ facts+ marts+
     dbt test
     ```
   - **Triggers**: Manual only (no schedule)

### 8.2 Use Cases

- Test new models before merging to main
- Debug issues in isolated environment
- Experiment with changes

## Step 9: Monitor and Maintain

### 9.1 Job History

1. Go to "Jobs" → "Daily Pipeline - Production"
2. View "Run History"
3. See all past runs:
   - Status (Success/Failed/Cancelled)
   - Duration
   - Timestamp
   - Trigger (Scheduled/Manual)

### 9.2 Performance Monitoring

**Track Metrics**:
- Run duration trend
- Model execution time
- Test pass rate
- Failure frequency

**Optimize**:
- If runs take too long → Increase threads
- If tests fail frequently → Review data quality
- If timeouts occur → Check Databricks cluster

### 9.3 Alerts and Notifications

**Review Failure Alerts**:
1. Check email/Slack for failure notifications
2. Click link to view failed run
3. Investigate and fix issue
4. Re-run manually or wait for next scheduled run

## Step 10: Advanced Configuration (Optional)

### 10.1 Multiple Jobs

Create separate jobs for different purposes:

**Job 1: Incremental Refresh** (Hourly)
```bash
dbt run --select staging+ --exclude marts.*
```

**Job 2: Full Refresh** (Daily)
```bash
dbt run --full-refresh
dbt test
```

**Job 3: Marts Only** (Every 6 hours)
```bash
dbt run --select marts.*
```

### 10.2 Job Chaining

Create dependencies between jobs:
1. Job A completes → Trigger Job B
2. Configure in "Triggers" → "On Completion of Another Job"

### 10.3 Environment Variables

Add environment variables for sensitive data:
1. Go to Environment settings
2. Click "Environment Variables"
3. Add variables:
   - `DATABRICKS_TOKEN`
   - `SLACK_WEBHOOK_URL`
4. Reference in code: `{{ env_var('DATABRICKS_TOKEN') }}`

## Troubleshooting

### Issue: Connection Failed

**Error**: "Could not connect to Databricks"

**Solutions**:
1. Verify SQL Warehouse is running
2. Check token is valid (not expired)
3. Verify network connectivity
4. Test connection in Databricks SQL Editor

### Issue: Job Timeout

**Error**: "Job exceeded timeout of 60 minutes"

**Solutions**:
1. Increase timeout in job settings
2. Increase threads for faster execution
3. Optimize slow models
4. Use incremental models for large tables

### Issue: Test Failures

**Error**: "1 test failed"

**Solutions**:
1. Click on failed test to see details
2. Run test SQL manually in Databricks
3. Investigate data quality issue
4. Fix underlying data or update test

### Issue: Git Sync Failed

**Error**: "Could not sync with repository"

**Solutions**:
1. Check repository permissions
2. Re-authorize dbt Cloud
3. Verify branch exists
4. Check for merge conflicts

## Best Practices

### 1. Use Git Integration
- Version control all changes
- Review code before merging
- Use branches for development

### 2. Separate Environments
- Development for testing
- Production for scheduled runs
- Use different credentials

### 3. Monitor Job Performance
- Track run duration
- Set up alerts for failures
- Review logs regularly

### 4. Document Changes
- Update model descriptions
- Document new business logic
- Keep README up-to-date

### 5. Test Before Production
- Run in development first
- Verify all tests pass
- Check data quality

## Cost Considerations

### dbt Cloud Pricing

**Developer Plan (Free)**:
- 1 developer seat
- 3,000 model runs/month
- Community support

**Team Plan ($100/month)**:
- 8 developer seats
- Unlimited model runs
- Email support
- Advanced features

**For This Project**:
- Free plan is sufficient
- ~480 model runs/month (16 models × 30 days)
- Well within 3,000 limit

### Databricks Costs

**SQL Warehouse Costs**:
- Charged per DBU (Databricks Unit)
- Depends on warehouse size and runtime
- Estimate: ~$2-5/day for small warehouse

**Optimization**:
- Use Serverless SQL Warehouse (auto-scaling)
- Set auto-stop timeout (e.g., 10 minutes)
- Schedule jobs during off-peak hours

## Next Steps

After setting up dbt Cloud scheduling:

1. ✅ Verify first scheduled run completes successfully
2. ✅ Check documentation is generated and accessible
3. ✅ Set up email/Slack notifications
4. ✅ Monitor job performance for first week
5. ➡️ Proceed to **Step 15: Power BI Connection and Reports**

## Additional Resources

- [dbt Cloud Documentation](https://docs.getdbt.com/docs/dbt-cloud/cloud-overview)
- [dbt Cloud Jobs](https://docs.getdbt.com/docs/dbt-cloud/using-dbt-cloud/cloud-jobs)
- [dbt Cloud Scheduler](https://docs.getdbt.com/docs/dbt-cloud/using-dbt-cloud/cloud-scheduler)
- [Databricks Integration](https://docs.getdbt.com/docs/dbt-cloud/cloud-configuring-dbt-cloud/connecting-your-database#databricks)

