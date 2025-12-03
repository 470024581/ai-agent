# dbt Profiles Configuration Guide
# dbt Profiles 配置指南

This guide explains how to configure `profiles.yml` for dbt Core with Databricks.

## Configuration Overview

The `profiles.yml` file connects dbt to your Databricks workspace. It uses environment variables from `.env` file.

## Current Configuration

```yaml
shanghai_transport:
  target: dev
  outputs:
    dev:
      type: databricks
      method: token
      catalog: "workspace"
      schema: "staging"  # Default schema
      host: "${DATABRICKS_SERVER_HOSTNAME}"
      http_path: "${DATABRICKS_HTTP_PATH}"
      token: "${DATABRICKS_TOKEN}"
      threads: 4
```

## Environment Variables

Ensure these are set in `.env` file:

```bash
DATABRICKS_SERVER_HOSTNAME=your-workspace.cloud.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id
DATABRICKS_TOKEN=your_databricks_token
```

## Schema Configuration

dbt uses different schemas for different layers:

- **Default Schema**: `staging` (set in profiles.yml)
- **Model Schemas**: Overridden in `dbt_project.yml`:
  - Staging: `workspace.staging`
  - Dimensions: `workspace.dimensions`
  - Facts: `workspace.facts`
  - Marts: `workspace.marts`

## Testing Configuration

Test your configuration:

```bash
cd data_warehouse/dbt
dbt debug --profiles-dir .
```

Expected output:
```
Using profiles dir at [path]
Using dbt_project.yml at [path]

Configuration:
  profiles.yml file: [OK found and valid]
  dbt_project.yml file: [OK found and valid]

Required dependencies:
  - git: [OK found]

Connection:
  host: [your-host]
  http_path: [your-path]
  catalog: [workspace]
  Connection test: [OK connection ok]
```

## Troubleshooting

### Environment Variables Not Loading

If `${VAR}` syntax doesn't work, you can hardcode values temporarily:

```yaml
host: "your-workspace.cloud.databricks.com"
http_path: "/sql/1.0/warehouses/your-id"
token: "your-token"
```

**Note**: Don't commit hardcoded credentials to version control!

### Multiple Environments

You can configure multiple environments:

```yaml
shanghai_transport:
  target: dev  # Default target
  outputs:
    dev:
      # Development environment
      catalog: "workspace"
      schema: "staging"
      # ... other config
    prod:
      # Production environment
      catalog: "workspace"
      schema: "staging_prod"
      threads: 8  # More threads for production
      # ... other config
```

Switch targets:
```bash
dbt run --target prod
```

## Next Steps

After configuring profiles:

1. ✅ Test connection: `dbt debug`
2. ✅ Verify schemas exist or can be created
3. ➡️ Proceed to create dbt models

