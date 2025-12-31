"""
Silver Streaming Pipeline - Bronze to Silver with SCD2
从 Bronze 层读取 CDC 事件，动态分表并应用 SCD2 逻辑，写入 Silver 层
表命名：silver_*_streaming (与 DLT 版本区分)
"""

import os
import sys
import platform
import tempfile
from datetime import datetime
from pathlib import Path

# Windows-specific: Set HADOOP_HOME BEFORE importing PySpark
if platform.system() == "Windows":
    if "HADOOP_HOME" not in os.environ:
        user_temp = Path(os.environ.get("TEMP", os.environ.get("TMP", tempfile.gettempdir())))
        hadoop_home = user_temp / "hadoop_spark"
        bin_dir = hadoop_home / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        os.environ["HADOOP_HOME"] = str(hadoop_home)
        os.environ["hadoop.home.dir"] = str(hadoop_home)
    
    hadoop_home = os.environ.get("HADOOP_HOME")
    if hadoop_home:
        bin_dir = Path(hadoop_home) / "bin"
        if bin_dir.exists():
            current_path = os.environ.get("PATH", "")
            if str(bin_dir) not in current_path:
                os.environ["PATH"] = f"{bin_dir};{current_path}"

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, lit, when, to_timestamp, from_unixtime,
    lead, row_number, coalesce
)
from pyspark.sql.types import MapType, StringType
from pyspark.sql.window import Window
from databricks.sql import connect as databricks_connect
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
if not env_path.exists():
    env_path = Path(__file__).parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"✓ Loaded environment variables from: {env_path}")

# ===== Configuration =====
DATABRICKS_SERVER_HOSTNAME = os.getenv("DATABRICKS_SERVER_HOSTNAME")
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")
DATABRICKS_ACCESS_TOKEN = os.getenv("DATABRICKS_ACCESS_TOKEN") or os.getenv("DATABRICKS_TOKEN")

# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
CDC_EVENTS_TOPIC = "transport_dw.cdc_events"

# Catalog configuration (support both DATABRICKS_CATALOG and DATABRICKS_DATABASE for backward compatibility)
CATALOG = os.getenv("DATABRICKS_CATALOG") or os.getenv("DATABRICKS_DATABASE") or "default"
SCHEMA = os.getenv("DATABRICKS_SCHEMA", "default")

# Silver tables (with _streaming suffix)
# Use three-level namespace for Databricks SQL Connector (supports Unity Catalog)
SILVER_TABLES = {
    "users": f"{CATALOG}.{SCHEMA}.silver_users_streaming" if CATALOG else f"{SCHEMA}.silver_users_streaming",
    "routes": f"{CATALOG}.{SCHEMA}.silver_routes_streaming" if CATALOG else f"{SCHEMA}.silver_routes_streaming",
    "stations": f"{CATALOG}.{SCHEMA}.silver_stations_streaming" if CATALOG else f"{SCHEMA}.silver_stations_streaming",
    "topups": f"{CATALOG}.{SCHEMA}.silver_topups_streaming" if CATALOG else f"{SCHEMA}.silver_topups_streaming",
    "transactions": f"{CATALOG}.{SCHEMA}.silver_transactions_streaming" if CATALOG else f"{SCHEMA}.silver_transactions_streaming"
}

# Checkpoint locations
CHECKPOINT_BASE = "./checkpoints/silver_streaming"


