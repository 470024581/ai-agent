-- Test: Ensure all top-up amounts are positive
-- This test will fail if any top-up has a zero or negative amount

SELECT
    topup_id,
    amount,
    payment_method
FROM {{ ref('fact_topups') }}
WHERE amount <= 0

