# Databricks notebook source
# MAGIC %md
# MAGIC # Silver Streaming Pipeline - Bronze to Silver with SCD2
# MAGIC 
# MAGIC 从 Bronze 层 Delta 表读取 CDC 事件，动态分表并应用 SCD2 逻辑，写入 Silver 层
# MAGIC 
# MAGIC **运行环境：** Databricks Cluster (不能在本地运行)
# MAGIC 
# MAGIC **表命名：** `silver_*_streaming` (与 DLT 版本区分)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 配置参数

# COMMAND ----------

# 配置 - 根据你的环境修改
CATALOG = "workspace"  # 修改为你的 catalog
SCHEMA = "default"   # 修改为你的 schema

# Bronze 表
BRONZE_TABLE = f"{CATALOG}.{SCHEMA}.bronze_cdc_events"

# Silver 表 (with _streaming suffix)
SILVER_TABLES = {
    "users": f"{CATALOG}.{SCHEMA}.silver_users_streaming",
    "routes": f"{CATALOG}.{SCHEMA}.silver_routes_streaming",
    "stations": f"{CATALOG}.{SCHEMA}.silver_stations_streaming",
    "topups": f"{CATALOG}.{SCHEMA}.silver_topups_streaming",
    "transactions": f"{CATALOG}.{SCHEMA}.silver_transactions_streaming"
}

# Checkpoint 位置 (DBFS)
CHECKPOINT_BASE = "/tmp/checkpoints/silver_streaming"

print("=" * 60)
print("Configuration:")
print(f"  Bronze Table: {BRONZE_TABLE}")
print(f"  Sample Silver Table: {SILVER_TABLES['users']}")
print(f"  Checkpoint: {CHECKPOINT_BASE}")
print("=" * 60)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 创建 Silver 表

# COMMAND ----------

from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.sql.window import Window

# 创建 Users 表
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {SILVER_TABLES['users']} (
        user_id BIGINT,
        card_number STRING,
        card_type STRING,
        is_verified BOOLEAN,
        created_at TIMESTAMP,
        updated_at TIMESTAMP,
        _debezium_op STRING,
        _debezium_ts_ms BIGINT,
        _event_id STRING,
        _processed_at TIMESTAMP,
        valid_from TIMESTAMP,
        valid_to TIMESTAMP,
        is_current BOOLEAN,
        is_deleted BOOLEAN
    ) USING DELTA
    PARTITIONED BY (is_current)
    TBLPROPERTIES (
        'delta.autoOptimize.optimizeWrite' = 'true',
        'delta.autoOptimize.autoCompact' = 'true'
    )
""")

# 创建 Routes 表
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {SILVER_TABLES['routes']} (
        route_id BIGINT,
        route_name STRING,
        route_type STRING,
        route_number STRING,
        start_station_id BIGINT,
        end_station_id BIGINT,
        created_at TIMESTAMP,
        _debezium_op STRING,
        _debezium_ts_ms BIGINT,
        _event_id STRING,
        _processed_at TIMESTAMP,
        valid_from TIMESTAMP,
        valid_to TIMESTAMP,
        is_current BOOLEAN,
        is_deleted BOOLEAN
    ) USING DELTA
    PARTITIONED BY (is_current)
""")

# 创建 Stations 表
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {SILVER_TABLES['stations']} (
        station_id BIGINT,
        station_name STRING,
        station_type STRING,
        latitude DOUBLE,
        longitude DOUBLE,
        district STRING,
        address STRING,
        created_at TIMESTAMP,
        _debezium_op STRING,
        _debezium_ts_ms BIGINT,
        _event_id STRING,
        _processed_at TIMESTAMP,
        valid_from TIMESTAMP,
        valid_to TIMESTAMP,
        is_current BOOLEAN,
        is_deleted BOOLEAN
    ) USING DELTA
    PARTITIONED BY (is_current)
""")

# 创建 Topups 表
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {SILVER_TABLES['topups']} (
        topup_id BIGINT,
        user_id BIGINT,
        topup_date DATE,
        topup_time STRING,
        amount DECIMAL(10,2),
        payment_method STRING,
        topup_location STRING,
        created_at TIMESTAMP,
        _debezium_op STRING,
        _debezium_ts_ms BIGINT,
        _event_id STRING,
        _processed_at TIMESTAMP,
        valid_from TIMESTAMP,
        valid_to TIMESTAMP,
        is_current BOOLEAN,
        is_deleted BOOLEAN
    ) USING DELTA
    PARTITIONED BY (is_current)
""")

