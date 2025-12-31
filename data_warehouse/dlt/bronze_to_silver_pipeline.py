"""
Delta Live Tables Pipeline: Bronze to Silver
从Bronze层读取CDC事件，动态分离表并实现SCD2逻辑
"""

import dlt
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, when, lead, window, 
    current_timestamp, to_timestamp, from_unixtime, lit
)
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType, MapType
)
from pyspark.sql.window import Window
import json

# Define Debezium schema for parsing JSON fields
debezium_source_schema = StructType([
    StructField("version", StringType(), True),
    StructField("connector", StringType(), True),
    StructField("name", StringType(), True),
    StructField("ts_ms", LongType(), True),
    StructField("snapshot", StringType(), True),
    StructField("db", StringType(), True),
    StructField("schema", StringType(), True),
    StructField("table", StringType(), True)
])


# Note: Bronze table is created and populated by bronze_streaming.py
# DLT reads from the existing Bronze table, so we don't need to define it here
# The Bronze table is: {catalog}.{schema}.bronze_cdc_events


def extract_business_fields(df, table_name, field_mapping):
    """
    Extract business fields from after map based on table schema
    field_mapping: dict of {field_name: (data_type, default_value)}
    """
    result_df = df
    
    for field_name, (data_type, default_val) in field_mapping.items():
        # Extract from after JSON string
        if data_type == "bigint":
            result_df = result_df.withColumn(
                field_name,
                when(col("after").isNotNull(), 
                     from_json(col("after"), MapType(StringType(), StringType()))[field_name].cast("bigint"))
                .otherwise(default_val)
            )
        elif data_type == "string":
            result_df = result_df.withColumn(
                field_name,
                when(col("after").isNotNull(),
                     from_json(col("after"), MapType(StringType(), StringType()))[field_name])
                .otherwise(default_val)
            )
        elif data_type == "boolean":
            result_df = result_df.withColumn(
                field_name,
                when(col("after").isNotNull(),
                     from_json(col("after"), MapType(StringType(), StringType()))[field_name].cast("boolean"))
                .otherwise(default_val)
            )
        elif data_type == "timestamp":
            result_df = result_df.withColumn(
                field_name,
                when(col("after").isNotNull(),
                     to_timestamp(from_json(col("after"), MapType(StringType(), StringType()))[field_name]))
                .otherwise(default_val)
            )
        elif data_type == "double":
            result_df = result_df.withColumn(
                field_name,
                when(col("after").isNotNull(),
                     from_json(col("after"), MapType(StringType(), StringType()))[field_name].cast("double"))
                .otherwise(default_val)
            )
    
    return result_df


def apply_scd2_logic(df, primary_key_col):
    """
    Apply SCD2 logic to create versioned records
    """
    window_spec = Window.partitionBy(primary_key_col).orderBy("ts_ms")
    
    return df \
        .withColumn("valid_from", from_unixtime(col("ts_ms") / 1000).cast("timestamp")) \
        .withColumn("valid_to",
            lead(from_unixtime(col("ts_ms") / 1000).cast("timestamp"))
            .over(window_spec)
        ) \
        .withColumn("is_current",
            when(col("valid_to").isNull(), True).otherwise(False)
        )


