# Databricks Setup Guide
# Databricks 设置指南

This guide covers Databricks configuration for the data warehouse, focusing on dbt Cloud integration.

## Prerequisites

- ✅ Databricks account and workspace created
- ✅ SQL Warehouse configured
- ✅ Data synced from Supabase via Airbyte
- ✅ dbt Cloud account ready
- ✅ Environment variables configured in `.env` file

## Step 1: Verify Data Sync from Airbyte

After Airbyte sync completes, verify data exists in Databricks:

1. Open Databricks workspace
2. Go to **SQL Editor**
3. Run verification queries:

```sql
-- Check if tables exist (Airbyte creates these)
SHOW TABLES IN hive_metastore.shanghai_transport;

-- Check record counts
SELECT COUNT(*) as user_count FROM hive_metastore.shanghai_transport.users;
SELECT COUNT(*) as station_count FROM hive_metastore.shanghai_transport.stations;
SELECT COUNT(*) as transaction_count FROM hive_metastore.shanghai_transport.transactions;
```

## Step 2: Configure Environment Variables

Ensure your `.env` file contains Databricks configuration:

```bash
# Databricks Configuration
DATABRICKS_SERVER_HOSTNAME=your-workspace.cloud.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id
DATABRICKS_TOKEN=your_databricks_token
DATABRICKS_CATALOG=hive_metastore
DATABRICKS_SCHEMA=shanghai_transport
```

**Note**: 
- `DATABRICKS_CATALOG`: Usually `hive_metastore` (default) or your custom catalog
- `DATABRICKS_SCHEMA`: The schema where Airbyte synced data (check in Databricks)

## Step 3: Verify SQL Warehouse is Running

1. In Databricks, go to **SQL Warehouses**
2. Ensure your SQL Warehouse is **Running**
3. If not running, click **Start**
4. Note the **Connection details**:
   - Server hostname
   - HTTP path
   - Port (usually 443)

## Step 4: Test Connection from dbt Cloud

Before configuring dbt Cloud, test the connection:

### Option A: Using dbt CLI (Local Test)

If you have dbt-databricks installed locally:

```bash
cd data_warehouse/dbt
dbt debug --profiles-dir .
```

This will test the Databricks connection.

### Option B: Using Databricks SQL Editor

Test basic connectivity:

```sql
SELECT current_catalog(), current_schema();
SELECT COUNT(*) FROM hive_metastore.shanghai_transport.users;
```

## Step 5: Prepare for dbt Cloud Setup

Before setting up dbt Cloud, ensure:

1. ✅ Databricks SQL Warehouse is running
2. ✅ Databricks token is valid (not expired)
3. ✅ Token has proper permissions:
   - Can read/write to the schema
   - Can create tables/views
   - Can query existing tables

4. ✅ You know:
   - Server hostname
   - HTTP path
   - Catalog name (usually `hive_metastore`)
   - Schema name (where Airbyte synced data)

## Step 6: Understanding Table Structure

### Source Tables (from Airbyte)

Airbyte creates tables in Databricks with the same structure as Supabase:
- `users` - User data
- `stations` - Station data
- `routes` - Route data
- `transactions` - Transaction data
- `topups` - Top-up data

**Location**: Usually in `hive_metastore.shanghai_transport` (or your configured schema)

### Target Tables (created by dbt)

dbt will create additional tables for the data warehouse:
- **Staging**: `stg_users`, `stg_stations`, etc. (cleaned data)
- **Dimensions**: `dim_user`, `dim_station`, `dim_route`, `dim_time`
- **Facts**: `fact_transactions`, `fact_topups` (partitioned by date)
- **Marts**: `daily_active_users`, `daily_topup_summary`, etc.

**Location**: Same catalog/schema or separate schema (configurable in dbt)

## Step 7: Verify Permissions

Ensure your Databricks token/user has permissions to:

1. **Read** from source tables (created by Airbyte)
2. **Create** tables/views in the target schema
3. **Write** to Delta Lake tables
4. **Query** metadata (SHOW TABLES, DESCRIBE, etc.)

## Next Steps

After completing Databricks setup:

1. ✅ Verify data exists in Databricks
2. ✅ Test connection from dbt Cloud
3. ✅ Note catalog and schema names
4. ➡️ Proceed to **Step 8: dbt Project Initialization** (see `dbt_setup.md`)

## Troubleshooting

### Cannot Connect to Databricks

- Verify SQL Warehouse is running
- Check token is valid and not expired
- Verify server hostname and HTTP path are correct
- Check network/firewall settings

### Cannot See Tables

- Verify schema name is correct
- Check if Airbyte sync completed successfully
- Run `SHOW TABLES IN <catalog>.<schema>` to list tables

### Permission Errors

- Ensure token has proper permissions
- Check if user can create tables in target schema
- Verify catalog access permissions

## Additional Resources

- [Databricks SQL Warehouse Documentation](https://docs.databricks.com/sql/admin/sql-endpoints.html)
- [Databricks Delta Lake Guide](https://docs.databricks.com/delta/index.html)
- [dbt-databricks Documentation](https://docs.getdbt.com/reference/warehouse-profiles/databricks-profile)

