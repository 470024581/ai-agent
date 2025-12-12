{{
    config(
        materialized='table',
        schema='public'
    )
}}
-- User summary by card type
-- Aggregates user activity metrics by card type

WITH users AS (
    SELECT * FROM {{ ref('dim_user') }}
),

transactions AS (
    SELECT 
        f.user_key,
        f.amount
    FROM {{ ref('fact_transactions') }} f
),

topups AS (
    SELECT 
        f.user_key,
        f.amount
    FROM {{ ref('fact_topups') }} f
),

user_transactions AS (
    SELECT
        u.card_type,
        COUNT(DISTINCT u.user_key) AS total_users,
        SUM(CASE WHEN u.is_verified THEN 1 ELSE 0 END) AS verified_users,
        COUNT(t.user_key) AS total_transactions,
        COALESCE(SUM(t.amount), 0) AS total_transaction_amount
    FROM users u
    LEFT JOIN transactions t ON u.user_key = t.user_key
    GROUP BY u.card_type
),

user_topups AS (
    SELECT
        u.card_type,
        COUNT(tp.user_key) AS total_topups,
        COALESCE(SUM(tp.amount), 0) AS total_topup_amount
    FROM users u
    LEFT JOIN topups tp ON u.user_key = tp.user_key
    GROUP BY u.card_type
),

summary AS (
    SELECT
        ut.card_type,
        ut.total_users,
        ut.verified_users,
        ut.total_transactions,
        ut.total_transaction_amount,
        CAST(ut.total_transactions AS DOUBLE) / ut.total_users AS avg_transactions_per_user,
        utp.total_topups,
        utp.total_topup_amount,
        CAST(utp.total_topup_amount AS DOUBLE) / ut.total_users AS avg_topup_per_user
    FROM user_transactions ut
    JOIN user_topups utp ON ut.card_type = utp.card_type
)

SELECT * FROM summary
ORDER BY total_users DESC

