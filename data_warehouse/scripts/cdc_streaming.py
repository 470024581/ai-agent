#!/usr/bin/env python3
"""
CDC Streaming Application - Enhanced Version
从 Kafka 读取 Debezium CDC 数据并写入 Databricks Delta Lake

架构: PostgreSQL (Docker) → Debezium → Kafka → Structured Streaming → Databricks

Enhanced features:
1. Automatic schema change handling (type changes, column renames)
2. Automatic new table discovery without restart
3. Snapshot + incremental CDC support
"""

import json
import os
import platform
import re
import tempfile
import threading
import time
from pathlib import Path

# Windows-specific: Set HADOOP_HOME and configure native library path BEFORE importing SparkSession
# PySpark requires Hadoop libraries even when only writing to Databricks
# This is because Spark uses Hadoop's file system abstractions internally
if platform.system() == "Windows":
    if "HADOOP_HOME" not in os.environ:
        # Use a fixed location in user's temp directory for persistence
        user_temp = Path(os.environ.get("TEMP", os.environ.get("TMP", tempfile.gettempdir())))
        hadoop_home = user_temp / "hadoop_spark"
        bin_dir = hadoop_home / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        
        os.environ["HADOOP_HOME"] = str(hadoop_home)
        os.environ["hadoop.home.dir"] = str(hadoop_home)
    
    # Ensure Java can find hadoop.dll by adding bin directory to java.library.path
    hadoop_home = os.environ.get("HADOOP_HOME")
    if hadoop_home:
        bin_dir = Path(hadoop_home) / "bin"
        if bin_dir.exists():
            # Add to PATH for winutils.exe
            current_path = os.environ.get("PATH", "")
            if str(bin_dir) not in current_path:
                os.environ["PATH"] = f"{bin_dir};{current_path}"
            
            # Set java.library.path for hadoop.dll
            java_lib_path = os.environ.get("java.library.path", "")
            if str(bin_dir) not in java_lib_path:
                os.environ["java.library.path"] = f"{bin_dir};{java_lib_path}" if java_lib_path else str(bin_dir)
            
            # Verify files exist
            winutils_path = bin_dir / "winutils.exe"
            hadoop_dll_path = bin_dir / "hadoop.dll"
            if winutils_path.exists() and hadoop_dll_path.exists():
                print(f"✓ Found Hadoop native libraries at: {bin_dir}")
                # Add DLL directory to Windows DLL search path (Python 3.8+)
                try:
                    os.add_dll_directory(str(bin_dir))
                except AttributeError:
                    # Python < 3.8, fallback to PATH
                    current_path = os.environ.get("PATH", "")
                    if str(bin_dir) not in current_path:
                        os.environ["PATH"] = f"{bin_dir};{current_path}"
                # Note: java.library.path will also be set via Spark configuration in create_spark_session()
            else:
                missing = []
                if not winutils_path.exists():
                    missing.append("winutils.exe")
                if not hadoop_dll_path.exists():
                    missing.append("hadoop.dll")
                print(f"⚠ Missing files: {', '.join(missing)} in {bin_dir}")

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, lit, current_timestamp, 
    when, expr, coalesce
)
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType, 
    MapType, TimestampType
)
from dotenv import load_dotenv
import pandas as pd

# Load environment variables
# Try data_warehouse/.env first, then project root .env
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
# Support both DATABRICKS_CATALOG and DATABRICKS_DATABASE (for backward compatibility)
DATABRICKS_CATALOG = os.getenv('DATABRICKS_CATALOG') or os.getenv('DATABRICKS_DATABASE') or 'hive_metastore'
DATABRICKS_SCHEMA = os.getenv('DATABRICKS_SCHEMA', 'public')
# Use local filesystem for checkpoints when running locally (not in Databricks)
# For Databricks runtime, use dbfs:/checkpoints/cdc
CHECKPOINT_BASE = os.getenv('CHECKPOINT_BASE')
if not CHECKPOINT_BASE:
    # Default to local filesystem checkpoint directory
    import tempfile
    checkpoint_dir = Path(tempfile.gettempdir()) / "spark_checkpoints" / "cdc"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_BASE = str(checkpoint_dir.absolute())