# Silver layer tables - Users
@dlt.table(
    name="silver_users",
    comment="SCD2 dimension table for users",
    partition_cols=["is_current"]
)
def silver_users():
    # Read from Bronze table (created by bronze_streaming.py)
    spark = SparkSession.getActiveSession()
    catalog = spark.conf.get("spark.databricks.catalog", "workspace")
    schema = spark.conf.get("spark.databricks.schema", "public")
    bronze_data = spark.read.table(f"{catalog}.{schema}.bronze_cdc_events")
    
    # Filter users table events (include DELETE operations)
    users_events = bronze_data.filter(col("source_table") == "users")
    
    # Parse JSON maps
    after_map = from_json(col("after"), MapType(StringType(), StringType()))
    before_map = from_json(col("before"), MapType(StringType(), StringType()))
    
    # Handle CREATE/UPDATE/READ operations (from after)
    crud_events = users_events.filter(col("op").isin(["c", "u", "r"]))
    crud_df = crud_events.select(
        # Business fields from after
        after_map["user_id"].cast("bigint").alias("user_id"),
        after_map["card_number"].alias("card_number"),
        after_map["card_type"].alias("card_type"),
        when(after_map["is_verified"].isNotNull(), 
             when(after_map["is_verified"] == "true", True).otherwise(False))
        .otherwise(False).alias("is_verified"),
        to_timestamp(after_map["created_at"]).alias("created_at"),
        to_timestamp(after_map["updated_at"]).alias("updated_at"),
        # Metadata
        col("op").alias("_debezium_op"),
        col("ts_ms").alias("_debezium_ts_ms"),
        col("_event_id"),
        col("_processed_at"),
        # Logical delete flag
        lit(False).alias("is_deleted")
    ).filter(col("user_id").isNotNull())
    
    # Handle DELETE operations (from before, mark as deleted)
    delete_events = users_events.filter(col("op") == "d")
    delete_df = delete_events.select(
        # Extract primary key from before
        before_map["user_id"].cast("bigint").alias("user_id"),
        # Keep last known values (will be null for DELETE, but we have PK)
        lit(None).cast("string").alias("card_number"),
        lit(None).cast("string").alias("card_type"),
        lit(False).alias("is_verified"),
        lit(None).cast("timestamp").alias("created_at"),
        lit(None).cast("timestamp").alias("updated_at"),
        # Metadata
        col("op").alias("_debezium_op"),
        col("ts_ms").alias("_debezium_ts_ms"),
        col("_event_id"),
        col("_processed_at"),
        # Logical delete flag
        lit(True).alias("is_deleted")
    ).filter(col("user_id").isNotNull())
    
    # Union all events
    users_df = crud_df.unionByName(delete_df, allowMissingColumns=True)
    
    # Apply SCD2 logic
    window_spec = Window.partitionBy("user_id").orderBy("_debezium_ts_ms")
    
    scd2_df = users_df \
        .withColumn("valid_from", from_unixtime(col("_debezium_ts_ms") / 1000).cast("timestamp")) \
        .withColumn("valid_to",
            lead(from_unixtime(col("_debezium_ts_ms") / 1000).cast("timestamp"))
            .over(window_spec)
        ) \
        .withColumn("is_current",
            when(col("valid_to").isNull(), True).otherwise(False)
        )
    
    return scd2_df


# Silver layer tables - Stations
@dlt.table(
    name="silver_stations",
    comment="SCD2 dimension table for stations",
    partition_cols=["is_current"]
)
def silver_stations():
    spark = SparkSession.getActiveSession()
    catalog = spark.conf.get("spark.databricks.catalog", "workspace")
    schema = spark.conf.get("spark.databricks.schema", "public")
    bronze_data = spark.read.table(f"{catalog}.{schema}.bronze_cdc_events")
    
    stations_events = bronze_data.filter(col("source_table") == "stations")
    
    after_map = from_json(col("after"), MapType(StringType(), StringType()))
    before_map = from_json(col("before"), MapType(StringType(), StringType()))
    
    # CREATE/UPDATE/READ operations
    crud_events = stations_events.filter(col("op").isin(["c", "u", "r"]))
    crud_df = crud_events.select(
        after_map["station_id"].cast("bigint").alias("station_id"),
        after_map["station_name"].alias("station_name"),
        after_map["station_type"].alias("station_type"),
        after_map["latitude"].cast("double").alias("latitude"),
        after_map["longitude"].cast("double").alias("longitude"),
        after_map["district"].alias("district"),
        after_map["address"].alias("address"),
        to_timestamp(after_map["created_at"]).alias("created_at"),
        col("op").alias("_debezium_op"),
        col("ts_ms").alias("_debezium_ts_ms"),
        col("_event_id"),
        col("_processed_at"),
        lit(False).alias("is_deleted")
    ).filter(col("station_id").isNotNull())
    
    # DELETE operations
    delete_events = stations_events.filter(col("op") == "d")
    delete_df = delete_events.select(
        before_map["station_id"].cast("bigint").alias("station_id"),
        lit(None).cast("string").alias("station_name"),
        lit(None).cast("string").alias("station_type"),
        lit(None).cast("double").alias("latitude"),
        lit(None).cast("double").alias("longitude"),
        lit(None).cast("string").alias("district"),
        lit(None).cast("string").alias("address"),
        lit(None).cast("timestamp").alias("created_at"),
        col("op").alias("_debezium_op"),
        col("ts_ms").alias("_debezium_ts_ms"),
        col("_event_id"),
        col("_processed_at"),
        lit(True).alias("is_deleted")
    ).filter(col("station_id").isNotNull())
    
    stations_df = crud_df.unionByName(delete_df, allowMissingColumns=True)
    
    window_spec = Window.partitionBy("station_id").orderBy("_debezium_ts_ms")
    
    scd2_df = stations_df \
        .withColumn("valid_from", from_unixtime(col("_debezium_ts_ms") / 1000).cast("timestamp")) \
        .withColumn("valid_to",
            lead(from_unixtime(col("_debezium_ts_ms") / 1000).cast("timestamp"))
            .over(window_spec)
        ) \
        .withColumn("is_current",
            when(col("valid_to").isNull(), True).otherwise(False)
        )
    
    return scd2_df


