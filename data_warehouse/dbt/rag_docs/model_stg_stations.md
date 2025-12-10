# stg_stations

**Type:** model  
**Database:** `workspace`  
**Schema:** `staging`  
**Unique ID:** `model.shanghai_transport.stg_stations`

## Description

Cleaned station data from source

## Columns

| Column Name | Type | Description |
|------------|------|-------------|
| `created_at` | `timestamp` |  |
| `latitude` | `decimal(10,6)` |  |
| `longitude` | `decimal(10,6)` |  |
| `station_id` | `bigint` |  |
| `station_name` | `string` |  |
| `station_type` | `string` |  |

## Statistics

- **rows:** 134
- **bytes:** 4043

## Lineage

### Upstream Dependencies

This model depends on:

- `shanghai_transport.raw.src_stations`

### Downstream Dependencies

The following models depend on this model:

- `shanghai_transport.dim_station`
- `test.shanghai_transport.unique_stg_stations_station_id.cc6df0deeb`
- `test.shanghai_transport.not_null_stg_stations_station_id.88327b742a`
- `test.shanghai_transport.not_null_stg_stations_station_name.06602c6638`
- `test.shanghai_transport.not_null_stg_stations_station_type.5aef6b7d63`
- `test.shanghai_transport.accepted_values_stg_stations_station_type__Metro__Bus__Ferry__Other.0709f74a94`
- `test.shanghai_transport.not_null_stg_stations_latitude.145c98253c`
- `test.shanghai_transport.not_null_stg_stations_longitude.3fe57995d9`
- `test.shanghai_transport.relationships_stg_transactions_station_id__station_id__ref_stg_stations_.126cd25e97`

## Metadata

- **Materialized as:** table
- **Tags:** 