# Table discovery interval (in seconds)
TABLE_DISCOVERY_INTERVAL = int(os.getenv('TABLE_DISCOVERY_INTERVAL', '600'))  # Default: 10 minutes

# Force reset checkpoint to re-read snapshot data (set to 'true' to reset)
FORCE_RESET_CHECKPOINT = os.getenv('FORCE_RESET_CHECKPOINT', 'false').lower() == 'true'

# Schema changes topic
SCHEMA_CHANGES_TOPIC = "transport_dw.schema.changes"

# Global state for managing streaming queries
active_queries = {}
active_tables = set()
schema_changes = {}  # Store schema change information: {table_name: {column_name: new_name/new_type}}


def create_spark_session():
    """Create Spark session with Databricks configuration"""
    builder = SparkSession.builder \
        .appName("CDCStreaming") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
        .config("spark.jars.packages", 
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,"
                "io.delta:delta-spark_2.12:3.1.0") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    
    # Windows-specific: Configure to use local filesystem and enable native libraries
    if platform.system() == "Windows":
        builder.config("spark.hadoop.fs.defaultFS", "file:///")
        
        # Increase Python worker connection timeout to handle Windows socket connection issues
        # Default is 120 seconds, increase to 300 seconds (5 minutes)
        builder.config("spark.python.worker.timeout", "300")
        
        # Configure Java to find hadoop.dll in HADOOP_HOME/bin
        hadoop_home = os.environ.get("HADOOP_HOME")
        if hadoop_home:
            bin_dir = Path(hadoop_home) / "bin"
            if bin_dir.exists():
                # Add bin directory to java.library.path for hadoop.dll
                # Use absolute path and ensure proper formatting for Windows
                bin_path = str(bin_dir.absolute())
                # Get existing java.library.path if any
                existing_lib_path = os.environ.get("java.library.path", "")
                if bin_path not in existing_lib_path:
                    # Combine paths with semicolon (Windows path separator)
                    if existing_lib_path:
                        new_lib_path = f"{bin_path};{existing_lib_path}"
                    else:
                        new_lib_path = bin_path
                    # Set via Spark configuration (this will be passed to JVM)
                    builder.config("spark.driver.extraJavaOptions", f"-Djava.library.path={new_lib_path}")
                    builder.config("spark.executor.extraJavaOptions", f"-Djava.library.path={new_lib_path}")
                    print(f"✓ Configured java.library.path to include: {bin_path}")
    
    # Databricks-specific configurations
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


def parse_schema_change_message(message):
    """Parse Debezium schema change message"""
    try:
        payload = json.loads(message)
        ddl_payload = payload.get('payload', {})
        
        ddl = ddl_payload.get('ddl', '')
        table_changes = ddl_payload.get('tableChanges', [])
        source = ddl_payload.get('source', {})
        
        table_name = source.get('table', '')
        schema_name = source.get('schema', '')
        
        return {
            'ddl': ddl,
            'table': table_name,
            'schema': schema_name,
            'table_changes': table_changes
        }
    except Exception as e:
        print(f"Error parsing schema change message: {e}")
        return None


