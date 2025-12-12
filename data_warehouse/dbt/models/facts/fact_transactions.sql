{{
    config(
        materialized='table',
        schema='public',
        partition_by=['transaction_date']
    )
}}
-- Transaction fact table
-- Links to user, station, route, and time dimensions
-- Partitioned by transaction_date for query performance

WITH transactions AS (
    SELECT * FROM {{ ref('stg_transactions') }}
),

dim_user AS (
    SELECT user_key, user_id FROM {{ ref('dim_user') }}
),

dim_station AS (
    SELECT station_key, station_id FROM {{ ref('dim_station') }}
),

dim_route AS (
    SELECT route_key, route_id FROM {{ ref('dim_route') }}
),

dim_time AS (
    SELECT date_key, date_day FROM {{ ref('dim_time') }}
),

fact AS (
    SELECT
        -- Surrogate key (hash of business key)
        {{ dbt_utils.generate_surrogate_key(['t.transaction_id']) }} AS transaction_key,
        
        -- Business key
        t.transaction_id,
        
        -- Foreign keys to dimensions
        u.user_key,
        s.station_key,
        r.route_key,
        d.date_key,
        
        -- Degenerate dimensions (attributes stored in fact table)
        t.transaction_date,
        t.transaction_datetime,
        
        -- Measures
        t.amount,
        t.transaction_type,
        
        -- Timestamps
        t.created_at,
        CURRENT_TIMESTAMP() AS dbt_updated_at
        
    FROM transactions t
    
    -- Join dimensions
    LEFT JOIN dim_user u 
        ON t.user_id = u.user_id
    LEFT JOIN dim_station s 
        ON t.station_id = s.station_id
    LEFT JOIN dim_route r 
        ON t.route_id = r.route_id
    LEFT JOIN dim_time d 
        ON t.transaction_date = d.date_day
)

SELECT * FROM fact

