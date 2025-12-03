# dbt Project - Shanghai Transport Data Warehouse

## Quick Start

### 1. Install Dependencies

```bash
cd data_warehouse
pip install dbt-databricks
```

### 2. Install dbt Packages

```bash
cd dbt
dbt deps
```

### 3. Test Connection

```bash
dbt debug --profiles-dir .
```

### 4. Run Models

```bash
# Run all staging models
dbt run --select staging.*

# Run all models
dbt run

# Run specific model
dbt run --select stg_users
```

### 5. Run Tests

```bash
# Test all staging models
dbt test --select staging.*

# Test all models
dbt test

# Test specific model
dbt test --select stg_users
```

### 6. Generate Documentation

```bash
dbt docs generate
dbt docs serve
```

## Project Structure

```
dbt/
├── dbt_project.yml          # Project configuration
├── packages.yml             # dbt packages (dbt_utils)
├── profiles.yml             # Connection profiles
├── models/
│   ├── sources.yml          # Source table definitions
│   ├── staging/             # Staging models (views)
│   │   ├── schema.yml       # Tests and documentation
│   │   ├── stg_users.sql
│   │   ├── stg_stations.sql
│   │   ├── stg_routes.sql
│   │   ├── stg_transactions.sql
│   │   └── stg_topups.sql
│   ├── dimensions/          # Dimension models (tables)
│   ├── facts/               # Fact models (tables)
│   └── marts/               # Marts models (tables)
└── tests/                   # Custom tests
```

## Schema Structure

- **Source**: `workspace.public` (Airbyte synced tables)
- **Staging**: `workspace.staging` (cleaned data, views)
- **Dimensions**: `workspace.dimensions` (dimension tables)
- **Facts**: `workspace.facts` (fact tables, partitioned)
- **Marts**: `workspace.marts` (business metrics tables)

## Environment Variables

Ensure `.env` file in `data_warehouse` directory contains:

```bash
DATABRICKS_SERVER_HOSTNAME=your-workspace.cloud.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id
DATABRICKS_TOKEN=your_databricks_token
```

## Common Commands

```bash
# List all models
dbt list

# Compile without running
dbt compile

# Run with specific target
dbt run --target prod

# Run models and downstream dependencies
dbt run --select stg_users+

# Run models and upstream dependencies
dbt run --select +fact_transactions

# Run models by tag
dbt run --select tag:daily

# Fresh check (for sources)
dbt source freshness
```

## Documentation

See `docs/` directory for detailed guides:

- `dbt_setup.md` - Initial setup guide
- `dbt_staging_models.md` - Staging models guide
- `dbt_dimension_models.md` - Dimension models guide (coming next)
- `dbt_fact_models.md` - Fact models guide
- `dbt_marts_models.md` - Marts models guide
- `dbt_tests.md` - Testing guide

## Next Steps

1. ✅ Run staging models: `dbt run --select staging.*`
2. ✅ Test staging models: `dbt test --select staging.*`
3. ➡️ Create dimension models (Step 10)

