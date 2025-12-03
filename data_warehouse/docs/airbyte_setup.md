# Airbyte Setup Guide
# Airbyte 设置指南

This guide walks you through setting up Airbyte Cloud to sync data from Supabase PostgreSQL to Databricks.

## Prerequisites

- ✅ Supabase database with tables created and populated
- ✅ Databricks workspace and SQL Warehouse configured
- ✅ `.env` file configured with all required credentials
- ✅ Airbyte Cloud account (free tier available)

## Step 1: Create Airbyte Cloud Account

1. Visit https://cloud.airbyte.com
2. Click **"Sign Up"** or **"Get Started"**
3. Sign up using:
   - **Email** (recommended)
   - **Google** account
   - **GitHub** account
4. Verify your email address if required
5. Complete the onboarding process

## Step 2: Create Workspace

1. After logging in, you'll be prompted to create a workspace
2. Fill in workspace details:
   - **Workspace Name**: e.g., "shanghai-transport"
   - **Company Name**: Your company name
3. Click **"Create Workspace"**

## Step 3: Get API Credentials (Optional, for Automation)

If you want to automate Airbyte configuration via API:

1. Go to **Settings** > **API** (in Airbyte Cloud)
2. Click **"Generate API Key"**
3. Copy the API key (save securely)
4. Copy your **Workspace ID** (found in the URL or API settings)

Add to your `.env` file:
```bash
AIRBYTE_API_KEY=your_api_key_here
AIRBYTE_WORKSPACE_ID=your_workspace_id_here
```

## Step 4: Configure Environment Variables

Ensure your `.env` file in `data_warehouse` directory contains all required variables:

```bash
# Supabase Database (already configured)
SUPABASE_DB_HOST=your-supabase-host
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=your-supabase-user
SUPABASE_DB_PASSWORD=your-supabase-password

# Databricks (from Databricks setup)
DATABRICKS_SERVER_HOSTNAME=your-workspace.cloud.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id
DATABRICKS_TOKEN=your_databricks_token
DATABRICKS_DATABASE=hive_metastore
DATABRICKS_SCHEMA=shanghai_transport

# Airbyte (optional, for API automation)
AIRBYTE_API_KEY=your_airbyte_api_key
AIRBYTE_WORKSPACE_ID=your_workspace_id
```

## Step 5: Generate Configuration Files (Optional)

You can generate configuration JSON files from environment variables:

```bash
cd data_warehouse/airbyte/connections
python generate_config.py
```

This will create:
- `supabase_source.json` - Source configuration
- `databricks_destination.json` - Destination configuration

**Note**: These files are for reference. You'll still need to configure connections in Airbyte UI.

## Step 6: Create Source (Supabase PostgreSQL)

### Option A: Using Airbyte UI (Recommended)

1. In Airbyte Cloud, click **"Sources"** in the left sidebar
2. Click **"New Source"**
3. Search for **"PostgreSQL"** and select it
4. Fill in the connection details:

   **Basic Information:**
   - **Source Name**: `Supabase Source`
   
   **Connection Configuration:**
   - **Host**: Value from `SUPABASE_DB_HOST` in `.env`
   - **Port**: `5432`
   - **Database Name**: Value from `SUPABASE_DB_NAME` (usually `postgres`)
   - **Username**: Value from `SUPABASE_DB_USER`
   - **Password**: Value from `SUPABASE_DB_PASSWORD`
   - **SSL**: Enable (toggle ON)
   - **SSL Mode**: Select `require`
   
   **Replication Method:**
   - **Replication Method**: Select `Logical Replication (CDC)` for incremental sync
     - Or use `Standard` for full refresh (simpler, but slower)
   - **Replication Slot**: `airbyte_slot` (for CDC)
   - **Publication**: `airbyte_publication` (for CDC)
   
   **Schemas:**
   - **Schemas**: Select `public` schema

5. Click **"Set up source"**
6. Wait for connection test (should succeed if credentials are correct)
7. Click **"Save & Continue"**

### Option B: Using Airbyte API (Advanced)

If you have API credentials configured, you can use the API to create the source programmatically. See Airbyte API documentation for details.

## Step 7: Select Tables to Sync

After creating the source:

1. You'll see a list of available tables
2. Select the tables you want to sync:
   - ✅ `users`
   - ✅ `stations`
   - ✅ `routes`
   - ✅ `transactions`
   - ✅ `topups`
3. Click **"Save & Continue"**

## Step 8: Create Destination (Databricks)

### Option A: Using Airbyte UI (Recommended)

1. In Airbyte Cloud, click **"Destinations"** in the left sidebar
2. Click **"New Destination"**
3. Search for **"Databricks"** and select it
4. Fill in the connection details:

   **Basic Information:**
   - **Destination Name**: `Databricks Destination`
   
   **Connection Configuration:**
   - **Server Hostname**: Value from `DATABRICKS_SERVER_HOSTNAME` in `.env`
   - **HTTP Path**: Value from `DATABRICKS_HTTP_PATH` in `.env`
   - **Port**: `443`
   - **Personal Access Token**: Value from `DATABRICKS_TOKEN` in `.env`
   - **Database** (optional): Value from `DATABRICKS_DATABASE` (default: `hive_metastore`)
   - **Schema** (optional): Value from `DATABRICKS_SCHEMA` (e.g., `shanghai_transport`)

5. Click **"Set up destination"**
6. Wait for connection test (should succeed if credentials are correct)
7. Click **"Save & Continue"**

### Option B: Using Airbyte API (Advanced)

Use Airbyte API to create destination programmatically if you prefer.

## Step 9: Create Connection