def handle_schema_change(ddl_info, spark=None):
    """Handle schema changes: type changes and column renames"""
    if not ddl_info:
        return
    
    table_name = ddl_info['table']
    ddl = ddl_info['ddl'].upper()
    
    print(f"\n{'='*60}")
    print(f"Schema Change Detected: {table_name}")
    print(f"DDL: {ddl_info['ddl']}")
    print(f"{'='*60}")
    
    # Initialize schema changes tracking for this table
    if table_name not in schema_changes:
        schema_changes[table_name] = {}
    
    # Parse ALTER COLUMN TYPE
    # Pattern: ALTER COLUMN column_name TYPE new_type
    type_change_pattern = r'ALTER\s+COLUMN\s+(\w+)\s+TYPE\s+(\w+(?:\([^)]+\))?)'
    type_matches = re.findall(type_change_pattern, ddl)
    for old_col, new_type in type_matches:
        # Create new column name: old_col_new_type
        new_col_name = f"{old_col}_new_{new_type.lower().replace('(', '_').replace(')', '').replace(',', '_')}"
        schema_changes[table_name][old_col] = {
            'type': 'type_change',
            'new_column': new_col_name,
            'new_type': new_type
        }
        print(f"  ✓ Type change: {old_col} -> {new_col_name} ({new_type})")
        print(f"    Old column kept, new column will store converted data")
    
    # Parse RENAME COLUMN
    # Pattern: RENAME COLUMN old_name TO new_name
    rename_pattern = r'RENAME\s+COLUMN\s+(\w+)\s+TO\s+(\w+)'
    rename_matches = re.findall(rename_pattern, ddl)
    for old_col, new_col in rename_matches:
        schema_changes[table_name][old_col] = {
            'type': 'rename',
            'new_column': new_col
        }
        print(f"  ✓ Column rename: {old_col} -> {new_col}")
        print(f"    Old column kept, new column added")
    
    # Parse ADD COLUMN (already handled by mergeSchema, but log it)
    if 'ADD COLUMN' in ddl:
        add_pattern = r'ADD\s+COLUMN\s+(\w+)'
        add_matches = re.findall(add_pattern, ddl)
        for new_col in add_matches:
            print(f"  ✓ New column added: {new_col} (handled by mergeSchema)")
    
    # Parse DROP COLUMN (keep old column, mark as deprecated)
    if 'DROP COLUMN' in ddl:
        drop_pattern = r'DROP\s+COLUMN\s+(\w+)'
        drop_matches = re.findall(drop_pattern, ddl)
        for dropped_col in drop_matches:
            schema_changes[table_name][dropped_col] = {
                'type': 'drop',
                'deprecated': True
            }
            print(f"  ✓ Column dropped: {dropped_col} (kept in Databricks for history)")


def apply_schema_changes_to_dataframe(df, table_name):
    """Apply schema changes (type changes, renames) to DataFrame"""
    if table_name not in schema_changes:
        return df
    
    changes = schema_changes[table_name]
    result_df = df
    
    for old_col, change_info in changes.items():
        change_type = change_info.get('type')
        new_col = change_info.get('new_column')
        
        if change_type == 'type_change':
            # For type change: add new column with converted data from old column
            # The old column data will be in the data map, try to cast it
            new_type = change_info.get('new_type', 'STRING')
            # Extract from data map and cast
            result_df = result_df.withColumn(
                new_col,
                col("data")[new_col].cast(new_type) if new_col else 
                coalesce(col("data")[old_col].cast(new_type), lit(None))
            )
        
        elif change_type == 'rename':
            # For rename: add new column with data from old column
            # Check if new column name exists in data map first
            result_df = result_df.withColumn(
                new_col,
                coalesce(col("data")[new_col], col("data")[old_col])
            )
        
        # For drop: old column is kept in data map, no action needed
    
    return result_df


def process_debezium_messages(df, table_name):
    """Process Debezium messages and extract data"""
    # Extract data based on operation type
    data_col = when(col("op") == "d", col("before")).otherwise(col("after"))
    
    # Extract metadata
    result_df = df.select(
        data_col.alias("data"),
        col("op").alias("_debezium_op"),
        col("ts_ms").alias("_debezium_ts_ms"),
        col("source.table").alias("_source_table"),
        col("source.schema").alias("_source_schema"),
        col("source.db").alias("_source_db")
    )
    
    # Add processing metadata
    result_df = result_df.withColumn("_kafka_timestamp", current_timestamp()) \
        .withColumn("_processed_at", current_timestamp()) \
        .withColumn("_is_deleted", col("_debezium_op") == "d")
    
    # Apply schema changes (type changes, renames)
    result_df = apply_schema_changes_to_dataframe(result_df, table_name)
    
    return result_df


