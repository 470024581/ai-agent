# fact_topups

**Type:** model  
**Database:** `workspace`  
**Schema:** `facts`  
**Unique ID:** `model.shanghai_transport.fact_topups`

## Description

Top-up fact table with dimension keys and measures

## Columns

| Column Name | Type | Description |
|------------|------|-------------|
| `amount` | `decimal(10,2)` |  |
| `created_at` | `timestamp` |  |
| `date_key` | `integer` |  |
| `dbt_updated_at` | `timestamp` |  |
| `payment_method` | `string` |  |
| `topup_date` | `date` |  |
| `topup_datetime` | `timestamp` |  |
| `topup_id` | `bigint` |  |
| `topup_key` | `string` |  |
| `user_key` | `string` |  |

## Statistics

- **rows:** 1038
- **bytes:** 163531

## Lineage

### Upstream Dependencies

This model depends on:

- `shanghai_transport.stg_topups`
- `shanghai_transport.dim_user`
- `shanghai_transport.dim_time`

### Downstream Dependencies

The following models depend on this model:

- `shanghai_transport.daily_topup_summary`
- `shanghai_transport.user_card_type_summary`
- `test.shanghai_transport.assert_positive_topup_amounts`
- `test.shanghai_transport.unique_fact_topups_topup_key.7928e4d0b8`
- `test.shanghai_transport.not_null_fact_topups_topup_key.8af5135545`
- `test.shanghai_transport.unique_fact_topups_topup_id.4d1451043d`
- `test.shanghai_transport.not_null_fact_topups_topup_id.3577af745a`
- `test.shanghai_transport.not_null_fact_topups_user_key.8bf6fb97e5`
- `test.shanghai_transport.relationships_fact_topups_user_key__user_key__ref_dim_user_.482074af32`
- `test.shanghai_transport.not_null_fact_topups_date_key.eb8b5f9088`
- `test.shanghai_transport.relationships_fact_topups_date_key__date_key__ref_dim_time_.f46e457e3c`
- `test.shanghai_transport.not_null_fact_topups_topup_date.ffd0058113`
- `test.shanghai_transport.not_null_fact_topups_topup_datetime.b743ef085e`
- `test.shanghai_transport.not_null_fact_topups_amount.b0e48c2c72`
- `test.shanghai_transport.not_null_fact_topups_payment_method.66268f739d`
- `test.shanghai_transport.accepted_values_fact_topups_payment_method__Cash__Card__Mobile__Online__Other.24c4307280`

## Metadata

- **Materialized as:** table
- **Tags:** 
