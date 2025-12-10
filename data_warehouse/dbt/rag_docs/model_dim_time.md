# dim_time

**Type:** model  
**Database:** `workspace`  
**Schema:** `dimensions`  
**Unique ID:** `model.shanghai_transport.dim_time`

## Description

Time dimension table with date attributes

## Columns

| Column Name | Type | Description |
|------------|------|-------------|
| `date_day` | `timestamp` |  |
| `date_key` | `integer` |  |
| `day_of_month` | `integer` |  |
| `day_of_week` | `integer` |  |
| `day_of_week_name` | `string` |  |
| `day_of_year` | `integer` |  |
| `is_holiday` | `boolean` |  |
| `is_weekend` | `boolean` |  |
| `month_name` | `string` |  |
| `month_number` | `integer` |  |
| `quarter` | `integer` |  |
| `week_of_year` | `integer` |  |
| `year` | `integer` |  |

## Statistics

- **rows:** 730
- **bytes:** 9050

## Lineage

### Downstream Dependencies

The following models depend on this model:

- `shanghai_transport.fact_topups`
- `shanghai_transport.fact_transactions`
- `shanghai_transport.daily_active_users`
- `shanghai_transport.daily_topup_summary`
- `shanghai_transport.station_flow_daily`
- `test.shanghai_transport.unique_dim_time_date_key.c815c3216d`
- `test.shanghai_transport.not_null_dim_time_date_key.668b84ffec`
- `test.shanghai_transport.unique_dim_time_date_day.d8637451e0`
- `test.shanghai_transport.not_null_dim_time_date_day.f8d7dcdffa`
- `test.shanghai_transport.not_null_dim_time_day_of_week.296786d878`
- `test.shanghai_transport.not_null_dim_time_day_of_week_name.5a97a1b7a3`
- `test.shanghai_transport.not_null_dim_time_day_of_month.2366c8be4e`
- `test.shanghai_transport.not_null_dim_time_day_of_year.cb6765058c`
- `test.shanghai_transport.not_null_dim_time_week_of_year.068933b181`
- `test.shanghai_transport.not_null_dim_time_month_number.717cfb859a`
- `test.shanghai_transport.not_null_dim_time_month_name.5b491402b4`
- `test.shanghai_transport.not_null_dim_time_quarter.feeb266fc1`
- `test.shanghai_transport.not_null_dim_time_year.6fb9595d53`
- `test.shanghai_transport.not_null_dim_time_is_weekend.f294374ebd`
- `test.shanghai_transport.relationships_fact_transactions_date_key__date_key__ref_dim_time_.ae943d57ac`
- `test.shanghai_transport.relationships_fact_topups_date_key__date_key__ref_dim_time_.f46e457e3c`

## Metadata

- **Materialized as:** table
- **Tags:** 
