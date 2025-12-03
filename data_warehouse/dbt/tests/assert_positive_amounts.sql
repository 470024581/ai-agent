-- Test: Ensure all transaction amounts are non-negative
-- This test will fail if any transaction has a negative amount

SELECT
    transaction_id,
    amount,
    transaction_type
FROM {{ ref('fact_transactions') }}
WHERE amount < 0

