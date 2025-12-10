# dim_route

**Type:** model  
**Database:** `workspace`  
**Schema:** `dimensions`  
**Unique ID:** `model.shanghai_transport.dim_route`

## Description

Route dimension table with surrogate keys

## Columns

| Column Name | Type | Description |
|------------|------|-------------|
| `created_at` | `timestamp` |  |
| `dbt_updated_at` | `timestamp` |  |
| `route_id` | `bigint` |  |
| `route_key` | `string` |  |
| `route_name` | `string` |  |
| `route_type` | `string` |  |

## Statistics

- **rows:** 23
- **bytes:** 2905

## Lineage

### Upstream Dependencies

This model depends on:

- `shanghai_transport.stg_routes`

### Downstream Dependencies

The following models depend on this model:

- `shanghai_transport.fact_transactions`
- `shanghai_transport.route_usage_summary`
- `test.shanghai_transport.unique_dim_route_route_key.3ef0a63b5d`
- `test.shanghai_transport.not_null_dim_route_route_key.100ea7aa1d`
- `test.shanghai_transport.unique_dim_route_route_id.467cac8cbd`
- `test.shanghai_transport.not_null_dim_route_route_id.e10f03ce9e`
- `test.shanghai_transport.not_null_dim_route_route_name.953d27bd7a`
- `test.shanghai_transport.not_null_dim_route_route_type.001d8f8c47`
- `test.shanghai_transport.accepted_values_dim_route_route_type__Metro__Bus__Ferry__Other.31b5feb3ba`
- `test.shanghai_transport.relationships_fact_transactions_route_key__route_key__ref_dim_route_.57f9fa5e0e`

## Metadata

- **Materialized as:** table
- **Tags:** 
