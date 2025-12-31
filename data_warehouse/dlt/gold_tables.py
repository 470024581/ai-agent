"""
Delta Live Tables: Gold Layer
基于Silver层构建业务聚合视图
"""

import dlt
from pyspark.sql.functions import (
    col, count, sum, avg, date_trunc, 
    when, countDistinct, max, min
)


# Gold layer: Daily Active Users
@dlt.table(
    name="gold_daily_active_users",
    comment="Daily active users summary by card type"
)
def gold_daily_active_users():
    users = dlt.read("silver_users")
    
    # Filter current records only, exclude deleted records
    current_users = users.filter(
        (col("is_current") == True) & 
        (col("is_deleted") == False)
    )
    
    return current_users \
        .groupBy(
            col("card_type"),
            date_trunc("day", col("created_at")).alias("date")
        ) \
        .agg(
            count("*").alias("active_users"),
            sum(when(col("is_verified") == True, 1).otherwise(0)).alias("verified_users")
        ) \
        .orderBy("date", "card_type")


# Gold layer: Station Flow Daily
@dlt.table(
    name="gold_station_flow_daily",
    comment="Daily station flow summary"
)
def gold_station_flow_daily():
    transactions = dlt.read("silver_transactions")
    stations = dlt.read("silver_stations")
    
    # Filter current records, exclude deleted records
    current_transactions = transactions.filter(
        (col("is_current") == True) & 
        (col("is_deleted") == False)
    )
    current_stations = stations.filter(
        (col("is_current") == True) & 
        (col("is_deleted") == False)
    )
    
    # Join and aggregate
    return current_transactions \
        .join(
            current_stations.select("station_id", "station_name", "station_type"),
            current_transactions.station_id == current_stations.station_id,
            "inner"
        ) \
        .groupBy(
            col("station_name"),
            col("station_type"),
            date_trunc("day", col("transaction_date")).alias("date")
        ) \
        .agg(
            count("*").alias("transaction_count"),
            sum(col("amount")).alias("total_amount"),
            avg(col("amount")).alias("avg_amount")
        ) \
        .orderBy("date", "station_name")


# Gold layer: Route Usage Summary
@dlt.table(
    name="gold_route_usage_summary",
    comment="Route usage summary by day"
)
def gold_route_usage_summary():
    transactions = dlt.read("silver_transactions")
    routes = dlt.read("silver_routes")
    
    current_transactions = transactions.filter(
        (col("is_current") == True) & 
        (col("is_deleted") == False)
    )
    current_routes = routes.filter(
        (col("is_current") == True) & 
        (col("is_deleted") == False)
    )
    
    return current_transactions \
        .join(
            current_routes.select("route_id", "route_name", "route_type", "route_number"),
            current_transactions.route_id == current_routes.route_id,
            "inner"
        ) \
        .groupBy(
            col("route_name"),
            col("route_type"),
            col("route_number"),
            date_trunc("day", col("transaction_date")).alias("date")
        ) \
        .agg(
            count("*").alias("usage_count"),
            countDistinct(col("user_id")).alias("unique_users"),
            sum(col("amount")).alias("total_revenue")
        ) \
        .orderBy("date", "route_name")


# Gold layer: User Card Type Summary
@dlt.table(
    name="gold_user_card_type_summary",
    comment="User summary by card type"
)
def gold_user_card_type_summary():
    users = dlt.read("silver_users")
    
    current_users = users.filter(
        (col("is_current") == True) & 
        (col("is_deleted") == False)
    )
    
    return current_users \
        .groupBy("card_type") \
        .agg(
            count("*").alias("total_users"),
            sum(when(col("is_verified") == True, 1).otherwise(0)).alias("verified_users"),
            min(col("created_at")).alias("first_user_created"),
            max(col("created_at")).alias("last_user_created")
        ) \
        .orderBy("card_type")


# Gold layer: Daily Topup Summary
@dlt.table(
    name="gold_daily_topup_summary",
    comment="Daily topup summary by payment method"
)
def gold_daily_topup_summary():
    topups = dlt.read("silver_topups")
    
    current_topups = topups.filter(
        (col("is_current") == True) & 
        (col("is_deleted") == False)
    )
    
    return current_topups \
        .groupBy(
            date_trunc("day", col("topup_date")).alias("date"),
            col("payment_method")
        ) \
        .agg(
            count("*").alias("topup_count"),
            sum(col("amount")).alias("total_amount"),
            avg(col("amount")).alias("avg_amount"),
            countDistinct(col("user_id")).alias("unique_users")
        ) \
        .orderBy("date", "payment_method")

