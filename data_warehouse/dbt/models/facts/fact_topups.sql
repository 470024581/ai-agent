{{
    config(
        materialized='table',
        schema='public',
        partition_by=['topup_date']
    )
}}
-- Top-up fact table
-- Links to user and time dimensions
-- Partitioned by topup_date for query performance

WITH topups AS (
    SELECT * FROM {{ ref('stg_topups') }}
),

dim_user AS (
    SELECT user_key, user_id FROM {{ ref('dim_user') }}
),

dim_time AS (
    SELECT date_key, date_day FROM {{ ref('dim_time') }}
),

fact AS (
    SELECT
        -- Surrogate key (hash of business key)
        {{ dbt_utils.generate_surrogate_key(['t.topup_id']) }} AS topup_key,
        
        -- Business key
        t.topup_id,
        
        -- Foreign keys to dimensions
        u.user_key,
        d.date_key,
        
        -- Degenerate dimensions (attributes stored in fact table)
        t.topup_date,
        t.topup_datetime,
        
        -- Measures
        t.amount,
        t.payment_method,
        
        -- Timestamps
        t.created_at,
        CURRENT_TIMESTAMP() AS dbt_updated_at
        
    FROM topups t
    
    -- Join dimensions
    LEFT JOIN dim_user u 
        ON t.user_id = u.user_id
    LEFT JOIN dim_time d 
        ON t.topup_date = d.date_day
)

SELECT * FROM fact

