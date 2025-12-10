# stg_transactions

**Type:** model  
**Database:** `workspace`  
**Schema:** `staging`  
**Unique ID:** `model.shanghai_transport.stg_transactions`

## Description

Cleaned transaction data from source

## Columns

| Column Name | Type | Description |
|------------|------|-------------|
| `amount` | `decimal(10,2)` |  |
| `created_at` | `timestamp` |  |
| `route_id` | `bigint` |  |
| `station_id` | `bigint` |  |
| `transaction_date` | `date` |  |
| `transaction_datetime` | `timestamp` |  |
| `transaction_id` | `bigint` |  |
| `transaction_time` | `timestamp` |  |
| `transaction_type` | `string` |  |
| `user_id` | `bigint` |  |

## Statistics

- **rows:** 150000
- **bytes:** 1713566

## Lineage

### Upstream Dependencies

This model depends on:

- `shanghai_transport.raw.src_transactions`

### Downstream Dependencies

The following models depend on this model:

- `shanghai_transport.fact_transactions`
- `test.shanghai_transport.unique_stg_transactions_transaction_id.ee9a78a396`
- `test.shanghai_transport.not_null_stg_transactions_transaction_id.1d00a8e2e4`
- `test.shanghai_transport.not_null_stg_transactions_user_id.b541614306`
- `test.shanghai_transport.relationships_stg_transactions_user_id__user_id__ref_stg_users_.7fcea8eb2e`
- `test.shanghai_transport.relationships_stg_transactions_station_id__station_id__ref_stg_stations_.126cd25e97`
- `test.shanghai_transport.relationships_stg_transactions_route_id__route_id__ref_stg_routes_.61db3dd698`
- `test.shanghai_transport.not_null_stg_transactions_transaction_date.353bde368c`
- `test.shanghai_transport.not_null_stg_transactions_transaction_datetime.d2def2593b`
- `test.shanghai_transport.not_null_stg_transactions_amount.3629b5421e`
- `test.shanghai_transport.not_null_stg_transactions_transaction_type.a76cf10735`
- `test.shanghai_transport.accepted_values_stg_transactions_transaction_type__Entry__Exit__Transfer__Top_up__Refund.9ced1c4991`

## Metadata

- **Materialized as:** table
- **Tags:** 
