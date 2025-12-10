# dbt Project Lineage Graph

Generated on: 2025-12-10 18:41:52

This document shows the complete data lineage for all models and sources.

## Sources

### raw.src_users

**Used by:**
- `shanghai_transport.stg_users`

### raw.src_stations

**Used by:**
- `shanghai_transport.stg_stations`

### raw.src_routes

**Used by:**
- `shanghai_transport.stg_routes`

### raw.src_transactions

**Used by:**
- `shanghai_transport.stg_transactions`

### raw.src_topups

**Used by:**
- `shanghai_transport.stg_topups`

## Staging Layer

### stg_routes

**Depends on:**
- `shanghai_transport.raw.src_routes`

**Used by:**
- `shanghai_transport.dim_route`
- `test.shanghai_transport.unique_stg_routes_route_id.04085681c2`
- `test.shanghai_transport.not_null_stg_routes_route_id.bff549db32`
- `test.shanghai_transport.not_null_stg_routes_route_name.134934506a`
- `test.shanghai_transport.not_null_stg_routes_route_type.0cbc75e598`
- `test.shanghai_transport.accepted_values_stg_routes_route_type__Metro__Bus__Ferry__Other.0e9be30d31`
- `test.shanghai_transport.relationships_stg_transactions_route_id__route_id__ref_stg_routes_.61db3dd698`

### stg_stations

**Depends on:**
- `shanghai_transport.raw.src_stations`

**Used by:**
- `shanghai_transport.dim_station`
- `test.shanghai_transport.unique_stg_stations_station_id.cc6df0deeb`
- `test.shanghai_transport.not_null_stg_stations_station_id.88327b742a`
- `test.shanghai_transport.not_null_stg_stations_station_name.06602c6638`
- `test.shanghai_transport.not_null_stg_stations_station_type.5aef6b7d63`
- `test.shanghai_transport.accepted_values_stg_stations_station_type__Metro__Bus__Ferry__Other.0709f74a94`
- `test.shanghai_transport.not_null_stg_stations_latitude.145c98253c`
- `test.shanghai_transport.not_null_stg_stations_longitude.3fe57995d9`
- `test.shanghai_transport.relationships_stg_transactions_station_id__station_id__ref_stg_stations_.126cd25e97`

### stg_topups

**Depends on:**
- `shanghai_transport.raw.src_topups`

**Used by:**
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

### stg_transactions

**Depends on:**
- `shanghai_transport.raw.src_transactions`

**Used by:**
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

### stg_users

**Depends on:**
- `shanghai_transport.raw.src_users`

**Used by:**
- `shanghai_transport.dim_user`
- `test.shanghai_transport.unique_stg_users_user_id.c2ff477e6b`
- `test.shanghai_transport.not_null_stg_users_user_id.980dfc1b77`
- `test.shanghai_transport.not_null_stg_users_card_number.6a8fd8695c`
- `test.shanghai_transport.not_null_stg_users_card_type.f5b5fa80a6`
- `test.shanghai_transport.accepted_values_stg_users_card_type__Regular__Student__Senior__Disabled.32588e75c8`
- `test.shanghai_transport.not_null_stg_users_is_verified.2168b06f59`
- `test.shanghai_transport.relationships_stg_transactions_user_id__user_id__ref_stg_users_.7fcea8eb2e`
- `test.shanghai_transport.relationships_stg_topups_user_id__user_id__ref_stg_users_.73060b2a60`

## Dimensions Layer

### dim_route

**Depends on:**
- `shanghai_transport.stg_routes`

**Used by:**
- `shanghai_transport.fact_transactions`
- `shanghai_transport.route_usage_summary`
- `test.shanghai_transport.unique_dim_route_route_key.3ef0a63b5d`
- `test.shanghai_transport.not_null_dim_route_route_key.100ea7aa1d`
- `test.shanghai_transport.unique_dim_route_route_id.467cac8cbd`
- `test.shanghai_transport.not_null_dim_route_route_id.e10f03ce9e`
- `test.shanghai_transport.not_null_dim_route_route_name.953d27bd7a`
- `test.shanghai_transport.not_null_dim_route_route_type.001d8f8c47`
- `test.shanghai_transport.accepted_values_dim_route_route_type__Metro__Bus__Ferry__Other.31b5feb3ba`
- `test.shanghai_transport.relationships_fact_transactions_route_key__route_key__ref_dim_route_.57f9fa5e0e`

### dim_station

**Depends on:**
- `shanghai_transport.stg_stations`

