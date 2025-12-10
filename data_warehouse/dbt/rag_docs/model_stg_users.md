# stg_users

**Type:** model  
**Database:** `workspace`  
**Schema:** `staging`  
**Unique ID:** `model.shanghai_transport.stg_users`

## Description

Cleaned user data from source

## Columns

| Column Name | Type | Description |
|------------|------|-------------|
| `card_number` | `string` |  |
| `card_type` | `string` |  |
| `created_at` | `timestamp` |  |
| `is_verified` | `boolean` |  |
| `updated_at` | `timestamp` |  |
| `user_id` | `bigint` |  |

## Statistics

- **rows:** 1000
- **bytes:** 15150

## Lineage

### Upstream Dependencies

This model depends on:

- `shanghai_transport.raw.src_users`

### Downstream Dependencies

The following models depend on this model:

- `shanghai_transport.dim_user`
- `test.shanghai_transport.unique_stg_users_user_id.c2ff477e6b`
- `test.shanghai_transport.not_null_stg_users_user_id.980dfc1b77`
- `test.shanghai_transport.not_null_stg_users_card_number.6a8fd8695c`
- `test.shanghai_transport.not_null_stg_users_card_type.f5b5fa80a6`
- `test.shanghai_transport.accepted_values_stg_users_card_type__Regular__Student__Senior__Disabled.32588e75c8`
- `test.shanghai_transport.not_null_stg_users_is_verified.2168b06f59`
- `test.shanghai_transport.relationships_stg_transactions_user_id__user_id__ref_stg_users_.7fcea8eb2e`
- `test.shanghai_transport.relationships_stg_topups_user_id__user_id__ref_stg_users_.73060b2a60`

## Metadata

- **Materialized as:** table
- **Tags:** 