# ===== Helper Functions =====
def create_silver_tables():
    """Create Silver tables with SCD2 schema"""
    connection = databricks_connect(
        server_hostname=DATABRICKS_SERVER_HOSTNAME,
        http_path=DATABRICKS_HTTP_PATH,
        access_token=DATABRICKS_ACCESS_TOKEN
    )
    cursor = connection.cursor()
    
    # Users table
    cursor.execute(f"""
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
    
    # Routes table
    cursor.execute(f"""
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
    
    # Stations table
    cursor.execute(f"""
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
    
    # Topups table
    cursor.execute(f"""
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
    
    # Transactions table
    cursor.execute(f"""
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
    
    cursor.close()
    connection.close()
    print("✅ Silver tables created successfully")


def process_users_scd2(batch_df, batch_id):
    """Process users table with SCD2 logic"""
    if batch_df.isEmpty():
        return
    
    table_name = SILVER_TABLES['users']
    
    # Parse after/before JSON
    after_map = from_json(col("after"), MapType(StringType(), StringType()))
    before_map = from_json(col("before"), MapType(StringType(), StringType()))
    
    # Handle DELETE operations - create logical delete records
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
    
    # Write with MERGE INTO for SCD2
    merge_condition = "target.user_id = source.user_id AND target.is_current = true"
    
    new_records_df.createOrReplaceTempView("source_users")
    
    spark = SparkSession.getActiveSession()
    spark.sql(f"""
        MERGE INTO {table_name} AS target
        USING source_users AS source
        ON {merge_condition}
        WHEN MATCHED THEN
            UPDATE SET
                target.valid_to = source.valid_from,
                target.is_current = false
        WHEN NOT MATCHED THEN
            INSERT (
                user_id, card_number, card_type, is_verified, created_at, updated_at,
                _debezium_op, _debezium_ts_ms, _event_id, _processed_at,
                valid_from, valid_to, is_current, is_deleted
            ) VALUES (
                source.user_id, source.card_number, source.card_type, source.is_verified,
                source.created_at, source.updated_at, source._debezium_op, source._debezium_ts_ms,
                source._event_id, source._processed_at, source.valid_from, NULL, true, source.is_deleted
            )
    """)
    
    # Insert new current versions
    new_records_df.withColumn("valid_to", lit(None).cast("timestamp")) \
        .withColumn("is_current", lit(True)) \
        .write \
        .format("delta") \
        .mode("append") \
        .saveAsTable(table_name)
    
    print(f"✅ Batch {batch_id}: Processed {new_records_df.count()} users records")


def process_routes_scd2(batch_df, batch_id):
    """Process routes table with SCD2 logic"""
    if batch_df.isEmpty():
        return
    
    table_name = SILVER_TABLES['routes']
    after_map = from_json(col("after"), MapType(StringType(), StringType()))
    before_map = from_json(col("before"), MapType(StringType(), StringType()))
    
    # Handle DELETE
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
    
    # Handle active
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
    spark = SparkSession.getActiveSession()
    
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
    
    # Build select expressions for active records
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
    spark = SparkSession.getActiveSession()
    
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


def main():
    print("=" * 60)
    print("Silver Streaming Pipeline - Bronze to Silver with SCD2")
    print("=" * 60)
    print(f"Configuration:")
    print(f"  Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
    print(f"  Topic: {CDC_EVENTS_TOPIC}")
    print(f"  Catalog: {CATALOG}")
    print(f"  Schema: {SCHEMA}")
    print(f"  Sample Silver Table: {SILVER_TABLES['users']}")
    print("=" * 60)
    
    # Create Spark session with Delta Lake support
    builder = SparkSession.builder \
        .appName("Silver_Streaming_Pipeline") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
        .config("spark.jars.packages", "io.delta:delta-spark_2.12:3.1.0") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    
    # Windows-specific configurations
    if platform.system() == "Windows":
        builder.config("spark.hadoop.fs.defaultFS", "file:///")
        builder.config("spark.python.worker.timeout", "300")
        
        hadoop_home = os.environ.get("HADOOP_HOME")
        if hadoop_home:
            bin_dir = Path(hadoop_home) / "bin"
            if bin_dir.exists():
                bin_path = str(bin_dir.absolute())
                existing_lib_path = os.environ.get("java.library.path", "")
                if bin_path not in existing_lib_path:
                    if existing_lib_path:
                        new_lib_path = f"{bin_path};{existing_lib_path}"
                    else:
                        new_lib_path = bin_path
                    builder.config("spark.driver.extraJavaOptions", f"-Djava.library.path={new_lib_path}")
                    builder.config("spark.executor.extraJavaOptions", f"-Djava.library.path={new_lib_path}")
    
    spark = builder.getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    # Create Silver tables
    create_silver_tables()
    
    # Read from Kafka (same as bronze_streaming.py)
    print(f"📖 Reading from Kafka topic: {CDC_EVENTS_TOPIC}")
    
    kafka_df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", CDC_EVENTS_TOPIC) \
        .option("startingOffsets", "earliest") \
        .option("failOnDataLoss", "false") \
        .load()
    
    # Parse Kafka message (JSON format from Debezium)
    from pyspark.sql.types import StructType, StructField, LongType, IntegerType, TimestampType
    
    bronze_stream = kafka_df.selectExpr("CAST(value AS STRING) as json_value") \
        .select(
            from_json(col("json_value"), MapType(StringType(), StringType())).alias("data"),
            col("json_value")
        ) \
        .select(
            col("data.before").alias("before"),
            col("data.after").alias("after"),
            col("data.source.version").alias("source_version"),
            col("data.source.connector").alias("source_connector"),
            col("data.source.name").alias("source_name"),
            col("data.source.ts_ms").cast("bigint").alias("source_ts_ms"),
            col("data.source.snapshot").alias("source_snapshot"),
            col("data.source.db").alias("source_db"),
            col("data.source.schema").alias("source_schema"),
            col("data.source.table").alias("source_table"),
            col("data.op").alias("op"),
            col("data.ts_ms").cast("bigint").alias("ts_ms")
        )
    
    # Process each table type
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
    print("Press Ctrl+C to stop...")
    print("=" * 60 + "\n")
    
    # Wait for all queries
    for query in queries:
        query.awaitTermination()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  Streaming stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