def write_to_databricks(df, epoch_id, table_name):
    """Write batch to Databricks Delta Lake"""
    # Note: We skip empty check to avoid Python worker connection issues on Windows
    # Delta Lake can safely handle empty batches, so this is safe
    
    try:
        full_table_name = f"{DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.{table_name}"
        
        # Flatten the data map into columns
        # Note: Avoid first() to prevent Python worker issues on Windows
        # Use a simpler approach: try to get keys, but fallback if it fails
        select_exprs = None
        data_keys_list = None
        
        try:
            # Try to get keys from first row (may trigger Python worker, but wrapped in try-except)
            data_keys = df.select(expr("map_keys(data)").alias("keys")).first()
            if data_keys and data_keys[0]:
                data_keys_list = data_keys[0]
                # Build select expression to extract all fields from map
                select_exprs = [col("data")[key].alias(key) for key in data_keys_list]
        except Exception as e:
            # If first() fails (Python worker issue), use fallback approach
            print(f"⚠ Could not extract data keys (Python worker issue), using fallback: {e}")
            data_keys_list = []
        
        if select_exprs:
            # We have specific keys, continue with the original logic
            
            # Add schema change columns if any (type changes, renames)
            base_table_name = table_name.replace('cdc_', '')
            if base_table_name in schema_changes:
                changes = schema_changes[base_table_name]
                for old_col, change_info in changes.items():
                    change_type = change_info.get('type')
                    new_col = change_info.get('new_column')
                    
                    if new_col and data_keys_list and new_col not in data_keys_list:
                        if change_type == 'type_change':
                            # Type change: cast old column to new type
                            new_type = change_info.get('new_type', 'STRING')
                            select_exprs.append(
                                coalesce(
                                    col("data")[new_col].cast(new_type),
                                    col("data")[old_col].cast(new_type)
                                ).alias(new_col)
                            )
                        elif change_type == 'rename':
                            # Rename: use new column name if exists, otherwise old column
                            select_exprs.append(
                                coalesce(
                                    col("data")[new_col],
                                    col("data")[old_col]
                                ).alias(new_col)
                            )
            
            select_exprs.extend([
                col("_debezium_op"),
                col("_debezium_ts_ms"),
                col("_source_table"),
                col("_source_schema"),
                col("_source_db"),
                col("_kafka_timestamp"),
                col("_processed_at"),
                col("_is_deleted")
            ])
            
            flattened_df = df.select(*select_exprs)
        else:
            flattened_df = df
        
        # Write to Databricks using Databricks SQL Connector
        # Local Spark cannot access Databricks catalog directly, so we use SQL Connector
        try:
            from databricks import sql as databricks_sql
            
            # Convert to Pandas DataFrame for batch insert
            # Note: This collects data to driver, but for streaming batches it should be manageable
            pandas_df = flattened_df.toPandas()
            
            if len(pandas_df) == 0:
                print(f"⚠ Batch {epoch_id} for {table_name} is empty, skipping...")
                return
            
            # Connect to Databricks
            connection = databricks_sql.connect(
                server_hostname=DATABRICKS_SERVER_HOSTNAME,
                http_path=DATABRICKS_HTTP_PATH,
                access_token=DATABRICKS_TOKEN
            )
            
            cursor = connection.cursor()
            
            # Set catalog and schema (required for Unity Catalog)
            # If catalog is not 'hive_metastore', use Unity Catalog
            if DATABRICKS_CATALOG and DATABRICKS_CATALOG.lower() != 'hive_metastore':
                try:
                    cursor.execute(f"USE CATALOG `{DATABRICKS_CATALOG}`")
                except Exception as e:
                    print(f"⚠ Could not set catalog {DATABRICKS_CATALOG}: {e}")
                    # Try to continue anyway
            
            # Set schema
            try:
                cursor.execute(f"USE SCHEMA `{DATABRICKS_SCHEMA}`")
            except Exception as e:
                print(f"⚠ Could not set schema {DATABRICKS_SCHEMA}: {e}")
                # Try to continue anyway
            
            # Create table if not exists (with schema evolution support)
            # Get column names and types from DataFrame
            df_columns = list(pandas_df.columns)
            df_dtypes = pandas_df.dtypes
            
            # Map pandas dtypes to SQL types
            type_mapping = {
                'int64': 'BIGINT',
                'int32': 'INT',
                'float64': 'DOUBLE',
                'float32': 'REAL',
                'bool': 'BOOLEAN',
                'datetime64[ns]': 'TIMESTAMP',
                'object': 'STRING'  # Default for strings and other types
            }
            
            # Check if table exists and get existing columns
            existing_columns = set()
            try:
                cursor.execute(f"DESCRIBE TABLE {full_table_name}")
                existing_columns = {row[0] for row in cursor.fetchall()}
            except Exception as e:
                # Table doesn't exist, will create it
                # Check if error is due to Hive Metastore being disabled
                error_msg = str(e)
                if 'UC_HIVE_METASTORE_DISABLED_EXCEPTION' in error_msg or 'HIVE_METASTORE_DISABLED' in error_msg:
                    print(f"\n✗ ERROR: Hive Metastore is disabled in your Databricks workspace.")
                    print(f"  Your workspace uses Unity Catalog. Please set DATABRICKS_CATALOG to a Unity Catalog catalog name.")
                    print(f"  Common Unity Catalog names: 'main', 'workspace', or your custom catalog name.")
                    print(f"  Current catalog: {DATABRICKS_CATALOG}")
                    print(f"  Please update your .env file:")
                    print(f"    DATABRICKS_CATALOG=main  # or your Unity Catalog catalog name")
                    raise
                pass
            
            # Build CREATE TABLE IF NOT EXISTS statement
            column_defs = []
            for col_name, dtype in zip(df_columns, df_dtypes):
                sql_type = type_mapping.get(str(dtype), 'STRING')
                column_defs.append(f"`{col_name}` {sql_type}")
            
            # Create table if not exists
            create_table_sql = f"""
                CREATE TABLE IF NOT EXISTS {full_table_name} (
                    {', '.join(column_defs)}
                ) USING DELTA
            """
            
            try:
                cursor.execute(create_table_sql)
            except Exception as e:
                error_msg = str(e)
                if 'UC_HIVE_METASTORE_DISABLED_EXCEPTION' in error_msg or 'HIVE_METASTORE_DISABLED' in error_msg:
                    print(f"\n✗ ERROR: Hive Metastore is disabled. Please use Unity Catalog.")
                    print(f"  Update your .env file: DATABRICKS_CATALOG=main  # or your Unity Catalog catalog name")
                    raise
                print(f"⚠ Table creation note: {e}")
            
            # Add missing columns (schema evolution)
            for col_name, dtype in zip(df_columns, df_dtypes):
                if col_name not in existing_columns:
                    sql_type = type_mapping.get(str(dtype), 'STRING')
                    try:
                        alter_sql = f"ALTER TABLE {full_table_name} ADD COLUMN `{col_name}` {sql_type}"
                        cursor.execute(alter_sql)
                        print(f"  ✓ Added new column: {col_name} ({sql_type})")
                    except Exception as e:
                        error_msg = str(e)
                        if 'UC_HIVE_METASTORE_DISABLED_EXCEPTION' in error_msg or 'HIVE_METASTORE_DISABLED' in error_msg:
                            # Skip column addition if Hive Metastore is disabled
                            # This will be handled by the INSERT statement error
                            pass
                        elif 'FIELD_ALREADY_EXISTS' in error_msg or 'already exists' in error_msg.lower():
                            # Column already exists, this is normal - silently skip
                            # This can happen if DESCRIBE TABLE didn't return all columns or table was created in parallel
                            pass
                        else:
                            # Other error - log it
                            print(f"  ⚠ Could not add column {col_name}: {e}")
            
            # Prepare INSERT statement
            columns_str = ", ".join([f"`{col}`" for col in df_columns])
            placeholders = ", ".join(["?" for _ in df_columns])
            
            insert_sql = f"""
                INSERT INTO {full_table_name} ({columns_str})
                VALUES ({placeholders})
            """
            
            # Convert DataFrame rows to tuples (handle None values)
            rows = []
            for _, row in pandas_df.iterrows():
                row_tuple = tuple(None if pd.isna(val) else val for val in row.values)
                rows.append(row_tuple)
            
            # Execute batch insert
            try:
                cursor.executemany(insert_sql, rows)
                connection.commit()
            except Exception as e:
                error_msg = str(e)
                if 'UC_HIVE_METASTORE_DISABLED_EXCEPTION' in error_msg or 'HIVE_METASTORE_DISABLED' in error_msg:
                    print(f"\n✗ ERROR: Hive Metastore is disabled in your Databricks workspace.")
                    print(f"  Your workspace uses Unity Catalog. Please set DATABRICKS_CATALOG to a Unity Catalog catalog name.")
                    print(f"  Common Unity Catalog names: 'main', 'workspace', or your custom catalog name.")
                    print(f"  Current catalog: {DATABRICKS_CATALOG}")
                    print(f"  Please update your .env file:")
                    print(f"    DATABRICKS_CATALOG=main  # or your Unity Catalog catalog name")
                    raise
                raise
            
            cursor.close()
            connection.close()
            
            print(f"✓ Wrote batch {epoch_id} to {table_name} ({len(pandas_df)} rows)")
            
        except ImportError:
            print(f"✗ databricks-sql-connector not available. Please install: pip install databricks-sql-connector")
            raise
        except Exception as e:
            print(f"✗ Error in Databricks SQL write: {e}")
            import traceback
            traceback.print_exc()
            raise
        
    except Exception as e:
        print(f"✗ Error writing batch {epoch_id} to {table_name}: {e}")
        import traceback
        traceback.print_exc()


