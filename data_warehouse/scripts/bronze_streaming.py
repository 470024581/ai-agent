#!/usr/bin/env python3
"""
Bronze Layer Streaming Application
从 Kafka 单一 topic 读取所有 CDC 事件，以 Append-Only 方式写入 Databricks Bronze 表

架构: Kafka (transport_dw.cdc_events) → Structured Streaming → Databricks Bronze (bronze_cdc_events)

特性:
1. Append-Only 写入，保留完整 CDC 日志
2. 单一流任务处理所有表
3. 支持 snapshot + incremental CDC
4. 完整审计追踪能力
"""

import json
import os
import platform
import tempfile
import time
import uuid
from pathlib import Path

# Windows-specific: Set HADOOP_HOME and configure native library path BEFORE importing SparkSession
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
            
            java_lib_path = os.environ.get("java.library.path", "")
            if str(bin_dir) not in java_lib_path:
                os.environ["java.library.path"] = f"{bin_dir};{java_lib_path}" if java_lib_path else str(bin_dir)
            
            winutils_path = bin_dir / "winutils.exe"
            hadoop_dll_path = bin_dir / "hadoop.dll"
            if winutils_path.exists() and hadoop_dll_path.exists():
                print(f"✓ Found Hadoop native libraries at: {bin_dir}")
                try:
                    os.add_dll_directory(str(bin_dir))
                except AttributeError:
                    current_path = os.environ.get("PATH", "")
                    if str(bin_dir) not in current_path:
                        os.environ["PATH"] = f"{bin_dir};{current_path}"

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, current_timestamp, concat, lit
)
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType, 
    MapType, TimestampType
)
from dotenv import load_dotenv
import pandas as pd

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
if not env_path.exists():
    env_path = Path(__file__).parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"✓ Loaded environment variables from: {env_path}")

# Configuration from environment variables
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
DATABRICKS_SERVER_HOSTNAME = os.getenv('DATABRICKS_SERVER_HOSTNAME')
DATABRICKS_HTTP_PATH = os.getenv('DATABRICKS_HTTP_PATH')
DATABRICKS_TOKEN = os.getenv('DATABRICKS_TOKEN')
DATABRICKS_CATALOG = os.getenv('DATABRICKS_CATALOG') or os.getenv('DATABRICKS_DATABASE') or 'hive_metastore'
DATABRICKS_SCHEMA = os.getenv('DATABRICKS_SCHEMA', 'public')

# Checkpoint configuration
CHECKPOINT_BASE = os.getenv('CHECKPOINT_BASE')
if not CHECKPOINT_BASE:
    import tempfile
    checkpoint_dir = Path(tempfile.gettempdir()) / "spark_checkpoints" / "bronze_cdc"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_BASE = str(checkpoint_dir.absolute())

# Force reset checkpoint to re-read snapshot data
FORCE_RESET_CHECKPOINT = os.getenv('FORCE_RESET_CHECKPOINT', 'false').lower() == 'true'

# Unified CDC topic name
CDC_EVENTS_TOPIC = "transport_dw.cdc_events"


def create_spark_session():
    """Create Spark session with Databricks configuration"""
    builder = SparkSession.builder \
        .appName("BronzeCDCStreaming") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
        .config("spark.jars.packages", 
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3,"
                "io.delta:delta-spark_2.12:3.2.0") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    
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
    
    if DATABRICKS_SERVER_HOSTNAME:
        builder.config("spark.databricks.service.address", f"https://{DATABRICKS_SERVER_HOSTNAME}")
        builder.config("spark.databricks.service.token", DATABRICKS_TOKEN)
    
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    
    return spark


def parse_debezium_message_schema():
    """Define schema for Debezium message format"""
    return StructType([
        StructField("before", MapType(StringType(), StringType()), True),
        StructField("after", MapType(StringType(), StringType()), True),
        StructField("source", StructType([
            StructField("version", StringType(), True),
            StructField("connector", StringType(), True),
            StructField("name", StringType(), True),
            StructField("ts_ms", LongType(), True),
            StructField("snapshot", StringType(), True),
            StructField("db", StringType(), True),
            StructField("schema", StringType(), True),
            StructField("table", StringType(), True)
        ]), True),
        StructField("op", StringType(), True),
        StructField("ts_ms", LongType(), True)
    ])


