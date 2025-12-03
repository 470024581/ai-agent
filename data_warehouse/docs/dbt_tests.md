# dbt Tests Guide
# dbt 测试指南

This guide covers dbt testing strategies and custom tests.

## Overview

dbt provides two types of tests:
1. **Schema Tests**: Defined in `schema.yml` files (unique, not_null, relationships, accepted_values)
2. **Data Tests**: Custom SQL queries in `tests/` directory

Tests ensure data quality and catch issues early in the pipeline.

## Schema Tests

Schema tests are defined in `schema.yml` files for each layer.

### Built-in Tests

**unique**: Ensures column values are unique
```yaml
- name: user_id
  tests:
    - unique
```

**not_null**: Ensures column values are not NULL
```yaml
- name: user_id
  tests:
    - not_null
```

**relationships**: Validates foreign key relationships
```yaml
- name: user_key
  tests:
    - relationships:
        to: ref('dim_user')
        field: user_key
```

**accepted_values**: Validates enum/categorical values
```yaml
- name: card_type
  tests:
    - accepted_values:
        values: ['Regular', 'Student', 'Senior', 'Disabled']
```

### Test Coverage Summary

**Staging Layer** (~25 tests):
- Primary key uniqueness and not_null
- Foreign key relationships
- Enum value validation
- Data type validation

**Dimension Layer** (~30 tests):
- Surrogate key uniqueness
- Business key uniqueness
- Required field validation
- Date attribute validation

**Fact Layer** (~25 tests):
- Fact key uniqueness
- Foreign key relationships to all dimensions
- Measure validation (not_null, positive values)
- Date range validation

**Marts Layer** (~20 tests):
- Grain validation (unique dates/keys)
- Metric consistency
- Not_null for key metrics

**Total**: ~100 schema tests

## Custom Data Tests

Custom tests are SQL queries in `tests/` directory that return failing rows.

### 1. assert_positive_amounts.sql
**Purpose**: Ensure all transaction amounts are non-negative

**Logic**: Fails if any transaction has amount < 0

**Why**: Transaction amounts should never be negative

### 2. assert_positive_topup_amounts.sql
**Purpose**: Ensure all top-up amounts are positive

**Logic**: Fails if any top-up has amount <= 0

**Why**: Top-ups must have positive amounts

### 3. assert_valid_date_range.sql
**Purpose**: Ensure transaction dates are within valid range

**Logic**: Fails if dates are before 2024-01-01 or in the future

**Why**: Catch data quality issues with invalid dates

### 4. assert_dimension_integrity.sql
**Purpose**: Ensure dimension surrogate keys are consistent

**Logic**: Fails if same business key has multiple surrogate keys

**Why**: Maintain referential integrity

### 5. assert_daily_metrics_consistency.sql
**Purpose**: Ensure daily metrics are logically consistent

**Logic**: Fails if active_users > total_transactions

**Why**: Impossible scenario indicates data quality issue

## Custom Test Macros

Macros allow reusable test logic.

### test_amount_range.sql
**Purpose**: Check if amounts are within expected range

**Usage**:
```yaml
- name: amount
  tests:
    - dbt_utils.expression_is_true:
        expression: "amount >= 0 AND amount <= 1000"
```

## Running Tests

### Run All Tests

```bash
cd data_warehouse/dbt

# Run all tests
dbt test
```

Expected output:
```
Running with dbt=1.7.0
Found 16 models, 100 tests, 0 snapshots

Concurrency: 4 threads (target='dev')

1 of 100 START test not_null_stg_users_user_id ...................... [RUN]
2 of 100 START test unique_stg_users_user_id ........................ [RUN]
...
100 of 100 OK passed ................................................ [PASS in 0.45s]

Completed successfully

Done. PASS=100 WARN=0 ERROR=0 SKIP=0 TOTAL=100
```

### Run Tests by Layer

```bash
# Test staging models only
dbt test --select staging.*

# Test dimensions only
dbt test --select dimensions.*

# Test facts only
dbt test --select facts.*

# Test marts only
dbt test --select marts.*
```