def process_table_stream(spark, table_name, kafka_topic):
    """Process stream for a single table"""
    print(f"Starting stream for table: {table_name} (topic: {kafka_topic})")
    
    # Check if checkpoint exists
    checkpoint_location = f"{CHECKPOINT_BASE}/{table_name}"
    checkpoint_path = Path(checkpoint_location)
    checkpoint_exists = checkpoint_path.exists() and any(checkpoint_path.iterdir())
    
    # Force reset checkpoint if requested (to re-read snapshot data)
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
        "subscribe": kafka_topic,
        "failOnDataLoss": "false"
    }
    
    # Only use "earliest" if checkpoint doesn't exist (to read snapshot data)
    # If checkpoint exists, Spark will automatically resume from checkpoint offset
    if not checkpoint_exists:
        print(f"  No checkpoint found, starting from earliest offset (will read snapshot + CDC data)")
        kafka_options["startingOffsets"] = "earliest"
    else:
        print(f"  Checkpoint found, resuming from last offset (CDC data only)")
    
    # Read from Kafka
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
        col("timestamp").alias("kafka_timestamp")
    ).select("debezium.*", "kafka_timestamp")
    
    # Process messages
    processed_df = process_debezium_messages(parsed_df, table_name.replace('cdc_', ''))
    
    # Write to Databricks (checkpoint_location already defined above)
    query = processed_df.writeStream \
        .foreachBatch(lambda df, epoch_id: write_to_databricks(df, epoch_id, table_name)) \
        .outputMode("update") \
        .option("checkpointLocation", checkpoint_location) \
        .trigger(processingTime="10 seconds") \
        .start()
    
    return query


