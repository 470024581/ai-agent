-- Test: Ensure daily active users metrics are consistent
-- This test will fail if active_users > total_transactions (impossible scenario)

SELECT
    date,
    active_users,
    total_transactions
FROM {{ ref('daily_active_users') }}
WHERE active_users > total_transactions

