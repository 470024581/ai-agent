# Shanghai Transport dbt Project

## Quick Start

### Prerequisites
1. Create `.env` file in `data_warehouse` directory with:
```bash
DATABRICKS_SERVER_HOSTNAME=your-workspace.cloud.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id
DATABRICKS_TOKEN=your_token
```

### Local Testing
```bash
cd data_warehouse/dbt
.\test_local_with_env.bat
```

## Project Structure
- `models/staging/` - Staging layer (raw data cleaning)
- `models/dimensions/` - Dimension tables
- `models/facts/` - Fact tables
- `models/marts/` - Business metrics and aggregations

## Important Notes

### File Encoding
⚠️ **All SQL files must be saved as UTF-8 without BOM**

If you encounter `PARSE_SYNTAX_ERROR` in Databricks, check for BOM:
```powershell
# Check for BOM
$bytes = [System.IO.File]::ReadAllBytes("file.sql")
$hasBOM = ($bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)

# Remove BOM
$content = Get-Content "file.sql" -Raw
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText("file.sql", $content, $utf8NoBom)
```

### Source Tables
Source tables in Databricks have `src_` prefix:
- `workspace.public.src_users`
- `workspace.public.src_stations`
- `workspace.public.src_routes`
- `workspace.public.src_transactions`
- `workspace.public.src_topups`

## dbt Commands
```bash
# Test connection
dbt debug --profiles-dir .

# Install dependencies
dbt deps

# Run all models
dbt run

# Run specific layer
dbt run --select staging.*
dbt run --select dimensions.*
dbt run --select facts.*
dbt run --select marts.*

# Run tests
dbt test

# Generate documentation
dbt docs generate
dbt docs serve
```

## Troubleshooting

### Connection Issues
- Ensure Databricks SQL Warehouse is running
- Verify environment variables are set correctly
- Check token is valid

### Compilation Errors
- Clear cache: `Remove-Item -Recurse -Force target,logs`
- Check for BOM in SQL files
- Verify source table names have `src_` prefix

### dbt Cloud
- Set "Project subdirectory" to `data_warehouse/dbt`
- Configure environment variables in dbt Cloud project settings
