{{
    config(
        materialized='table',
        schema='marts'
    )
}}
-- Daily active users metrics
-- Aggregates transaction data by date with user activity metrics

WITH transactions AS (
    SELECT 
        f.*,
        d.is_weekend
    FROM {{ ref('fact_transactions') }} f
    JOIN {{ ref('dim_time') }} d ON f.date_key = d.date_key
),

daily_metrics AS (
    SELECT
        transaction_date AS date,
        
        -- User metrics
        COUNT(DISTINCT user_key) AS active_users,
        
        -- Transaction metrics
        COUNT(*) AS total_transactions,
        SUM(amount) AS total_amount,
        
        -- Average metrics
        COUNT(*) / COUNT(DISTINCT user_key) AS avg_transactions_per_user,
        AVG(amount) AS avg_amount_per_transaction,
        
        -- Transaction type breakdown
        SUM(CASE WHEN transaction_type = 'Entry' THEN 1 ELSE 0 END) AS entry_transactions,
        SUM(CASE WHEN transaction_type = 'Exit' THEN 1 ELSE 0 END) AS exit_transactions,
        
        -- Time attributes
        MAX(is_weekend) AS is_weekend
        
    FROM transactions
    GROUP BY transaction_date
)

SELECT * FROM daily_metrics
ORDER BY date DESC

