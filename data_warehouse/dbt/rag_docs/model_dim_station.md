# dim_station

**Type:** model  
**Database:** `workspace`  
**Schema:** `dimensions`  
**Unique ID:** `model.shanghai_transport.dim_station`

## Description

Station dimension table with surrogate keys

## Columns

| Column Name | Type | Description |
|------------|------|-------------|
| `created_at` | `timestamp` |  |
| `dbt_updated_at` | `timestamp` |  |
| `latitude` | `decimal(10,6)` |  |
| `longitude` | `decimal(10,6)` |  |
| `station_id` | `bigint` |  |
| `station_key` | `string` |  |
| `station_name` | `string` |  |
| `station_type` | `string` |  |

## Statistics

- **rows:** 134
- **bytes:** 7180

## Lineage

### Upstream Dependencies

This model depends on:

- `shanghai_transport.stg_stations`

### Downstream Dependencies

The following models depend on this model:

- `shanghai_transport.fact_transactions`
- `shanghai_transport.station_flow_daily`
- `test.shanghai_transport.unique_dim_station_station_key.22b4b7393b`
- `test.shanghai_transport.not_null_dim_station_station_key.cd74fedb47`
- `test.shanghai_transport.unique_dim_station_station_id.118f0d4d56`
- `test.shanghai_transport.not_null_dim_station_station_id.34954bc218`
- `test.shanghai_transport.not_null_dim_station_station_name.264a600ac8`
- `test.shanghai_transport.not_null_dim_station_station_type.fc83bd32b5`
- `test.shanghai_transport.accepted_values_dim_station_station_type__Metro__Bus__Ferry__Other.5bd971ba0a`
- `test.shanghai_transport.not_null_dim_station_latitude.1d363d2a09`
- `test.shanghai_transport.not_null_dim_station_longitude.43a6bcd699`
- `test.shanghai_transport.relationships_fact_transactions_station_key__station_key__ref_dim_station_.622949e741`

## Metadata

- **Materialized as:** table
- **Tags:** 
