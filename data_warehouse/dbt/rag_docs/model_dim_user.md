# dim_user

**Type:** model  
**Database:** `workspace`  
**Schema:** `dimensions`  
**Unique ID:** `model.shanghai_transport.dim_user`

## Description

User dimension table with surrogate keys

## Columns

| Column Name | Type | Description |
|------------|------|-------------|
| `card_number` | `string` |  |
| `card_type` | `string` |  |
| `created_at` | `timestamp` |  |
| `dbt_updated_at` | `timestamp` |  |
| `is_verified` | `boolean` |  |
| `updated_at` | `timestamp` |  |
| `user_id` | `bigint` |  |
| `user_key` | `string` |  |

## Statistics

- **rows:** 1000
- **bytes:** 33395

## Lineage

### Upstream Dependencies

This model depends on:

- `shanghai_transport.stg_users`

### Downstream Dependencies

The following models depend on this model:

- `shanghai_transport.fact_topups`
- `shanghai_transport.fact_transactions`
- `shanghai_transport.user_card_type_summary`
- `test.shanghai_transport.assert_dimension_integrity`
- `test.shanghai_transport.unique_dim_user_user_key.18728c07d2`
- `test.shanghai_transport.not_null_dim_user_user_key.546af3575d`
- `test.shanghai_transport.unique_dim_user_user_id.eff0a2a278`
- `test.shanghai_transport.not_null_dim_user_user_id.4b202b08a3`
- `test.shanghai_transport.not_null_dim_user_card_number.7629d9e603`
- `test.shanghai_transport.not_null_dim_user_card_type.860eee5310`
- `test.shanghai_transport.accepted_values_dim_user_card_type__Regular__Student__Senior__Disabled.2a484a548e`
- `test.shanghai_transport.not_null_dim_user_is_verified.297375bbd8`
- `test.shanghai_transport.relationships_fact_transactions_user_key__user_key__ref_dim_user_.142f17cdb1`
- `test.shanghai_transport.relationships_fact_topups_user_key__user_key__ref_dim_user_.482074af32`

## Metadata

- **Materialized as:** table
- **Tags:** 
