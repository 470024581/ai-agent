{{
    config(
        materialized='table',
        schema='public'
    )
}}
-- Route dimension table
-- Includes surrogate key and all route attributes

WITH source AS (
    SELECT * FROM {{ ref('stg_routes') }}
),

dimension AS (
    SELECT
        -- Surrogate key (hash of business key)
        {{ dbt_utils.generate_surrogate_key(['route_id']) }} AS route_key,
        
        -- Business key
        route_id,
        
        -- Route attributes
        route_name,
        route_type,
        
        -- Timestamps
        created_at,
        CURRENT_TIMESTAMP() AS dbt_updated_at
        
    FROM source
)

SELECT * FROM dimension

