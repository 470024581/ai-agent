-- Test: Ensure all transaction dates are within valid range
-- This test will fail if any transaction date is before 2024-01-01 or in the future

SELECT
    transaction_id,
    transaction_date
FROM {{ ref('fact_transactions') }}
WHERE transaction_date < '2024-01-01'
   OR transaction_date > CURRENT_DATE()