def discover_kafka_topics():
    """Dynamically discover Kafka topics matching the pattern"""
    try:
        from kafka import KafkaAdminClient
        
        admin_client = KafkaAdminClient(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            client_id='cdc_topic_discovery',
            request_timeout_ms=10000
        )
        
        # Get all topics - list_topics() returns a list of topic names
        all_topics = admin_client.list_topics()
        
        print(f"  Found {len(all_topics)} total topic(s) in Kafka")
        if all_topics:
            print(f"  Sample topics: {list(all_topics[:5])}")
        
        # Filter topics matching the pattern: transport_dw.public.*
        prefix = "transport_dw.public."
        matching_topics = [t for t in all_topics if t.startswith(prefix) and t != SCHEMA_CHANGES_TOPIC]
        
        print(f"  Found {len(matching_topics)} topic(s) matching pattern '{prefix}*'")
        
        # Extract table names and create mapping
        tables = {}
        for topic in matching_topics:
            table_name = topic.replace(prefix, "")
            tables[table_name] = topic
        
        if not tables and all_topics:
            print(f"  ⚠ No topics found matching pattern. Available topics: {list(all_topics)}")
        
        return tables
    except ImportError:
        print("⚠ kafka-python not available, using default table list")
        return {
            'users': 'transport_dw.public.users',
            'stations': 'transport_dw.public.stations',
            'routes': 'transport_dw.public.routes',
            'transactions': 'transport_dw.public.transactions',
            'topups': 'transport_dw.public.topups'
        }
    except Exception as e:
        print(f"⚠ Error discovering topics: {e}")
        print(f"  Trying to connect to Kafka at: {KAFKA_BOOTSTRAP_SERVERS}")
        print(f"  Make sure Kafka is running and Debezium connector is registered")
        print(f"  Using fallback table list...")
        return {
            'users': 'transport_dw.public.users',
            'stations': 'transport_dw.public.stations',
            'routes': 'transport_dw.public.routes',
            'transactions': 'transport_dw.public.transactions',
            'topups': 'transport_dw.public.topups'
        }


