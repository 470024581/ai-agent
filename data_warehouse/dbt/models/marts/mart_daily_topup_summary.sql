{{
    config(
        materialized='table',
        schema='public'
    )
}}
-- Daily top-up summary metrics
-- Aggregates top-up data by date with payment method breakdown

WITH topups AS (
    SELECT 
        f.*,
        d.is_weekend
    FROM {{ ref('fact_topups') }} f
    JOIN {{ ref('dim_time') }} d ON f.date_key = d.date_key
),

daily_metrics AS (
    SELECT
        topup_date AS date,
        
        -- Top-up metrics
        COUNT(*) AS total_topups,
        COUNT(DISTINCT user_key) AS unique_users,
        SUM(amount) AS total_amount,
        
        -- Average metrics
        AVG(amount) AS avg_amount_per_topup,
        SUM(amount) / COUNT(DISTINCT user_key) AS avg_amount_per_user,
        
        -- Payment method breakdown
        SUM(CASE WHEN payment_method = 'Cash' THEN 1 ELSE 0 END) AS cash_topups,
        SUM(CASE WHEN payment_method = 'Card' THEN 1 ELSE 0 END) AS card_topups,
        SUM(CASE WHEN payment_method = 'Mobile' THEN 1 ELSE 0 END) AS mobile_topups,
        SUM(CASE WHEN payment_method = 'Online' THEN 1 ELSE 0 END) AS online_topups,
        
        -- Time attributes
        MAX(is_weekend) AS is_weekend
        
    FROM topups
    GROUP BY topup_date
)

SELECT * FROM daily_metrics
ORDER BY date DESC

