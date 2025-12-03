WITH source AS (
    SELECT * FROM {{ source('raw', 'src_stations') }}
),

cleaned AS (
    SELECT
        station_id,
        TRIM(station_name) AS station_name,
        TRIM(station_type) AS station_type,
        CAST(latitude AS DECIMAL(10, 6)) AS latitude,
        CAST(longitude AS DECIMAL(10, 6)) AS longitude,
        created_at
    FROM source
    WHERE station_id IS NOT NULL
        AND station_name IS NOT NULL
        AND station_type IS NOT NULL
        AND latitude IS NOT NULL
        AND longitude IS NOT NULL
        AND latitude BETWEEN 30.0 AND 32.0
        AND longitude BETWEEN 120.0 AND 122.0
)

SELECT * FROM cleaned
