{{
    config(
        materialized='table',
        schema='marts'
    )
}}
-- Route usage summary metrics
-- Aggregates transaction data by route

WITH transactions AS (
    SELECT 
        f.*,
        r.route_id,
        r.route_name,
        r.route_type
    FROM {{ ref('fact_transactions') }} f
    JOIN {{ ref('dim_route') }} r ON f.route_key = r.route_key
),

route_metrics AS (
    SELECT
        route_id,
        route_name,
        route_type,
        
        -- Transaction metrics
        COUNT(*) AS total_transactions,
        COUNT(DISTINCT user_key) AS unique_users,
        SUM(amount) AS total_amount,
        
        -- Time-based metrics
        COUNT(*) / COUNT(DISTINCT transaction_date) AS avg_transactions_per_day,
        MIN(transaction_date) AS first_transaction_date,
        MAX(transaction_date) AS last_transaction_date
        
    FROM transactions
    GROUP BY route_id, route_name, route_type
)

SELECT * FROM route_metrics
ORDER BY total_transactions DESC