### Run Specific Test

```bash
# Run specific test by name
dbt test --select test_name

# Run custom data tests only
dbt test --select test_type:data
```

### Run Tests with Models

```bash
# Run models and then test them
dbt build

# Or run and test specific models
dbt build --select staging.*
```

## Test Results

### Passing Tests
```
PASS 1 unique_stg_users_user_id ................................. [PASS in 0.45s]
```

### Failing Tests
```
FAIL 1 assert_positive_amounts .................................. [FAIL 3 in 0.52s]
```

When a test fails:
1. Check the test SQL to understand what it's checking
2. Query the failing rows to investigate
3. Fix the underlying data issue
4. Re-run the test

### Investigate Failing Test

```sql
-- Run the test SQL manually to see failing rows
SELECT
    transaction_id,
    amount,
    transaction_type
FROM workspace.facts.fact_transactions
WHERE amount < 0;
```

## Test Organization

```
dbt/
├── models/
│   ├── staging/
│   │   └── schema.yml          # Staging tests
│   ├── dimensions/
│   │   └── schema.yml          # Dimension tests
│   ├── facts/
│   │   └── schema.yml          # Fact tests
│   └── marts/
│       └── schema.yml          # Marts tests
├── tests/
│   ├── assert_positive_amounts.sql
│   ├── assert_positive_topup_amounts.sql
│   ├── assert_valid_date_range.sql
│   ├── assert_dimension_integrity.sql
│   └── assert_daily_metrics_consistency.sql
└── macros/
    ├── test_amount_range.sql
    └── generate_schema_name.sql
```

## Best Practices

### 1. Test Early and Often
- Run tests after every model change
- Include tests in CI/CD pipeline
- Test at each layer (staging, dimensions, facts, marts)

### 2. Test Critical Business Logic
- Primary keys (unique, not_null)
- Foreign keys (relationships)
- Business rules (positive amounts, valid dates)
- Metric consistency

### 3. Write Descriptive Test Names
- Use clear, descriptive names for custom tests
- Document what each test checks
- Explain why the test is important

### 4. Balance Coverage vs Performance
- Test critical fields thoroughly
- Consider test execution time
- Use sampling for very large tables (if needed)

### 5. Document Test Failures
- Document common failure scenarios
- Provide troubleshooting steps
- Include example queries to investigate

## Troubleshooting

### Test Timeout

**Issue**: Tests take too long to run

**Solutions**:
- Run tests by layer: `dbt test --select staging.*`
- Increase timeout in `dbt_project.yml`
- Optimize test queries
- Consider sampling for large tables

### False Positives

**Issue**: Test fails but data is actually correct

**Solutions**:
- Review test logic
- Check for edge cases
- Update test to handle valid scenarios
- Add comments explaining expected behavior

### Test Dependencies

**Issue**: Test fails because upstream model hasn't run

**Solutions**:
- Run models before tests: `dbt build`
- Or run in order: `dbt run && dbt test`
- Check model dependencies: `dbt list --select +model_name`

## CI/CD Integration

### GitHub Actions Example

```yaml
name: dbt Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Install dbt
        run: pip install dbt-databricks
      - name: Run dbt tests
        run: |
          cd data_warehouse/dbt
          dbt deps
          dbt test
```

## Next Steps

After setting up tests:

1. ✅ Run all tests: `dbt test`
2. ✅ Verify all tests pass
3. ✅ Generate documentation: `dbt docs generate && dbt docs serve`
4. ➡️ Set up scheduling (dbt Cloud or Airflow)
5. ➡️ Connect Power BI for visualization

## Additional Resources

- [dbt Testing Documentation](https://docs.getdbt.com/docs/build/tests)
- [dbt Test Selection](https://docs.getdbt.com/reference/node-selection/test-selection-examples)
- [Custom Generic Tests](https://docs.getdbt.com/guides/best-practices/writing-custom-generic-tests)

