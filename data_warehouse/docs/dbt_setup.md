# dbt Setup Guide
# dbt 设置指南

This guide covers setting up dbt Core for the Shanghai Transport Card data warehouse project.

## Prerequisites

- ✅ Databricks workspace configured
- ✅ Data synced from Supabase via Airbyte (in `workspace.public` schema)
- ✅ Python 3.8+ installed
- ✅ `.env` file configured with Databricks credentials
- ✅ dbt Cloud project created (for future use)

## Step 1: Install dbt Core

Install dbt with Databricks adapter:

```bash
pip install dbt-databricks
```

Or add to requirements:

```bash
cd data_warehouse
pip install -r scripts/requirements.txt
pip install dbt-databricks
```

Verify installation:

```bash
dbt --version
```

Expected output should show dbt version and Databricks adapter.

## Step 2: Configure Environment Variables

Ensure your `.env` file in `data_warehouse` directory contains:

```bash
# Databricks Configuration
DATABRICKS_SERVER_HOSTNAME=your-workspace.cloud.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id
DATABRICKS_TOKEN=your_databricks_token
```

## Step 3: Test Connection

Navigate to dbt directory and test connection:

```bash
cd data_warehouse/dbt
dbt debug --profiles-dir .
```

This will:
- Check dbt installation
- Test Databricks connection
- Verify profiles.yml configuration

Expected output:
```
Connection test: [OK connection ok]
```

## Step 4: Install dbt Packages

Install required dbt packages:

```bash
cd data_warehouse/dbt
dbt deps
```

This installs packages defined in `packages.yml` (e.g., `dbt_utils`).

## Step 5: Verify Project Structure

Your dbt project structure should be:

```
dbt/
├── dbt_project.yml          # Project configuration
├── packages.yml             # dbt packages
├── profiles.yml             # Connection profiles (for dbt Core)
├── models/
│   ├── sources.yml          # Source table definitions
│   ├── staging/             # Staging models
│   ├── dimensions/          # Dimension models
│   ├── facts/               # Fact models
│   └── marts/               # Marts models
└── tests/                   # Custom tests
```

## Step 6: Verify Source Tables

Check that source tables exist in Databricks:

```bash
# In Databricks SQL Editor or via dbt
dbt run-operation run_query --args '{sql: "SHOW TABLES IN workspace.public"}'
```

Or directly in Databricks:

```sql
SHOW TABLES IN workspace.public;
```

You should see:
- `users`
- `stations`
- `routes`
- `transactions`
- `topups`

## Step 7: Understand Schema Structure

dbt will create tables in different schemas:

- **Source**: `workspace.public` (Airbyte synced tables)
- **Staging**: `workspace.staging` (cleaned data, views)
- **Dimensions**: `workspace.dimensions` (dimension tables)
- **Facts**: `workspace.facts` (fact tables, partitioned)
- **Marts**: `workspace.marts` (business metrics tables)

This separation provides:
- Clear data lineage
- Easy to manage permissions
- Better organization

## Step 8: Test dbt Commands

### List Models

```bash
dbt list
```

This shows all models defined in the project (will be empty until models are created).

### Compile Project

```bash
dbt compile
```

This compiles SQL without executing (useful for testing syntax).

### Run Models

```bash
# Run all models
dbt run

# Run specific model
dbt run --select staging.*

# Run models with dependencies
dbt run --select staging+  # staging and downstream models
```

### Run Tests

```bash
# Run all tests
dbt test

# Run tests for specific models
dbt test --select staging.*
```

### Generate Documentation

```bash
dbt docs generate
dbt docs serve
```

This generates and serves documentation website.

## Step 9: Create Schemas (First Time Only)

Before running dbt models, create the target schemas in Databricks:

```sql
-- In Databricks SQL Editor
CREATE SCHEMA IF NOT EXISTS workspace.staging;
CREATE SCHEMA IF NOT EXISTS workspace.dimensions;
CREATE SCHEMA IF NOT EXISTS workspace.facts;
CREATE SCHEMA IF NOT EXISTS workspace.marts;
```

Or dbt can create schemas automatically if you have permissions.

## Step 10: Verify Configuration

Check your configuration:

```bash
# Show current profile
dbt debug --profiles-dir .

# Show project configuration
dbt debug --config-dir .
```

## Common Issues

### Connection Failed

**Error**: `Connection test: [ERROR connection failed]`

**Solutions**:
- Verify `.env` file has correct values
- Check Databricks SQL Warehouse is running
- Verify token is valid and not expired
- Test connection manually in Databricks SQL Editor

### Schema Not Found

**Error**: `Schema 'workspace.staging' not found`

**Solutions**:
- Create schemas manually (see Step 9)
- Or ensure dbt has permissions to create schemas
- Check catalog name is correct (`workspace`)

### Environment Variables Not Loaded

**Error**: `Environment variable DATABRICKS_TOKEN not set`

**Solutions**:
- Ensure `.env` file is in `data_warehouse` directory
- Use `python-dotenv` to load variables (profiles.yml uses `${VAR}` syntax)
- Or set environment variables directly in shell

### Package Installation Failed

**Error**: `dbt deps` fails

**Solutions**:
- Check internet connection
- Verify `packages.yml` syntax is correct
- Try updating dbt: `pip install --upgrade dbt-databricks`

## Next Steps

After dbt Core setup:

1. ✅ Verify connection works
2. ✅ Install packages
3. ✅ Create target schemas
4. ➡️ Proceed to **Step 9: Create Staging Models** (see `dbt_staging_models.md`)

## dbt Cloud Setup (Future)

When ready to use dbt Cloud:

1. In dbt Cloud, go to **Settings** > **Connections**
2. Create new Databricks connection:
   - Use same credentials from `.env`
   - Catalog: `workspace`
   - Default Schema: `staging`
3. Connect your repository (when ready)
4. Create Environment and Jobs

For now, continue with dbt Core for development.

## Additional Resources

- [dbt Documentation](https://docs.getdbt.com/)
- [dbt Databricks Profile](https://docs.getdbt.com/reference/warehouse-profiles/databricks-profile)
- [dbt Best Practices](https://docs.getdbt.com/guides/best-practices)

