{{
    config(
        materialized='table',
        schema='dimensions'
    )
}}
-- Time dimension table
-- Generates date attributes for date range

WITH date_spine AS (
    -- Generate date range from 2024-01-01 to 2025-12-31
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('2024-01-01' as date)",
        end_date="cast('2025-12-31' as date)"
    ) }}
),

dimension AS (
    SELECT
        -- Surrogate key (YYYYMMDD format)
        CAST(DATE_FORMAT(date_day, 'yyyyMMdd') AS INT) AS date_key,
        
        -- Date value
        date_day,
        
        -- Day attributes
        DAYOFWEEK(date_day) AS day_of_week,  -- 1=Sunday, 7=Saturday in Spark
        CASE DAYOFWEEK(date_day)
            WHEN 1 THEN 'Sunday'
            WHEN 2 THEN 'Monday'
            WHEN 3 THEN 'Tuesday'
            WHEN 4 THEN 'Wednesday'
            WHEN 5 THEN 'Thursday'
            WHEN 6 THEN 'Friday'
            WHEN 7 THEN 'Saturday'
        END AS day_of_week_name,
        DAYOFMONTH(date_day) AS day_of_month,
        DAYOFYEAR(date_day) AS day_of_year,
        
        -- Week attributes
        WEEKOFYEAR(date_day) AS week_of_year,
        
        -- Month attributes
        MONTH(date_day) AS month_number,
        CASE MONTH(date_day)
            WHEN 1 THEN 'January'
            WHEN 2 THEN 'February'
            WHEN 3 THEN 'March'
            WHEN 4 THEN 'April'
            WHEN 5 THEN 'May'
            WHEN 6 THEN 'June'
            WHEN 7 THEN 'July'
            WHEN 8 THEN 'August'
            WHEN 9 THEN 'September'
            WHEN 10 THEN 'October'
            WHEN 11 THEN 'November'
            WHEN 12 THEN 'December'
        END AS month_name,
        
        -- Quarter attributes
        QUARTER(date_day) AS quarter,
        
        -- Year attributes
        YEAR(date_day) AS year,
        
        -- Weekend flag (Saturday=7, Sunday=1 in Spark DAYOFWEEK)
        CASE 
            WHEN DAYOFWEEK(date_day) IN (1, 7) THEN TRUE
            ELSE FALSE
        END AS is_weekend,
        
        -- Holiday flag (placeholder - can be enhanced with actual holiday data)
        FALSE AS is_holiday
        
    FROM date_spine
)

SELECT * FROM dimension

