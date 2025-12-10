# fact_transactions

**Type:** model  
**Database:** `workspace`  
**Schema:** `facts`  
**Unique ID:** `model.shanghai_transport.fact_transactions`

## Description

Transaction fact table with dimension keys and measures

## Columns

| Column Name | Type | Description |
|------------|------|-------------|
| `amount` | `decimal(10,2)` |  |
| `created_at` | `timestamp` |  |
| `date_key` | `integer` |  |
| `dbt_updated_at` | `timestamp` |  |
| `route_key` | `string` |  |
| `station_key` | `string` |  |
| `transaction_date` | `date` |  |
| `transaction_datetime` | `timestamp` |  |
| `transaction_id` | `bigint` |  |
| `transaction_key` | `string` |  |
| `transaction_type` | `string` |  |
| `user_key` | `string` |  |

## Statistics

- **rows:** 150000
- **bytes:** 4962877

## Lineage

### Upstream Dependencies

This model depends on:

- `shanghai_transport.stg_transactions`
- `shanghai_transport.dim_user`
- `shanghai_transport.dim_station`
- `shanghai_transport.dim_route`
- `shanghai_transport.dim_time`

### Downstream Dependencies

The following models depend on this model:

- `shanghai_transport.daily_active_users`
- `shanghai_transport.route_usage_summary`
- `shanghai_transport.station_flow_daily`
- `shanghai_transport.user_card_type_summary`
- `test.shanghai_transport.assert_positive_amounts`
- `test.shanghai_transport.assert_valid_date_range`
- `test.shanghai_transport.unique_fact_transactions_transaction_key.191e525211`
- `test.shanghai_transport.not_null_fact_transactions_transaction_key.44599dd998`
- `test.shanghai_transport.unique_fact_transactions_transaction_id.4978e2a484`
- `test.shanghai_transport.not_null_fact_transactions_transaction_id.e79bae8750`
- `test.shanghai_transport.not_null_fact_transactions_user_key.2ab57c1644`
- `test.shanghai_transport.relationships_fact_transactions_user_key__user_key__ref_dim_user_.142f17cdb1`
- `test.shanghai_transport.relationships_fact_transactions_station_key__station_key__ref_dim_station_.622949e741`
- `test.shanghai_transport.relationships_fact_transactions_route_key__route_key__ref_dim_route_.57f9fa5e0e`
- `test.shanghai_transport.not_null_fact_transactions_date_key.a8e6f6a34b`
- `test.shanghai_transport.relationships_fact_transactions_date_key__date_key__ref_dim_time_.ae943d57ac`
- `test.shanghai_transport.not_null_fact_transactions_transaction_date.d07e810641`
- `test.shanghai_transport.not_null_fact_transactions_transaction_datetime.2201995bd7`
- `test.shanghai_transport.not_null_fact_transactions_amount.073f4954fa`
- `test.shanghai_transport.not_null_fact_transactions_transaction_type.dad7e48e39`
- `test.shanghai_transport.accepted_values_fact_transactions_transaction_type__Entry__Exit__Transfer__Top_up__Refund.87655d812b`

## Metadata

- **Materialized as:** table
- **Tags:** 
