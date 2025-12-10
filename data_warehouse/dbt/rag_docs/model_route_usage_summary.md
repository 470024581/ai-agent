# route_usage_summary

**Type:** model  
**Database:** `workspace`  
**Schema:** `marts`  
**Unique ID:** `model.shanghai_transport.route_usage_summary`

## Description

Route usage summary metrics

## Columns

| Column Name | Type | Description |
|------------|------|-------------|
| `avg_transactions_per_day` | `double` |  |
| `first_transaction_date` | `date` |  |
| `last_transaction_date` | `date` |  |
| `route_id` | `bigint` |  |
| `route_name` | `string` |  |
| `route_type` | `string` |  |
| `total_amount` | `decimal(20,2)` |  |
| `total_transactions` | `bigint` |  |
| `unique_users` | `bigint` |  |

## Statistics

- **rows:** 23
- **bytes:** 3494

## Lineage

### Upstream Dependencies

This model depends on:

- `shanghai_transport.fact_transactions`
- `shanghai_transport.dim_route`

### Downstream Dependencies

The following models depend on this model:

- `test.shanghai_transport.unique_route_usage_summary_route_id.bb0def57e3`
- `test.shanghai_transport.not_null_route_usage_summary_route_id.58b6a368e7`
- `test.shanghai_transport.not_null_route_usage_summary_route_name.57b1cd0b09`
- `test.shanghai_transport.not_null_route_usage_summary_route_type.e174934ed5`
- `test.shanghai_transport.not_null_route_usage_summary_total_transactions.4a883e6f34`
- `test.shanghai_transport.not_null_route_usage_summary_unique_users.3734a88813`

## Metadata

- **Materialized as:** table
- **Tags:** 