# Silver layer tables - Routes
@dlt.table(
    name="silver_routes",
    comment="SCD2 dimension table for routes",
    partition_cols=["is_current"]
)
def silver_routes():
    spark = SparkSession.getActiveSession()
    catalog = spark.conf.get("spark.databricks.catalog", "workspace")
    schema = spark.conf.get("spark.databricks.schema", "public")
    bronze_data = spark.read.table(f"{catalog}.{schema}.bronze_cdc_events")
    
    routes_events = bronze_data.filter(col("source_table") == "routes")
    
    after_map = from_json(col("after"), MapType(StringType(), StringType()))
    before_map = from_json(col("before"), MapType(StringType(), StringType()))
    
    # CREATE/UPDATE/READ operations
    crud_events = routes_events.filter(col("op").isin(["c", "u", "r"]))
    crud_df = crud_events.select(
        after_map["route_id"].cast("bigint").alias("route_id"),
        after_map["route_name"].alias("route_name"),
        after_map["route_type"].alias("route_type"),
        after_map["route_number"].alias("route_number"),
        after_map["start_station_id"].cast("bigint").alias("start_station_id"),
        after_map["end_station_id"].cast("bigint").alias("end_station_id"),
        to_timestamp(after_map["created_at"]).alias("created_at"),
        col("op").alias("_debezium_op"),
        col("ts_ms").alias("_debezium_ts_ms"),
        col("_event_id"),
        col("_processed_at"),
        lit(False).alias("is_deleted")
    ).filter(col("route_id").isNotNull())
    
    # DELETE operations
    delete_events = routes_events.filter(col("op") == "d")
    delete_df = delete_events.select(
        before_map["route_id"].cast("bigint").alias("route_id"),
        lit(None).cast("string").alias("route_name"),
        lit(None).cast("string").alias("route_type"),
        lit(None).cast("string").alias("route_number"),
        lit(None).cast("bigint").alias("start_station_id"),
        lit(None).cast("bigint").alias("end_station_id"),
        lit(None).cast("timestamp").alias("created_at"),
        col("op").alias("_debezium_op"),
        col("ts_ms").alias("_debezium_ts_ms"),
        col("_event_id"),
        col("_processed_at"),
        lit(True).alias("is_deleted")
    ).filter(col("route_id").isNotNull())
    
    routes_df = crud_df.unionByName(delete_df, allowMissingColumns=True)
    
    window_spec = Window.partitionBy("route_id").orderBy("_debezium_ts_ms")
    
    scd2_df = routes_df \
        .withColumn("valid_from", from_unixtime(col("_debezium_ts_ms") / 1000).cast("timestamp")) \
        .withColumn("valid_to",
            lead(from_unixtime(col("_debezium_ts_ms") / 1000).cast("timestamp"))
            .over(window_spec)
        ) \
        .withColumn("is_current",
            when(col("valid_to").isNull(), True).otherwise(False)
        )
    
    return scd2_df


# Silver layer tables - Transactions
@dlt.table(
    name="silver_transactions",
    comment="SCD2 fact table for transactions",
    partition_cols=["is_current"]
)
def silver_transactions():
    spark = SparkSession.getActiveSession()
    catalog = spark.conf.get("spark.databricks.catalog", "workspace")
    schema = spark.conf.get("spark.databricks.schema", "public")
    bronze_data = spark.read.table(f"{catalog}.{schema}.bronze_cdc_events")
    
    transactions_events = bronze_data.filter(col("source_table") == "transactions")
    
    after_map = from_json(col("after"), MapType(StringType(), StringType()))
    before_map = from_json(col("before"), MapType(StringType(), StringType()))
    
    # CREATE/UPDATE/READ operations
    crud_events = transactions_events.filter(col("op").isin(["c", "u", "r"]))
    crud_df = crud_events.select(
        after_map["transaction_id"].cast("bigint").alias("transaction_id"),
        after_map["user_id"].cast("bigint").alias("user_id"),
        after_map["station_id"].cast("bigint").alias("station_id"),
        after_map["route_id"].cast("bigint").alias("route_id"),
        to_timestamp(after_map["transaction_date"]).alias("transaction_date"),
        to_timestamp(after_map["transaction_time"]).alias("transaction_time"),
        after_map["amount"].cast("double").alias("amount"),
        after_map["transaction_type"].alias("transaction_type"),
        to_timestamp(after_map["created_at"]).alias("created_at"),
        col("op").alias("_debezium_op"),
        col("ts_ms").alias("_debezium_ts_ms"),
        col("_event_id"),
        col("_processed_at"),
        lit(False).alias("is_deleted")
    ).filter(col("transaction_id").isNotNull())
    
    # DELETE operations
    delete_events = transactions_events.filter(col("op") == "d")
    delete_df = delete_events.select(
        before_map["transaction_id"].cast("bigint").alias("transaction_id"),
        lit(None).cast("bigint").alias("user_id"),
        lit(None).cast("bigint").alias("station_id"),
        lit(None).cast("bigint").alias("route_id"),
        lit(None).cast("timestamp").alias("transaction_date"),
        lit(None).cast("timestamp").alias("transaction_time"),
        lit(None).cast("double").alias("amount"),
        lit(None).cast("string").alias("transaction_type"),
        lit(None).cast("timestamp").alias("created_at"),
        col("op").alias("_debezium_op"),
        col("ts_ms").alias("_debezium_ts_ms"),
        col("_event_id"),
        col("_processed_at"),
        lit(True).alias("is_deleted")
    ).filter(col("transaction_id").isNotNull())
    
    transactions_df = crud_df.unionByName(delete_df, allowMissingColumns=True)
    
    window_spec = Window.partitionBy("transaction_id").orderBy("_debezium_ts_ms")
    
    scd2_df = transactions_df \
        .withColumn("valid_from", from_unixtime(col("_debezium_ts_ms") / 1000).cast("timestamp")) \
        .withColumn("valid_to",
            lead(from_unixtime(col("_debezium_ts_ms") / 1000).cast("timestamp"))
            .over(window_spec)
        ) \
        .withColumn("is_current",
            when(col("valid_to").isNull(), True).otherwise(False)
        )
    
    return scd2_df


