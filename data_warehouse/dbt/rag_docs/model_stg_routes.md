# stg_routes

**Type:** model  
**Database:** `workspace`  
**Schema:** `staging`  
**Unique ID:** `model.shanghai_transport.stg_routes`

## Description

Cleaned route data from source

## Columns

| Column Name | Type | Description |
|------------|------|-------------|
| `created_at` | `timestamp` |  |
| `route_id` | `bigint` |  |
| `route_name` | `string` |  |
| `route_type` | `string` |  |

## Statistics

- **rows:** 23
- **bytes:** 1754

## Lineage

### Upstream Dependencies

This model depends on:

- `shanghai_transport.raw.src_routes`

### Downstream Dependencies

The following models depend on this model:

- `shanghai_transport.dim_route`
- `test.shanghai_transport.unique_stg_routes_route_id.04085681c2`
- `test.shanghai_transport.not_null_stg_routes_route_id.bff549db32`
- `test.shanghai_transport.not_null_stg_routes_route_name.134934506a`
- `test.shanghai_transport.not_null_stg_routes_route_type.0cbc75e598`
- `test.shanghai_transport.accepted_values_stg_routes_route_type__Metro__Bus__Ferry__Other.0e9be30d31`
- `test.shanghai_transport.relationships_stg_transactions_route_id__route_id__ref_stg_routes_.61db3dd698`

## Metadata

- **Materialized as:** table
- **Tags:** 
