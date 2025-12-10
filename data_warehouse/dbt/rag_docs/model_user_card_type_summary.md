# user_card_type_summary

**Type:** model  
**Database:** `workspace`  
**Schema:** `marts`  
**Unique ID:** `model.shanghai_transport.user_card_type_summary`

## Description

User summary by card type

## Columns

| Column Name | Type | Description |
|------------|------|-------------|
| `avg_topup_per_user` | `double` |  |
| `avg_transactions_per_user` | `double` |  |
| `card_type` | `string` |  |
| `total_topup_amount` | `decimal(20,2)` |  |
| `total_topups` | `bigint` |  |
| `total_transaction_amount` | `decimal(20,2)` |  |
| `total_transactions` | `bigint` |  |
| `total_users` | `bigint` |  |
| `verified_users` | `bigint` |  |

## Statistics

- **rows:** 4
- **bytes:** 3181

## Lineage

### Upstream Dependencies

This model depends on:

- `shanghai_transport.dim_user`
- `shanghai_transport.fact_transactions`
- `shanghai_transport.fact_topups`

### Downstream Dependencies

The following models depend on this model:

- `test.shanghai_transport.unique_user_card_type_summary_card_type.26aad030dd`
- `test.shanghai_transport.not_null_user_card_type_summary_card_type.cfadc65b8e`
- `test.shanghai_transport.not_null_user_card_type_summary_total_users.b170a993d5`

## Metadata

- **Materialized as:** table
- **Tags:** 
