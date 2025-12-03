-- Test: Ensure all dimension surrogate keys match their business keys
-- This test will fail if there are duplicate business keys with different surrogate keys

WITH user_key_check AS (
    SELECT 
        user_id,
        COUNT(DISTINCT user_key) AS key_count
    FROM {{ ref('dim_user') }}
    GROUP BY user_id
    HAVING COUNT(DISTINCT user_key) > 1
)

SELECT * FROM user_key_check