**Used by:**
- `shanghai_transport.fact_transactions`
- `shanghai_transport.station_flow_daily`
- `test.shanghai_transport.unique_dim_station_station_key.22b4b7393b`
- `test.shanghai_transport.not_null_dim_station_station_key.cd74fedb47`
- `test.shanghai_transport.unique_dim_station_station_id.118f0d4d56`
- `test.shanghai_transport.not_null_dim_station_station_id.34954bc218`
- `test.shanghai_transport.not_null_dim_station_station_name.264a600ac8`
- `test.shanghai_transport.not_null_dim_station_station_type.fc83bd32b5`
- `test.shanghai_transport.accepted_values_dim_station_station_type__Metro__Bus__Ferry__Other.5bd971ba0a`
- `test.shanghai_transport.not_null_dim_station_latitude.1d363d2a09`
- `test.shanghai_transport.not_null_dim_station_longitude.43a6bcd699`
- `test.shanghai_transport.relationships_fact_transactions_station_key__station_key__ref_dim_station_.622949e741`

### dim_time

**Used by:**
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

### dim_user

**Depends on:**
- `shanghai_transport.stg_users`

**Used by:**
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

## Facts Layer

### fact_topups

**Depends on:**
- `shanghai_transport.stg_topups`
- `shanghai_transport.dim_user`
- `shanghai_transport.dim_time`

**Used by:**
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

### fact_transactions

**Depends on:**
- `shanghai_transport.stg_transactions`
- `shanghai_transport.dim_user`
- `shanghai_transport.dim_station`
- `shanghai_transport.dim_route`
- `shanghai_transport.dim_time`

**Used by:**
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

## Marts Layer

### daily_active_users

**Depends on:**
- `shanghai_transport.fact_transactions`
- `shanghai_transport.dim_time`

**Used by:**
- `test.shanghai_transport.assert_daily_metrics_consistency`
- `test.shanghai_transport.unique_daily_active_users_date.c2111cde69`
- `test.shanghai_transport.not_null_daily_active_users_date.1e2c635a6b`
- `test.shanghai_transport.not_null_daily_active_users_active_users.ebe70ee4d8`
- `test.shanghai_transport.not_null_daily_active_users_total_transactions.8b25b7fc39`
- `test.shanghai_transport.not_null_daily_active_users_total_amount.483528c25f`

### daily_topup_summary

**Depends on:**
- `shanghai_transport.fact_topups`
- `shanghai_transport.dim_time`

**Used by:**
- `test.shanghai_transport.unique_daily_topup_summary_date.a73fee264f`
- `test.shanghai_transport.not_null_daily_topup_summary_date.6fecde3ac9`
- `test.shanghai_transport.not_null_daily_topup_summary_total_topups.8e7010d44c`
- `test.shanghai_transport.not_null_daily_topup_summary_unique_users.da4d742e2f`
- `test.shanghai_transport.not_null_daily_topup_summary_total_amount.4ef2aef4a4`

### route_usage_summary

**Depends on:**
- `shanghai_transport.fact_transactions`
- `shanghai_transport.dim_route`

**Used by:**
- `test.shanghai_transport.unique_route_usage_summary_route_id.bb0def57e3`
- `test.shanghai_transport.not_null_route_usage_summary_route_id.58b6a368e7`
- `test.shanghai_transport.not_null_route_usage_summary_route_name.57b1cd0b09`
- `test.shanghai_transport.not_null_route_usage_summary_route_type.e174934ed5`
- `test.shanghai_transport.not_null_route_usage_summary_total_transactions.4a883e6f34`
- `test.shanghai_transport.not_null_route_usage_summary_unique_users.3734a88813`

### station_flow_daily

**Depends on:**
- `shanghai_transport.fact_transactions`
- `shanghai_transport.dim_station`
- `shanghai_transport.dim_time`

**Used by:**
- `test.shanghai_transport.not_null_station_flow_daily_date.a129a6d500`
- `test.shanghai_transport.not_null_station_flow_daily_station_id.b2063f94c5`
- `test.shanghai_transport.not_null_station_flow_daily_station_name.c472ae6099`
- `test.shanghai_transport.not_null_station_flow_daily_station_type.7a21f668bc`
- `test.shanghai_transport.not_null_station_flow_daily_total_transactions.fcd6ac11fe`
- `test.shanghai_transport.not_null_station_flow_daily_unique_users.29b0b6a44d`

### user_card_type_summary

**Depends on:**
- `shanghai_transport.dim_user`
- `shanghai_transport.fact_transactions`
- `shanghai_transport.fact_topups`

**Used by:**
- `test.shanghai_transport.unique_user_card_type_summary_card_type.26aad030dd`
- `test.shanghai_transport.not_null_user_card_type_summary_card_type.cfadc65b8e`
- `test.shanghai_transport.not_null_user_card_type_summary_total_users.b170a993d5`
