WITH source AS (
    SELECT * FROM {{ source('raw', 'src_users') }}
),

cleaned AS (
    SELECT
        user_id,
        card_number,
        TRIM(card_type) AS card_type,
        COALESCE(is_verified, FALSE) AS is_verified,
        created_at,
        updated_at
    FROM source
    WHERE user_id IS NOT NULL
        AND card_number IS NOT NULL
        AND card_type IS NOT NULL
)

SELECT * FROM cleaned