# 创建 Transactions 表
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {SILVER_TABLES['transactions']} (
        transaction_id BIGINT,
        user_id BIGINT,
        station_id BIGINT,
        route_id BIGINT,
        transaction_date DATE,
        transaction_time STRING,
        amount DECIMAL(10,2),
        transaction_type STRING,
        created_at TIMESTAMP,
        _debezium_op STRING,
        _debezium_ts_ms BIGINT,
        _event_id STRING,
        _processed_at TIMESTAMP,
        valid_from TIMESTAMP,
        valid_to TIMESTAMP,
        is_current BOOLEAN,
        is_deleted BOOLEAN
    ) USING DELTA
    PARTITIONED BY (is_current)
""")

print("✅ Silver tables created successfully")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 定义 SCD2 处理函数

# COMMAND ----------

def process_users_scd2(batch_df, batch_id):
    """Process users table with SCD2 logic"""
    if batch_df.isEmpty():
        return
    
    table_name = SILVER_TABLES['users']
    
    # Parse after/before JSON
    after_map = from_json(col("after"), MapType(StringType(), StringType()))
    before_map = from_json(col("before"), MapType(StringType(), StringType()))
    
    # Handle DELETE operations
    deleted_df = batch_df.filter(col("op") == "d").select(
        before_map["user_id"].cast("bigint").alias("user_id"),
        lit(None).cast("string").alias("card_number"),
        lit(None).cast("string").alias("card_type"),
        lit(None).cast("boolean").alias("is_verified"),
        lit(None).cast("timestamp").alias("created_at"),
        lit(None).cast("timestamp").alias("updated_at"),
        col("op").alias("_debezium_op"),
        col("ts_ms").alias("_debezium_ts_ms"),
        lit(None).cast("string").alias("_event_id"),
        lit(None).cast("timestamp").alias("_processed_at"),
        from_unixtime(col("ts_ms") / 1000).cast("timestamp").alias("valid_from"),
        lit(True).alias("is_deleted")
    ).filter(col("user_id").isNotNull())
    
    # Handle active operations (c, u, r)
    active_df = batch_df.filter(col("op").isin(["c", "u", "r"])).select(
        after_map["user_id"].cast("bigint").alias("user_id"),
        after_map["card_number"].alias("card_number"),
        after_map["card_type"].alias("card_type"),
        when(after_map["is_verified"].isNotNull(),
             when(after_map["is_verified"] == "true", True).otherwise(False))
        .otherwise(False).alias("is_verified"),
        to_timestamp(after_map["created_at"]).alias("created_at"),
        to_timestamp(after_map["updated_at"]).alias("updated_at"),
        col("op").alias("_debezium_op"),
        col("ts_ms").alias("_debezium_ts_ms"),
        col("_event_id"),
        col("_processed_at"),
        from_unixtime(col("ts_ms") / 1000).cast("timestamp").alias("valid_from"),
        lit(False).alias("is_deleted")
    ).filter(col("user_id").isNotNull())
    
    # Union active and deleted records
    new_records_df = active_df.unionByName(deleted_df)
    
    if new_records_df.isEmpty():
        return
    
    new_records_df.createOrReplaceTempView("source_users")
    
    # MERGE INTO for SCD2
    spark.sql(f"""
        MERGE INTO {table_name} AS target
        USING source_users AS source
        ON target.user_id = source.user_id AND target.is_current = true
        WHEN MATCHED THEN
            UPDATE SET
                target.valid_to = source.valid_from,
                target.is_current = false
    """)
    
    # Insert new current versions
    new_records_df.withColumn("valid_to", lit(None).cast("timestamp")) \
        .withColumn("is_current", lit(True)) \
        .write.format("delta").mode("append").saveAsTable(table_name)
    
    print(f"✅ Batch {batch_id}: Processed {new_records_df.count()} users records")


def process_routes_scd2(batch_df, batch_id):
    """Process routes table with SCD2 logic"""
    if batch_df.isEmpty():
        return
    
    table_name = SILVER_TABLES['routes']
    after_map = from_json(col("after"), MapType(StringType(), StringType()))
    before_map = from_json(col("before"), MapType(StringType(), StringType()))
    
    deleted_df = batch_df.filter(col("op") == "d").select(
        before_map["route_id"].cast("bigint").alias("route_id"),
        lit(None).cast("string").alias("route_name"),
        lit(None).cast("string").alias("route_type"),
        lit(None).cast("string").alias("route_number"),
        lit(None).cast("bigint").alias("start_station_id"),
        lit(None).cast("bigint").alias("end_station_id"),
        lit(None).cast("timestamp").alias("created_at"),
        col("op").alias("_debezium_op"),
        col("ts_ms").alias("_debezium_ts_ms"),
        lit(None).cast("string").alias("_event_id"),
        lit(None).cast("timestamp").alias("_processed_at"),
        from_unixtime(col("ts_ms") / 1000).cast("timestamp").alias("valid_from"),
        lit(True).alias("is_deleted")
    ).filter(col("route_id").isNotNull())
    
    active_df = batch_df.filter(col("op").isin(["c", "u", "r"])).select(
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
        from_unixtime(col("ts_ms") / 1000).cast("timestamp").alias("valid_from"),
        lit(False).alias("is_deleted")
    ).filter(col("route_id").isNotNull())
    
    new_records_df = active_df.unionByName(deleted_df)
    if new_records_df.isEmpty():
        return
    
    new_records_df.createOrReplaceTempView("source_routes")
    
    spark.sql(f"""
        MERGE INTO {table_name} AS target
        USING source_routes AS source
        ON target.route_id = source.route_id AND target.is_current = true
        WHEN MATCHED THEN
            UPDATE SET target.valid_to = source.valid_from, target.is_current = false
    """)
    
    new_records_df.withColumn("valid_to", lit(None).cast("timestamp")) \
        .withColumn("is_current", lit(True)) \
        .write.format("delta").mode("append").saveAsTable(table_name)
    
    print(f"✅ Batch {batch_id}: Processed {new_records_df.count()} routes records")


def process_table_generic(batch_df, batch_id, table_type, primary_key, columns_mapping):
    """Generic SCD2 processing for other tables"""
    if batch_df.isEmpty():
        return
    
    table_name = SILVER_TABLES[table_type]
    after_map = from_json(col("after"), MapType(StringType(), StringType()))
    before_map = from_json(col("before"), MapType(StringType(), StringType()))
    
    # Build select for active records
    select_exprs = [after_map[pk].cast(dtype).alias(pk) for pk, dtype in columns_mapping.items()]
    select_exprs.extend([
        col("op").alias("_debezium_op"),
        col("ts_ms").alias("_debezium_ts_ms"),
        col("_event_id"),
        col("_processed_at"),
        from_unixtime(col("ts_ms") / 1000).cast("timestamp").alias("valid_from"),
        lit(False).alias("is_deleted")
    ])
    
    active_df = batch_df.filter(col("op").isin(["c", "u", "r"])).select(*select_exprs) \
        .filter(col(primary_key).isNotNull())
    
    # Build select for deleted records
    delete_exprs = [before_map[primary_key].cast(columns_mapping[primary_key]).alias(primary_key)]
    for col_name in columns_mapping.keys():
        if col_name != primary_key:
            delete_exprs.append(lit(None).cast(columns_mapping[col_name]).alias(col_name))
    delete_exprs.extend([
        col("op").alias("_debezium_op"),
        col("ts_ms").alias("_debezium_ts_ms"),
        lit(None).cast("string").alias("_event_id"),
        lit(None).cast("timestamp").alias("_processed_at"),
        from_unixtime(col("ts_ms") / 1000).cast("timestamp").alias("valid_from"),
        lit(True).alias("is_deleted")
    ])
    
    deleted_df = batch_df.filter(col("op") == "d").select(*delete_exprs) \
        .filter(col(primary_key).isNotNull())
    
    new_records_df = active_df.unionByName(deleted_df)
    if new_records_df.isEmpty():
        return
    
    new_records_df.createOrReplaceTempView(f"source_{table_type}")
    
    spark.sql(f"""
        MERGE INTO {table_name} AS target
        USING source_{table_type} AS source
        ON target.{primary_key} = source.{primary_key} AND target.is_current = true
        WHEN MATCHED THEN
            UPDATE SET target.valid_to = source.valid_from, target.is_current = false
    """)
    
    new_records_df.withColumn("valid_to", lit(None).cast("timestamp")) \
        .withColumn("is_current", lit(True)) \
        .write.format("delta").mode("append").saveAsTable(table_name)
    
    print(f"✅ Batch {batch_id}: Processed {new_records_df.count()} {table_type} records")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 启动流式处理

# COMMAND ----------

# 从 Bronze 表读取流式数据
print(f"📖 Reading from Bronze table: {BRONZE_TABLE}")

bronze_stream = spark.readStream \
    .format("delta") \
    .table(BRONZE_TABLE)

# 配置表处理逻辑
tables_config = {
    "users": ("user_id", process_users_scd2),
    "routes": ("route_id", process_routes_scd2),
    "stations": ("station_id", lambda df, bid: process_table_generic(
        df, bid, "stations", "station_id",
        {
            "station_id": "bigint", "station_name": "string", "station_type": "string",
            "latitude": "double", "longitude": "double", "district": "string",
            "address": "string", "created_at": "timestamp"
        }
    )),
    "topups": ("topup_id", lambda df, bid: process_table_generic(
        df, bid, "topups", "topup_id",
        {
            "topup_id": "bigint", "user_id": "bigint", "topup_date": "date",
            "topup_time": "string", "amount": "decimal(10,2)", "payment_method": "string",
            "topup_location": "string", "created_at": "timestamp"
        }
    )),
    "transactions": ("transaction_id", lambda df, bid: process_table_generic(
        df, bid, "transactions", "transaction_id",
        {
            "transaction_id": "bigint", "user_id": "bigint", "station_id": "bigint",
            "route_id": "bigint", "transaction_date": "date", "transaction_time": "string",
            "amount": "decimal(10,2)", "transaction_type": "string", "created_at": "timestamp"
        }
    ))
}

# 为每个表启动流式查询
queries = []
for table_name, (pk, process_func) in tables_config.items():
    filtered_stream = bronze_stream.filter(col("source_table") == table_name)
    
    query = filtered_stream.writeStream \
        .foreachBatch(process_func) \
        .outputMode("append") \
        .option("checkpointLocation", f"{CHECKPOINT_BASE}/{table_name}") \
        .trigger(processingTime="30 seconds") \
        .start()
    
    queries.append(query)
    print(f"✅ Started streaming query for table: {table_name}")

print("\n" + "=" * 60)
print("🚀 All streaming queries started successfully!")
print("=" * 60)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 监控流式查询状态

# COMMAND ----------

# 查看所有活跃的流式查询
for s in spark.streams.active:
    print(f"Stream ID: {s.id}")
    print(f"  Name: {s.name}")
    print(f"  Status: {s.status}")
    print(f"  Recent Progress:")
    if s.lastProgress:
        print(f"    Input Rows: {s.lastProgress.get('numInputRows', 0)}")
        print(f"    Processed Rows: {s.lastProgress.get('processedRowsPerSecond', 0)}/s")
    print()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 验证 Silver 层数据

# COMMAND ----------

# 查看 Users 表的 SCD2 历史
display(spark.sql(f"""
    SELECT user_id, card_type, valid_from, valid_to, is_current, is_deleted
    FROM {SILVER_TABLES['users']}
    WHERE user_id = 1
    ORDER BY valid_from
"""))

# COMMAND ----------

# 查看当前有效的用户数据
display(spark.sql(f"""
    SELECT COUNT(*) as total_users,
           SUM(CASE WHEN is_current THEN 1 ELSE 0 END) as current_users,
           SUM(CASE WHEN is_deleted THEN 1 ELSE 0 END) as deleted_users
    FROM {SILVER_TABLES['users']}
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 停止流式查询 (需要时手动运行)

# COMMAND ----------

# # 取消注释以停止所有流式查询
# for s in spark.streams.active:
#     s.stop()
#     print(f"Stopped stream: {s.id}")

