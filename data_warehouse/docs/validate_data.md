# Data Statistics Guide
# 数据统计指南

This guide explains how to use the data statistics script to get basic information about the Shanghai Transport Card database.

**Important**: Detailed data validation and cleaning logic should be implemented in dbt tests. This script only provides basic statistics. For comprehensive validation, use `dbt test` after setting up dbt models.

## Prerequisites

- ✅ Database tables created and populated with data
- ✅ Python 3.8 or higher installed
- ✅ `.env` file configured with database credentials
- ✅ Required Python packages installed (`psycopg2-binary`, `python-dotenv`)

## Step 1: Get Basic Statistics

Navigate to the scripts directory and run:

```bash
cd data_warehouse/scripts
python validate_data.py
```

This will collect basic statistics (row counts, date ranges) and display a text report.

## Step 2: Generate Report Files

### JSON Report

Generate a JSON report for programmatic processing:

```bash
python validate_data.py --format json --output ../reports/validation_report.json
```

### HTML Report

Generate an HTML report for easy viewing:

```bash
python validate_data.py --format html --output ../reports/validation_report.html
```

Then open the HTML file in your web browser.

### Text Report (Default)

Generate a text report (default, displayed in console):

```bash
python validate_data.py --format text
```

## What This Script Does

This script provides **basic statistics** only:

- ✅ Table existence check
- ✅ Row counts for each table
- ✅ Column information
- ✅ Date ranges (if applicable)

## Detailed Validation in dbt

For comprehensive data validation, use **dbt tests**. After setting up dbt models, run:

```bash
cd data_warehouse/dbt
dbt test
```

dbt tests will validate:
- ✅ NOT NULL constraints
- ✅ Unique constraints
- ✅ Foreign key relationships
- ✅ Accepted values (enums)
- ✅ Custom business rules
- ✅ Data quality metrics

See `dbt_tests.md` for details on setting up dbt tests.

## Understanding Report Output

### Report Structure

The statistics report contains:

1. **Table Statistics**: Row counts and basic information for each table
2. **Date Ranges**: Min/max dates for date columns (if applicable)
3. **Column Information**: Number of columns per table

### Example Output

```
============================================================
STATISTICS REPORT
============================================================

For detailed data validation and cleaning, use dbt tests (dbt test)

Table Statistics:
--------------------------------------------------------------

USERS:
  Row Count: 1,000
  Columns: 6
  created_at Range: 2023-01-15 to 2024-12-02

STATIONS:
  Row Count: 150
  Columns: 7

TRANSACTIONS:
  Row Count: 150,000
  Columns: 10
  transaction_date Range: 2024-11-02 to 2024-12-02

============================================================
Note: For detailed data validation, run 'dbt test' after setting up dbt models
```

## Why Use dbt for Validation?

dbt is the recommended tool for data validation because:

1. **SQL-based**: Uses SQL for validation, which is more efficient and maintainable
2. **Integrated**: Works seamlessly with your data transformation pipeline
3. **Version-controlled**: Validation logic is stored in code and version-controlled
4. **Automated**: Can be run automatically in CI/CD pipelines
5. **Comprehensive**: Supports many test types (uniqueness, relationships, custom SQL)

## Setting Up dbt Tests

After creating dbt models, add tests in `schema.yml` files:

```yaml
models:
  - name: stg_users
    columns:
      - name: user_id
        tests:
          - unique
          - not_null
      - name: card_number
        tests:
          - unique
          - not_null
```

Then run: `dbt test`

## Integration with CI/CD

For CI/CD, use dbt tests instead:

```bash
# Run dbt tests (recommended)
cd data_warehouse/dbt
dbt test

# Check exit code
if [ $? -ne 0 ]; then
    echo "Data validation failed!"
    exit 1
fi
```

## Automated Statistics Collection

You can schedule this script to collect statistics regularly:

### Windows Task Scheduler

1. Create a batch file `collect_stats.bat`:
```batch
cd D:\Workspaces\ReactWorkspace\ai-agent\data_warehouse\scripts
python validate_data.py --format html --output ..\reports\stats_%date:~0,4%%date:~5,2%%date:~8,2%.html
```

2. Schedule it to run daily in Task Scheduler

### Linux Cron

Add to crontab:
```bash
# Collect statistics daily at 2 AM
0 2 * * * cd /path/to/data_warehouse/scripts && python validate_data.py --format html --output ../reports/stats_$(date +\%Y\%m\%d).html
```

**Note**: For automated validation, use dbt Cloud schedules or Airflow DAGs to run `dbt test`.

## Best Practices

1. **Use this script for quick statistics**: Good for checking data volume and basic info
2. **Use dbt tests for validation**: Implement comprehensive validation in dbt
3. **Run dbt tests regularly**: Set up automated dbt test runs in dbt Cloud or Airflow
4. **Keep statistics reports**: Save reports for tracking data growth over time
5. **Combine with dbt tests**: Use both tools - statistics for monitoring, dbt tests for validation

## Next Steps

After collecting statistics:

1. ✅ Review statistics report
2. ✅ Set up dbt models and tests for detailed validation
3. ➡️ Proceed to **Step 5: Airbyte Configuration** (see `airbyte_setup.md`)

For detailed validation, see:
- `dbt_tests.md` - How to set up dbt tests
- `dbt_staging_models.md` - How to create staging models with validation

## Additional Resources

- [PostgreSQL Data Types](https://www.postgresql.org/docs/current/datatype.html)
- [PostgreSQL Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)
- [Data Quality Best Practices](https://www.postgresql.org/docs/current/ddl-constraints.html)