1. In Airbyte Cloud, click **"Connections"** in the left sidebar
2. Click **"New Connection"**
3. Select:
   - **Source**: `Supabase Source` (created in Step 6)
   - **Destination**: `Databricks Destination` (created in Step 8)
4. Click **"Next"**

### Configure Sync Mode

For each table, configure the sync mode:

**Recommended Configuration:**

- **users**: 
  - Sync Mode: `Full Refresh | Overwrite`
  - (Small table, changes infrequently)
  
- **stations**: 
  - Sync Mode: `Full Refresh | Overwrite`
  - (Small table, changes infrequently)
  
- **routes**: 
  - Sync Mode: `Full Refresh | Overwrite`
  - (Small table, changes infrequently)
  
- **transactions**: 
  - Sync Mode: `Incremental | Append`
  - Cursor Field: `created_at` or `transaction_date`
  - (Large table, grows continuously)
  
- **topups**: 
  - Sync Mode: `Incremental | Append`
  - Cursor Field: `created_at` or `topup_date`
  - (Large table, grows continuously)

### Configure Sync Schedule

1. **Sync Frequency**: 
   - Select **"Scheduled"**
   - Choose frequency:
     - **Every hour** (for near real-time)
     - **Every 6 hours** (for daily updates)
     - **Every 24 hours** (for daily batch sync)
     - **Custom cron** (for advanced scheduling)

2. **Sync Schedule**:
   - Recommended: `0 2 * * *` (Daily at 2 AM UTC)
   - Or: `0 */6 * * *` (Every 6 hours)

### Configure Data Transformation (Optional)

1. **Normalization**: 
   - Enable **"Normalize data"** (recommended)
   - This creates normalized tables in Databricks

2. **Namespace**: 
   - Choose namespace format:
     - **Source namespace** (recommended)
     - **Destination namespace**
     - **Custom**

### Finalize Connection

1. Review all settings
2. Click **"Set up connection"**
3. Wait for connection creation
4. Connection status should show as **"Active"**

## Step 10: Trigger First Sync

1. After creating the connection, you'll see it in the Connections list
2. Click on the connection name
3. Click **"Sync Now"** button (or wait for scheduled sync)
4. Monitor the sync progress:
   - **Status**: Shows sync progress
   - **Logs**: View detailed logs if issues occur
   - **Records**: Shows number of records synced

## Step 11: Verify Data in Databricks

After the first sync completes:

1. Go to Databricks workspace
2. Open SQL Editor
3. Run queries to verify data:

```sql
-- Check if tables exist
SHOW TABLES IN shanghai_transport;

-- Check record counts
SELECT COUNT(*) FROM shanghai_transport.users;
SELECT COUNT(*) FROM shanghai_transport.stations;
SELECT COUNT(*) FROM shanghai_transport.routes;
SELECT COUNT(*) FROM shanghai_transport.transactions;
SELECT COUNT(*) FROM shanghai_transport.topups;

-- Compare with source (should match)
-- Run similar queries in Supabase to compare
```

## Troubleshooting

### Connection Test Fails

**Source (Supabase) Connection Issues:**
- Verify database credentials in `.env` file
- Check if Supabase project is running
- Ensure IP is not blocked (if using IP restrictions)
- Verify SSL settings are correct
- For CDC: Ensure PostgreSQL replication is enabled

**Destination (Databricks) Connection Issues:**
- Verify Databricks token is valid and not expired
- Check SQL Warehouse is running
- Verify HTTP path is correct
- Ensure token has proper permissions

### Sync Fails

**Common Issues:**
- **Out of memory**: Reduce batch size or sync fewer tables at once
- **Timeout**: Increase timeout settings or sync during off-peak hours
- **Schema mismatch**: Ensure Databricks schema exists
- **Permission errors**: Check token permissions

**Solutions:**
- Check sync logs in Airbyte UI
- Verify source data is accessible
- Check destination has sufficient resources
- Review error messages for specific issues

### CDC Replication Issues

If using CDC (Change Data Capture):

1. **Replication slot already exists**:
   - Connect to Supabase database
   - Drop existing slot: `SELECT pg_drop_replication_slot('airbyte_slot');`
   - Recreate source in Airbyte

2. **Publication not found**:
   - Create publication: `CREATE PUBLICATION airbyte_publication FOR ALL TABLES;`
   - Or recreate source in Airbyte

3. **Permissions**:
   - Ensure database user has replication permissions
   - Grant: `ALTER USER postgres WITH REPLICATION;`

## Free Tier Limits

Be aware of Airbyte Cloud free tier limitations:

- **Sync Frequency**: Limited sync frequency
- **Data Volume**: Limited data volume per month
- **Connections**: Limited number of connections
- **Support**: Community support

Check current limits at: https://airbyte.com/pricing

## Best Practices

1. **Use Incremental Sync**: For large tables (transactions, topups), use incremental sync to save bandwidth
2. **Schedule Off-Peak**: Schedule syncs during off-peak hours to avoid impacting source database
3. **Monitor Syncs**: Regularly check sync status and logs
4. **Test First**: Test with small tables before syncing large tables
5. **Backup**: Keep backups of important data before major syncs

## Next Steps

After setting up Airbyte:

1. ✅ Verify first sync completed successfully
2. ✅ Check data in Databricks matches source
3. ✅ Monitor sync status regularly
4. ➡️ Proceed to **Step 6: Databricks Configuration** (see `databricks_setup.md`)

## Additional Resources

- [Airbyte Documentation](https://docs.airbyte.com/)
- [Airbyte PostgreSQL Source](https://docs.airbyte.com/integrations/sources/postgres)
- [Airbyte Databricks Destination](https://docs.airbyte.com/integrations/destinations/databricks)
- [Airbyte API Documentation](https://reference.airbyte.com/)


