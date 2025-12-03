WITH source AS (
    SELECT * FROM {{ source('raw', 'src_topups') }}
),

cleaned AS (
    SELECT
        topup_id,
        user_id,
        CAST(topup_date AS DATE) AS topup_date,
        CAST(topup_time AS TIMESTAMP) AS topup_time,
        CAST(CONCAT(CAST(topup_date AS STRING), ' ', CAST(topup_time AS STRING)) AS TIMESTAMP) AS topup_datetime,
        CAST(amount AS DECIMAL(10, 2)) AS amount,
        TRIM(payment_method) AS payment_method,
        created_at
    FROM source
    WHERE topup_id IS NOT NULL
        AND user_id IS NOT NULL
        AND topup_date IS NOT NULL
        AND topup_date >= '2024-01-01'
        AND amount IS NOT NULL
        AND amount > 0
        AND payment_method IS NOT NULL
)

SELECT * FROM cleaned
