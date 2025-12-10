# station_flow_daily

**Type:** model  
**Database:** `workspace`  
**Schema:** `marts`  
**Unique ID:** `model.shanghai_transport.station_flow_daily`

## Description

Daily station flow metrics

## Columns

| Column Name | Type | Description |
|------------|------|-------------|
| `date` | `date` |  |
| `entry_count` | `bigint` |  |
| `exit_count` | `bigint` |  |
| `is_weekend` | `boolean` |  |
| `station_id` | `bigint` |  |
| `station_name` | `string` |  |
| `station_type` | `string` |  |
| `total_amount` | `decimal(20,2)` |  |
| `total_transactions` | `bigint` |  |
| `unique_users` | `bigint` |  |

## Statistics

- **rows:** 4020
- **bytes:** 34175

## Lineage

### Upstream Dependencies

This model depends on:

- `shanghai_transport.fact_transactions`
- `shanghai_transport.dim_station`
- `shanghai_transport.dim_time`

### Downstream Dependencies

The following models depend on this model:

- `test.shanghai_transport.not_null_station_flow_daily_date.a129a6d500`
- `test.shanghai_transport.not_null_station_flow_daily_station_id.b2063f94c5`
- `test.shanghai_transport.not_null_station_flow_daily_station_name.c472ae6099`
- `test.shanghai_transport.not_null_station_flow_daily_station_type.7a21f668bc`
- `test.shanghai_transport.not_null_station_flow_daily_total_transactions.fcd6ac11fe`
- `test.shanghai_transport.not_null_station_flow_daily_unique_users.29b0b6a44d`

## Metadata

- **Materialized as:** table
- **Tags:** 