# Silver layer tables - Topups
@dlt.table(
    name="silver_topups",
    comment="SCD2 fact table for topups",
    partition_cols=["is_current"]
)
def silver_topups():
    spark = SparkSession.getActiveSession()
    catalog = spark.conf.get("spark.databricks.catalog", "workspace")
    schema = spark.conf.get("spark.databricks.schema", "public")
    bronze_data = spark.read.table(f"{catalog}.{schema}.bronze_cdc_events")
    
    topups_events = bronze_data.filter(col("source_table") == "topups")
    
    after_map = from_json(col("after"), MapType(StringType(), StringType()))
    before_map = from_json(col("before"), MapType(StringType(), StringType()))
    
    # CREATE/UPDATE/READ operations
    crud_events = topups_events.filter(col("op").isin(["c", "u", "r"]))
    crud_df = crud_events.select(
        after_map["topup_id"].cast("bigint").alias("topup_id"),
        after_map["user_id"].cast("bigint").alias("user_id"),
        to_timestamp(after_map["topup_date"]).alias("topup_date"),
        to_timestamp(after_map["topup_time"]).alias("topup_time"),
        after_map["amount"].cast("double").alias("amount"),
        after_map["payment_method"].alias("payment_method"),
        after_map["topup_location"].alias("topup_location"),
        to_timestamp(after_map["created_at"]).alias("created_at"),
        col("op").alias("_debezium_op"),
        col("ts_ms").alias("_debezium_ts_ms"),
        col("_event_id"),
        col("_processed_at"),
        lit(False).alias("is_deleted")
    ).filter(col("topup_id").isNotNull())
    
    # DELETE operations
    delete_events = topups_events.filter(col("op") == "d")
    delete_df = delete_events.select(
        before_map["topup_id"].cast("bigint").alias("topup_id"),
        lit(None).cast("bigint").alias("user_id"),
        lit(None).cast("timestamp").alias("topup_date"),
        lit(None).cast("timestamp").alias("topup_time"),
        lit(None).cast("double").alias("amount"),
        lit(None).cast("string").alias("payment_method"),
        lit(None).cast("string").alias("topup_location"),
        lit(None).cast("timestamp").alias("created_at"),
        col("op").alias("_debezium_op"),
        col("ts_ms").alias("_debezium_ts_ms"),
        col("_event_id"),
        col("_processed_at"),
        lit(True).alias("is_deleted")
    ).filter(col("topup_id").isNotNull())
    
    topups_df = crud_df.unionByName(delete_df, allowMissingColumns=True)
    
    window_spec = Window.partitionBy("topup_id").orderBy("_debezium_ts_ms")
    
    scd2_df = topups_df \
        .withColumn("valid_from", from_unixtime(col("_debezium_ts_ms") / 1000).cast("timestamp")) \
        .withColumn("valid_to",
            lead(from_unixtime(col("_debezium_ts_ms") / 1000).cast("timestamp"))
            .over(window_spec)
        ) \
        .withColumn("is_current",
            when(col("valid_to").isNull(), True).otherwise(False)
        )
    
    return scd2_df

