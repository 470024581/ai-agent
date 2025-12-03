{% macro test_amount_range(model, column_name, min_value=0, max_value=1000) %}

-- Custom test macro: Check if amounts are within expected range
-- Usage: {{ test_amount_range(ref('fact_transactions'), 'amount', 0, 1000) }}

SELECT
    *
FROM {{ model }}
WHERE {{ column_name }} < {{ min_value }}
   OR {{ column_name }} > {{ max_value }}

{% endmacro %}

