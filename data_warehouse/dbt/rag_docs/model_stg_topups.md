# stg_topups

**Type:** model  
**Database:** `workspace`  
**Schema:** `staging`  
**Unique ID:** `model.shanghai_transport.stg_topups`

## Description

Cleaned top-up data from source

## Columns

| Column Name | Type | Description |
|------------|------|-------------|
| `amount` | `decimal(10,2)` |  |
| `created_at` | `timestamp` |  |
| `payment_method` | `string` |  |
| `topup_date` | `date` |  |
| `topup_datetime` | `timestamp` |  |
| `topup_id` | `bigint` |  |
| `topup_time` | `timestamp` |  |
| `user_id` | `bigint` |  |

## Statistics

- **rows:** 1038
- **bytes:** 21213

## Lineage

### Upstream Dependencies

This model depends on:

- `shanghai_transport.raw.src_topups`

### Downstream Dependencies

The following models depend on this model:

- `shanghai_transport.fact_topups`
- `test.shanghai_transport.unique_stg_topups_topup_id.8ccfe7652f`
- `test.shanghai_transport.not_null_stg_topups_topup_id.d656b347dd`
- `test.shanghai_transport.not_null_stg_topups_user_id.371198c3da`
- `test.shanghai_transport.relationships_stg_topups_user_id__user_id__ref_stg_users_.73060b2a60`
- `test.shanghai_transport.not_null_stg_topups_topup_date.762f7dee8e`
- `test.shanghai_transport.not_null_stg_topups_topup_datetime.4aff5d897c`
- `test.shanghai_transport.not_null_stg_topups_amount.b9a5b89a11`
- `test.shanghai_transport.not_null_stg_topups_payment_method.ff40779169`
- `test.shanghai_transport.accepted_values_stg_topups_payment_method__Cash__Card__Mobile__Online__Other.d33c9879aa`

## Metadata

- **Materialized as:** table
- **Tags:** 
