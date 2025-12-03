{{
    config(
        materialized='table',
        schema='dimensions'
    )
}}
-- Station dimension table
-- Includes surrogate key and all station attributes

WITH source AS (
    SELECT * FROM {{ ref('stg_stations') }}
),

dimension AS (
    SELECT
        -- Surrogate key (hash of business key)
        {{ dbt_utils.generate_surrogate_key(['station_id']) }} AS station_key,
        
        -- Business key
        station_id,
        
        -- Station attributes
        station_name,
        station_type,
        latitude,
        longitude,
        
        -- Timestamps
        created_at,
        CURRENT_TIMESTAMP() AS dbt_updated_at
        
    FROM source
)

SELECT * FROM dimension

