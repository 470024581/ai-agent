WITH source AS (
    SELECT * FROM {{ source('raw', 'src_transactions') }}
),

cleaned AS (
    SELECT
        transaction_id,
        user_id,
        station_id,
        route_id,
        CAST(transaction_date AS DATE) AS transaction_date,
        CAST(transaction_time AS TIMESTAMP) AS transaction_time,
        CAST(CONCAT(CAST(transaction_date AS STRING), ' ', CAST(transaction_time AS STRING)) AS TIMESTAMP) AS transaction_datetime,
        CAST(amount AS DECIMAL(10, 2)) AS amount,
        TRIM(transaction_type) AS transaction_type,
        created_at
    FROM source
    WHERE transaction_id IS NOT NULL
        AND user_id IS NOT NULL
        AND transaction_date IS NOT NULL
        AND transaction_date >= '2024-01-01'
        AND amount IS NOT NULL
        AND amount >= 0
        AND transaction_type IS NOT NULL
)

SELECT * FROM cleaned