def write_to_bronze_append_only(df, epoch_id):
    """Write batch to Bronze table in Append-Only mode"""
    try:
        from databricks import sql as databricks_sql
        
        full_table_name = f"{DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.bronze_cdc_events"
        
        # Convert to Pandas DataFrame
        pandas_df = df.toPandas()
        
        if len(pandas_df) == 0:
            print(f"⚠ Batch {epoch_id} is empty, skipping...")
            return
        
        # Connect to Databricks
        connection = databricks_sql.connect(
            server_hostname=DATABRICKS_SERVER_HOSTNAME,
            http_path=DATABRICKS_HTTP_PATH,
            access_token=DATABRICKS_TOKEN
        )
        cursor = connection.cursor()
        
        # Set catalog and schema
        if DATABRICKS_CATALOG and DATABRICKS_CATALOG.lower() != 'hive_metastore':
            try:
                cursor.execute(f"USE CATALOG `{DATABRICKS_CATALOG}`")
            except Exception as e:
                print(f"⚠ Could not set catalog {DATABRICKS_CATALOG}: {e}")
        
        try:
            cursor.execute(f"USE SCHEMA `{DATABRICKS_SCHEMA}`")
        except Exception as e:
            print(f"⚠ Could not set schema {DATABRICKS_SCHEMA}: {e}")
        
        # Create Bronze table if not exists
        create_bronze_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {full_table_name} (
                before STRING,
                after STRING,
                source_version STRING,
                source_connector STRING,
                source_name STRING,
                source_ts_ms BIGINT,
                source_snapshot STRING,
                source_db STRING,
                source_schema STRING,
                source_table STRING,
                op STRING,
                ts_ms BIGINT,
                kafka_partition INT,
                kafka_offset BIGINT,
                kafka_timestamp TIMESTAMP,
                _processed_at TIMESTAMP,
                _event_id STRING,
                _batch_id BIGINT
            ) USING DELTA
            PARTITIONED BY (source_table)
            TBLPROPERTIES (
                'delta.autoOptimize.optimizeWrite' = 'true',
                'delta.autoOptimize.autoCompact' = 'true'
            )
        """
        
        try:
            cursor.execute(create_bronze_table_sql)
            print(f"✓ Bronze table created or already exists: {full_table_name}")
        except Exception as e:
            error_msg = str(e)
            if 'UC_HIVE_METASTORE_DISABLED_EXCEPTION' in error_msg or 'HIVE_METASTORE_DISABLED' in error_msg:
                print(f"\n✗ ERROR: Hive Metastore is disabled. Please use Unity Catalog.")
                print(f"  Update your .env file: DATABRICKS_CATALOG=main")
                raise
            print(f"⚠ Table creation note: {e}")
        
        # Prepare data for INSERT
        insert_sql = f"""
            INSERT INTO {full_table_name} (
                before, after, source_version, source_connector, source_name,
                source_ts_ms, source_snapshot, source_db, source_schema, source_table,
                op, ts_ms, kafka_partition, kafka_offset, kafka_timestamp,
                _processed_at, _event_id, _batch_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        rows = []
        for idx, row in pandas_df.iterrows():
            # Generate unique event ID
            source_table = row.get('source', {}).get('table', 'unknown') if isinstance(row.get('source'), dict) else 'unknown'
            ts_ms = row.get('ts_ms', 0)
            kafka_offset = row.get('kafka_offset', idx)
            event_id = f"{source_table}_{ts_ms}_{kafka_offset}_{uuid.uuid4().hex[:8]}"
            
            # Serialize before/after as JSON strings
            before_json = json.dumps(row.get('before', {})) if row.get('before') else None
            after_json = json.dumps(row.get('after', {})) if row.get('after') else None
            
            # Extract source fields
            source = row.get('source', {}) if isinstance(row.get('source'), dict) else {}
            
            row_tuple = (
                before_json,
                after_json,
                source.get('version'),
                source.get('connector'),
                source.get('name'),
                source.get('ts_ms'),
                source.get('snapshot'),
                source.get('db'),
                source.get('schema'),
                source.get('table'),
                row.get('op'),
                row.get('ts_ms'),
                row.get('kafka_partition', 0),
                kafka_offset,
                pd.to_datetime(row.get('kafka_timestamp'), unit='ms') if row.get('kafka_timestamp') else None,
                pd.Timestamp.now(),
                event_id,
                epoch_id
            )
            rows.append(row_tuple)
        
        # Batch insert (Append-Only)
        cursor.executemany(insert_sql, rows)
        connection.commit()
        
        print(f"✓ Wrote batch {epoch_id} to bronze_cdc_events ({len(rows)} events)")
        
        cursor.close()
        connection.close()
        
    except ImportError:
        print(f"✗ databricks-sql-connector not available. Please install: pip install databricks-sql-connector")
        raise
    except Exception as e:
        print(f"✗ Error writing to bronze: {e}")
        import traceback
        traceback.print_exc()
        raise


def main():
    """Main function"""
    print("=" * 60)
    print("Bronze Layer CDC Streaming Application")
    print("=" * 60)
    print(f"Kafka Topic: {CDC_EVENTS_TOPIC}")
    print(f"Kafka Bootstrap: {KAFKA_BOOTSTRAP_SERVERS}")
    print(f"Databricks: {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}")
    print("=" * 60)
    
    # Validate configuration
    if not DATABRICKS_SERVER_HOSTNAME or not DATABRICKS_TOKEN:
        print("Error: Databricks configuration missing!")
        print("Please set DATABRICKS_SERVER_HOSTNAME and DATABRICKS_TOKEN environment variables")
        return 1
    
    # Create Spark session
    spark = create_spark_session()
    print("✓ Spark session created")
    
    # Check checkpoint
    checkpoint_location = f"{CHECKPOINT_BASE}/bronze_cdc_events"
    checkpoint_path = Path(checkpoint_location)
    checkpoint_exists = checkpoint_path.exists() and any(checkpoint_path.iterdir())
    
    # Force reset checkpoint if requested
    if FORCE_RESET_CHECKPOINT and checkpoint_exists:
        import shutil
        print(f"  ⚠ FORCE_RESET_CHECKPOINT=true: Removing checkpoint to re-read snapshot data...")
        try:
            shutil.rmtree(checkpoint_path)
            print(f"  ✓ Checkpoint removed, will start from earliest offset")
            checkpoint_exists = False
        except Exception as e:
            print(f"  ⚠ Could not remove checkpoint: {e}")
    
    # Build Kafka read options
    kafka_options = {
        "kafka.bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "subscribe": CDC_EVENTS_TOPIC,
        "failOnDataLoss": "false"
    }
    
    if not checkpoint_exists:
        print(f"  No checkpoint found, starting from earliest offset (will read snapshot + CDC data)")
        kafka_options["startingOffsets"] = "earliest"
    else:
        print(f"  Checkpoint found, resuming from last offset (CDC data only)")
    
    # Read from Kafka
    print(f"\nReading from Kafka topic: {CDC_EVENTS_TOPIC}")
    kafka_df = spark \
        .readStream \
        .format("kafka") \
        .options(**kafka_options) \
        .load()
    
    # Parse Debezium message
    debezium_schema = parse_debezium_message_schema()
    
    # Parse JSON value
    parsed_df = kafka_df.select(
        from_json(col("value").cast("string"), debezium_schema).alias("debezium"),
        col("partition").alias("kafka_partition"),
        col("offset").alias("kafka_offset"),
        col("timestamp").alias("kafka_timestamp")
    ).select(
        col("debezium.*"),
        col("kafka_partition"),
        col("kafka_offset"),
        col("kafka_timestamp")
    )
    
    # Add processing metadata
    processed_df = parsed_df \
        .withColumn("_processed_at", current_timestamp()) \
        .withColumn("_event_id",
            concat(
                col("source.table"), lit("_"),
                col("ts_ms"), lit("_"),
                col("kafka_offset")
            )
        )
    
    # Write to Bronze (Append-Only)
    print(f"\nStarting Bronze streaming query...")
    print(f"Checkpoint location: {checkpoint_location}")
    
    query = processed_df.writeStream \
        .foreachBatch(lambda df, epoch_id: write_to_bronze_append_only(df, epoch_id)) \
        .outputMode("append") \
        .option("checkpointLocation", checkpoint_location) \
        .trigger(processingTime="10 seconds") \
        .start()
    
    print(f"✓ Bronze streaming query started")
    print("Press Ctrl+C to stop...\n")
    
    # Wait for termination
    try:
        query.awaitTermination()
    except KeyboardInterrupt:
        print("\n\nStopping streaming query...")
        query.stop()
        print("✓ Query stopped")
    
    try:
        spark.stop()
    except Exception as e:
        print(f"⚠ Error stopping Spark session: {e}")
    
    return 0


if __name__ == "__main__":
    exit(main())