def monitor_schema_changes():
    """Monitor schema changes topic for DDL changes"""
    try:
        from kafka import KafkaConsumer
        
        consumer = KafkaConsumer(
            SCHEMA_CHANGES_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id='schema_change_monitor',
            auto_offset_reset='latest',
            value_deserializer=lambda m: m.decode('utf-8'),
            consumer_timeout_ms=1000  # Non-blocking check
        )
        
        print(f"✓ Started monitoring schema changes topic: {SCHEMA_CHANGES_TOPIC}")
        
        while True:
            try:
                # Poll for messages (non-blocking)
                messages = consumer.poll(timeout_ms=5000)
                for topic_partition, msgs in messages.items():
                    for message in msgs:
                        ddl_info = parse_schema_change_message(message.value)
                        if ddl_info:
                            handle_schema_change(ddl_info, None)  # Don't pass spark to avoid thread issues
            except Exception as e:
                print(f"⚠ Error processing schema change message: {e}")
            time.sleep(1)
    except Exception as e:
        print(f"⚠ Error monitoring schema changes: {e}")


def monitor_new_tables(spark, active_queries_dict, active_tables_set):
    """Periodically check for new tables and start streaming"""
    # TABLE_DISCOVERY_INTERVAL is in seconds (default: 600 = 10 minutes)
    # Convert to minutes for display
    interval_minutes = TABLE_DISCOVERY_INTERVAL // 60
    print(f"✓ Started new table discovery monitor (checks every {interval_minutes} minutes)")
    
    while True:
        try:
            # Sleep for TABLE_DISCOVERY_INTERVAL seconds (default: 600 seconds = 10 minutes)
            time.sleep(TABLE_DISCOVERY_INTERVAL)
            
            # Discover current topics
            current_tables = discover_kafka_topics()
            
            # Find new tables
            new_tables = {}
            for table_name, topic in current_tables.items():
                if table_name not in active_tables_set:
                    new_tables[table_name] = topic
            
            # Start streaming for new tables
            if new_tables:
                print(f"\n🔍 Discovered {len(new_tables)} new table(s): {list(new_tables.keys())}")
                for table_name, kafka_topic in new_tables.items():
                    try:
                        databricks_table = f"cdc_{table_name}"
                        query = process_table_stream(spark, databricks_table, kafka_topic)
                        active_queries_dict[table_name] = query
                        active_tables_set.add(table_name)
                        print(f"✓ Auto-discovered and started streaming for new table: {table_name}")
                    except Exception as e:
                        print(f"✗ Error starting stream for new table {table_name}: {e}")
        
        except Exception as e:
            print(f"⚠ Error in table discovery monitor: {e}")
            time.sleep(60)  # Wait longer on error


