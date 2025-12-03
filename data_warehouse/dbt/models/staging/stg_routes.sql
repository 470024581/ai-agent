WITH source AS (
    SELECT * FROM {{ source('raw', 'src_routes') }}
),

cleaned AS (
    SELECT
        route_id,
        TRIM(route_name) AS route_name,
        TRIM(route_type) AS route_type,
        created_at
    FROM source
    WHERE route_id IS NOT NULL
        AND route_name IS NOT NULL
        AND route_type IS NOT NULL
)

SELECT * FROM cleaned
