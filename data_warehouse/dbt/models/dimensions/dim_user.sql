{{
    config(
        materialized='table',
        schema='dimensions'
    )
}}
-- User dimension table
-- Includes surrogate key and all user attributes

WITH source AS (
    SELECT * FROM {{ ref('stg_users') }}
),

dimension AS (
    SELECT
        -- Surrogate key (hash of business key)
        {{ dbt_utils.generate_surrogate_key(['user_id']) }} AS user_key,
        
        -- Business key
        user_id,
        
        -- User attributes
        card_number,
        card_type,
        is_verified,
        
        -- Timestamps
        created_at,
        updated_at,
        CURRENT_TIMESTAMP() AS dbt_updated_at
        
    FROM source
)

SELECT * FROM dimension

