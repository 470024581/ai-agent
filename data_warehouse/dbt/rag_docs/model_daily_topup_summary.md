# daily_topup_summary

**Type:** model  
**Database:** `workspace`  
**Schema:** `marts`  
**Unique ID:** `model.shanghai_transport.daily_topup_summary`

## Description

Daily top-up summary metrics

## Columns

| Column Name | Type | Description |
|------------|------|-------------|
| `avg_amount_per_topup` | `decimal(14,6)` |  |
| `avg_amount_per_user` | `decimal(38,20)` |  |
| `card_topups` | `bigint` |  |
| `cash_topups` | `bigint` |  |
| `date` | `date` |  |
| `is_weekend` | `boolean` |  |
| `mobile_topups` | `bigint` |  |
| `online_topups` | `bigint` |  |
| `total_amount` | `decimal(20,2)` |  |
| `total_topups` | `bigint` |  |
| `unique_users` | `bigint` |  |

## Statistics

- **rows:** 30
- **bytes:** 4726

## Lineage

### Upstream Dependencies

This model depends on:

- `shanghai_transport.fact_topups`
- `shanghai_transport.dim_time`

### Downstream Dependencies

The following models depend on this model:

- `test.shanghai_transport.unique_daily_topup_summary_date.a73fee264f`
- `test.shanghai_transport.not_null_daily_topup_summary_date.6fecde3ac9`
- `test.shanghai_transport.not_null_daily_topup_summary_total_topups.8e7010d44c`
- `test.shanghai_transport.not_null_daily_topup_summary_unique_users.da4d742e2f`
- `test.shanghai_transport.not_null_daily_topup_summary_total_amount.4ef2aef4a4`

## Metadata

- **Materialized as:** table
- **Tags:** 
