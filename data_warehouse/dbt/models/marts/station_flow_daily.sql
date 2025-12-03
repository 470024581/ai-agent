{{
    config(
        materialized='table',
        schema='marts'
    )
}}
-- Daily station flow metrics
-- Aggregates transaction data by date and station

WITH transactions AS (
    SELECT 
        f.*,
        s.station_id,
        s.station_name,
        s.station_type,
        d.is_weekend
    FROM {{ ref('fact_transactions') }} f
    JOIN {{ ref('dim_station') }} s ON f.station_key = s.station_key
    JOIN {{ ref('dim_time') }} d ON f.date_key = d.date_key
),

station_metrics AS (
    SELECT
        transaction_date AS date,
        station_id,
        station_name,
        station_type,
        
        -- Transaction metrics
        COUNT(*) AS total_transactions,
        COUNT(DISTINCT user_key) AS unique_users,
        
        -- Entry/Exit breakdown
        SUM(CASE WHEN transaction_type = 'Entry' THEN 1 ELSE 0 END) AS entry_count,
        SUM(CASE WHEN transaction_type = 'Exit' THEN 1 ELSE 0 END) AS exit_count,
        
        -- Amount metrics
        SUM(amount) AS total_amount,
        
        -- Time attributes
        MAX(is_weekend) AS is_weekend
        
    FROM transactions
    GROUP BY transaction_date, station_id, station_name, station_type
)

SELECT * FROM station_metrics
ORDER BY date DESC, total_transactions DESC

