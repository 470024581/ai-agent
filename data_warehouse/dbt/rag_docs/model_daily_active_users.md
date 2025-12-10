# daily_active_users

**Type:** model  
**Database:** `workspace`  
**Schema:** `marts`  
**Unique ID:** `model.shanghai_transport.daily_active_users`

## Description

Daily active users metrics and trends

## Columns

| Column Name | Type | Description |
|------------|------|-------------|
| `active_users` | `bigint` |  |
| `avg_amount_per_transaction` | `decimal(14,6)` |  |
| `avg_transactions_per_user` | `double` |  |
| `date` | `date` |  |
| `entry_transactions` | `bigint` |  |
| `exit_transactions` | `bigint` |  |
| `is_weekend` | `boolean` |  |
| `total_amount` | `decimal(20,2)` |  |
| `total_transactions` | `bigint` |  |

## Statistics

- **rows:** 30
- **bytes:** 3793

## Lineage

### Upstream Dependencies

This model depends on:

- `shanghai_transport.fact_transactions`
- `shanghai_transport.dim_time`

### Downstream Dependencies

The following models depend on this model:

- `test.shanghai_transport.assert_daily_metrics_consistency`
- `test.shanghai_transport.unique_daily_active_users_date.c2111cde69`
- `test.shanghai_transport.not_null_daily_active_users_date.1e2c635a6b`
- `test.shanghai_transport.not_null_daily_active_users_active_users.ebe70ee4d8`
- `test.shanghai_transport.not_null_daily_active_users_total_transactions.8b25b7fc39`
- `test.shanghai_transport.not_null_daily_active_users_total_amount.483528c25f`

## Metadata

- **Materialized as:** table
- **Tags:** 