def main():
    """Main function"""
    print("=" * 60)
    print("CDC Streaming Application (Enhanced)")
    print("=" * 60)
    print(f"Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
    print(f"Databricks: {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}")
    print("=" * 60)
    
    # Validate configuration
    if not DATABRICKS_SERVER_HOSTNAME or not DATABRICKS_TOKEN:
        print("Error: Databricks configuration missing!")
        print("Please set DATABRICKS_SERVER_HOSTNAME and DATABRICKS_TOKEN environment variables")
        return 1
    
    # Validate catalog configuration
    if DATABRICKS_CATALOG.lower() == 'hive_metastore':
        print("\n⚠ WARNING: Using 'hive_metastore' catalog.")
        print("  If your Databricks workspace has Unity Catalog enabled and Hive Metastore disabled,")
        print("  you need to use a Unity Catalog catalog name instead (e.g., 'main', 'workspace').")
        print("  If you encounter 'UC_HIVE_METASTORE_DISABLED_EXCEPTION' errors, update your .env file:")
        print("    DATABRICKS_CATALOG=main  # or your Unity Catalog catalog name")
        print()
    
    # Create Spark session
    spark = create_spark_session()
    print("✓ Spark session created")
    
    # Discover initial tables/topics
    print("\nDiscovering Kafka topics...")
    tables = discover_kafka_topics()
    if not tables:
        print("\n✗ No tables to process")
        print("\nPossible reasons:")
        print("  1. Kafka is not running - check: docker ps | findstr kafka")
        print("  2. Debezium connector is not registered - run: .\\register_connector.ps1")
        print("  3. No data has been captured yet - check Kafka topics")
        print("\nTo check Kafka topics manually:")
        print(f"  docker exec -it kafka kafka-topics --list --bootstrap-server localhost:9092")
        return 1
    
    print(f"\nFound {len(tables)} table(s) to process:")
    for table_name, topic in tables.items():
        print(f"  - {table_name} <- {topic}")
        active_tables.add(table_name)
    
    # Start streaming queries for initial tables
    for table_name, kafka_topic in tables.items():
        try:
            databricks_table = f"cdc_{table_name}"
            query = process_table_stream(spark, databricks_table, kafka_topic)
            active_queries[table_name] = query
            print(f"✓ Started streaming for {table_name}")
        except Exception as e:
            print(f"✗ Error starting stream for {table_name}: {e}")
    
    if not active_queries:
        print("✗ No streaming queries started")
        return 1
    
    # Start background threads
    # 1. Schema change monitor (runs in separate thread)
    schema_thread = threading.Thread(
        target=monitor_schema_changes,
        daemon=True
    )
    schema_thread.start()
    print("✓ Schema change monitor started")
    
    # 2. New table discovery monitor (runs in separate thread)
    # Note: Starting new streaming queries from thread is safe in Spark
    discovery_thread = threading.Thread(
        target=monitor_new_tables,
        args=(spark, active_queries, active_tables),
        daemon=True
    )
    discovery_thread.start()
    interval_minutes = TABLE_DISCOVERY_INTERVAL // 60
    print(f"✓ New table discovery monitor started (checks every {interval_minutes} minutes)")
    
    print(f"\n✓ Started {len(active_queries)} streaming query(ies)")
    print(f"✓ Auto-discovery enabled (checks every {interval_minutes} minutes)")
    print("✓ Schema change monitoring enabled")
    print("Press Ctrl+C to stop...\n")
    
    # Wait for termination with periodic status updates
    last_status_time = time.time()
    status_interval = 30  # Print status every 30 seconds
    
    try:
        while True:
            time.sleep(1)
            current_time = time.time()
            
            # Check if any query has stopped
            for table_name, query in list(active_queries.items()):
                if not query.isActive:
                    print(f"⚠ Query for {table_name} has stopped")
            
            # Print periodic status (every 30 seconds)
            if current_time - last_status_time >= status_interval:
                print(f"\n[Status Check] {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  Active streaming queries: {len([q for q in active_queries.values() if q.isActive])}/{len(active_queries)}")
                for table_name, query in active_queries.items():
                    status = "✓ Active" if query.isActive else "✗ Stopped"
                    # Try to get recent progress (may fail on Windows, so wrap in try-except)
                    try:
                        progress = query.lastProgress
                        if progress:
                            input_rows = progress.get('inputRowsPerSecond', 0)
                            processing_rate = progress.get('processedRowsPerSecond', 0)
                            print(f"  - {table_name}: {status} | Input: {input_rows:.1f} rows/s | Processed: {processing_rate:.1f} rows/s")
                        else:
                            print(f"  - {table_name}: {status} | Waiting for data...")
                    except Exception:
                        print(f"  - {table_name}: {status}")
                print()  # Empty line for readability
                last_status_time = current_time
    except KeyboardInterrupt:
        print("\n\nStopping streaming queries...")
        for table_name, query in list(active_queries.items()):
            try:
                if query.isActive:
                    query.stop()
            except Exception as e:
                print(f"⚠ Error stopping query for {table_name}: {e}")
        print("✓ All queries stopped")
    
    try:
        spark.stop()
    except Exception as e:
        print(f"⚠ Error stopping Spark session: {e}")
    
    return 0


if __name__ == "__main__":
    exit(main())
