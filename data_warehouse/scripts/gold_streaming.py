"""
Gold Streaming Pipeline - Silver to Gold Materialized Views
从 Silver 层读取数据，构建实时物化聚合视图，写入 Gold 层
表命名：gold_*_streaming (与 DLT 版本区分)
"""

import os
import sys
import platform
import tempfile
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
    col, count, sum as spark_sum, avg, max as spark_max, min as spark_min,
    date_trunc, when, current_timestamp, window, date_format
)
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

# Catalog configuration (support both DATABRICKS_CATALOG and DATABRICKS_DATABASE for backward compatibility)
CATALOG = os.getenv("DATABRICKS_CATALOG") or os.getenv("DATABRICKS_DATABASE") or "default"
SCHEMA = os.getenv("DATABRICKS_SCHEMA", "default")

# Silver tables
SILVER_TABLES = {
    "users": f"{CATALOG}.{SCHEMA}.silver_users_streaming",
    "routes": f"{CATALOG}.{SCHEMA}.silver_routes_streaming",
    "stations": f"{CATALOG}.{SCHEMA}.silver_stations_streaming",
    "topups": f"{CATALOG}.{SCHEMA}.silver_topups_streaming",
    "transactions": f"{CATALOG}.{SCHEMA}.silver_transactions_streaming"
}

# Gold tables (with _streaming suffix)
GOLD_TABLES = {
    "daily_active_users": f"{CATALOG}.{SCHEMA}.gold_daily_active_users_streaming",
    "station_activity": f"{CATALOG}.{SCHEMA}.gold_station_activity_streaming",
    "route_usage": f"{CATALOG}.{SCHEMA}.gold_route_usage_streaming",
    "topup_summary": f"{CATALOG}.{SCHEMA}.gold_topup_summary_streaming",
    "transaction_summary": f"{CATALOG}.{SCHEMA}.gold_transaction_summary_streaming"
}

CHECKPOINT_BASE = "./checkpoints/gold_streaming"


# ===== Helper Functions =====
def create_gold_tables():
    """Create Gold aggregation tables"""
    connection = databricks_connect(
        server_hostname=DATABRICKS_SERVER_HOSTNAME,
        http_path=DATABRICKS_HTTP_PATH,
        access_token=DATABRICKS_ACCESS_TOKEN
    )
    cursor = connection.cursor()
    
    # Daily active users
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {GOLD_TABLES['daily_active_users']} (
            date DATE,
            card_type STRING,
            active_users BIGINT,
            verified_users BIGINT,
            updated_at TIMESTAMP
        ) USING DELTA
        PARTITIONED BY (date)
    """)
    
    # Station activity
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {GOLD_TABLES['station_activity']} (
            station_id BIGINT,
            station_name STRING,
            district STRING,
            date DATE,
            total_transactions BIGINT,
            total_amount DECIMAL(18,2),
            unique_users BIGINT,
            updated_at TIMESTAMP
        ) USING DELTA
        PARTITIONED BY (date)
    """)
    
    # Route usage
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {GOLD_TABLES['route_usage']} (
            route_id BIGINT,
            route_name STRING,
            route_type STRING,
            date DATE,
            total_transactions BIGINT,
            total_amount DECIMAL(18,2),
            unique_users BIGINT,
            updated_at TIMESTAMP
        ) USING DELTA
        PARTITIONED BY (date)
    """)
    
    # Topup summary
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {GOLD_TABLES['topup_summary']} (
            date DATE,
            payment_method STRING,
            total_topups BIGINT,
            total_amount DECIMAL(18,2),
            avg_amount DECIMAL(18,2),
            unique_users BIGINT,
            updated_at TIMESTAMP
        ) USING DELTA
        PARTITIONED BY (date)
    """)
    
    # Transaction summary
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {GOLD_TABLES['transaction_summary']} (
            date DATE,
            transaction_type STRING,
            total_transactions BIGINT,
            total_amount DECIMAL(18,2),
            avg_amount DECIMAL(18,2),
            unique_users BIGINT,
            updated_at TIMESTAMP
        ) USING DELTA
        PARTITIONED BY (date)
    """)
    
    cursor.close()
    connection.close()
    print("✅ Gold tables created successfully")


def build_daily_active_users(spark):
    """Build daily active users materialized view"""
    users_df = spark.readStream \
        .format("delta") \
        .table(SILVER_TABLES['users']) \
        .filter((col("is_current") == True) & (col("is_deleted") == False))
    
    # Aggregate by date and card_type
    result_df = users_df \
        .withWatermark("valid_from", "1 hour") \
        .groupBy(
            window(col("valid_from"), "1 day").alias("time_window"),
            col("card_type")
        ) \
        .agg(
            count("*").alias("active_users"),
            spark_sum(when(col("is_verified") == True, 1).otherwise(0)).alias("verified_users")
        ) \
        .select(
            col("time_window.start").cast("date").alias("date"),
            col("card_type"),
            col("active_users"),
            col("verified_users"),
            current_timestamp().alias("updated_at")
        )
    
    query = result_df.writeStream \
        .format("delta") \
        .outputMode("complete") \
        .option("checkpointLocation", f"{CHECKPOINT_BASE}/daily_active_users") \
        .trigger(processingTime="1 minute") \
        .toTable(GOLD_TABLES['daily_active_users'])
    
    print(f"✅ Started: Daily Active Users")
    return query


def build_station_activity(spark):
    """Build station activity materialized view"""
    transactions_df = spark.readStream \
        .format("delta") \
        .table(SILVER_TABLES['transactions']) \
        .filter((col("is_current") == True) & (col("is_deleted") == False))
    
    stations_df = spark.read \
        .format("delta") \
        .table(SILVER_TABLES['stations']) \
        .filter((col("is_current") == True) & (col("is_deleted") == False)) \
        .select("station_id", "station_name", "district")
    
    # Join and aggregate
    result_df = transactions_df \
        .join(stations_df, "station_id", "inner") \
        .withWatermark("created_at", "1 hour") \
        .groupBy(
            window(col("created_at"), "1 day").alias("time_window"),
            col("station_id"),
            col("station_name"),
            col("district")
        ) \
        .agg(
            count("*").alias("total_transactions"),
            spark_sum("amount").alias("total_amount"),
            count("user_id").alias("unique_users")
        ) \
        .select(
            col("station_id"),
            col("station_name"),
            col("district"),
            col("time_window.start").cast("date").alias("date"),
            col("total_transactions"),
            col("total_amount"),
            col("unique_users"),
            current_timestamp().alias("updated_at")
        )
    
    query = result_df.writeStream \
        .format("delta") \
        .outputMode("complete") \
        .option("checkpointLocation", f"{CHECKPOINT_BASE}/station_activity") \
        .trigger(processingTime="1 minute") \
        .toTable(GOLD_TABLES['station_activity'])
    
    print(f"✅ Started: Station Activity")
    return query


def build_route_usage(spark):
    """Build route usage materialized view"""
    transactions_df = spark.readStream \
        .format("delta") \
        .table(SILVER_TABLES['transactions']) \
        .filter((col("is_current") == True) & (col("is_deleted") == False))
    
    routes_df = spark.read \
        .format("delta") \
        .table(SILVER_TABLES['routes']) \
        .filter((col("is_current") == True) & (col("is_deleted") == False)) \
        .select("route_id", "route_name", "route_type")
    
    result_df = transactions_df \
        .join(routes_df, "route_id", "inner") \
        .withWatermark("created_at", "1 hour") \
        .groupBy(
            window(col("created_at"), "1 day").alias("time_window"),
            col("route_id"),
            col("route_name"),
            col("route_type")
        ) \
        .agg(
            count("*").alias("total_transactions"),
            spark_sum("amount").alias("total_amount"),
            count("user_id").alias("unique_users")
        ) \
        .select(
            col("route_id"),
            col("route_name"),
            col("route_type"),
            col("time_window.start").cast("date").alias("date"),
            col("total_transactions"),
            col("total_amount"),
            col("unique_users"),
            current_timestamp().alias("updated_at")
        )
    
    query = result_df.writeStream \
        .format("delta") \
        .outputMode("complete") \
        .option("checkpointLocation", f"{CHECKPOINT_BASE}/route_usage") \
        .trigger(processingTime="1 minute") \
        .toTable(GOLD_TABLES['route_usage'])
    
    print(f"✅ Started: Route Usage")
    return query


def build_topup_summary(spark):
    """Build topup summary materialized view"""
    topups_df = spark.readStream \
        .format("delta") \
        .table(SILVER_TABLES['topups']) \
        .filter((col("is_current") == True) & (col("is_deleted") == False))
    
    result_df = topups_df \
        .withWatermark("created_at", "1 hour") \
        .groupBy(
            window(col("created_at"), "1 day").alias("time_window"),
            col("payment_method")
        ) \
        .agg(
            count("*").alias("total_topups"),
            spark_sum("amount").alias("total_amount"),
            avg("amount").alias("avg_amount"),
            count("user_id").alias("unique_users")
        ) \
        .select(
            col("time_window.start").cast("date").alias("date"),
            col("payment_method"),
            col("total_topups"),
            col("total_amount"),
            col("avg_amount"),
            col("unique_users"),
            current_timestamp().alias("updated_at")
        )
    
    query = result_df.writeStream \
        .format("delta") \
        .outputMode("complete") \
        .option("checkpointLocation", f"{CHECKPOINT_BASE}/topup_summary") \
        .trigger(processingTime="1 minute") \
        .toTable(GOLD_TABLES['topup_summary'])
    
    print(f"✅ Started: Topup Summary")
    return query


def build_transaction_summary(spark):
    """Build transaction summary materialized view"""
    transactions_df = spark.readStream \
        .format("delta") \
        .table(SILVER_TABLES['transactions']) \
        .filter((col("is_current") == True) & (col("is_deleted") == False))
    
    result_df = transactions_df \
        .withWatermark("created_at", "1 hour") \
        .groupBy(
            window(col("created_at"), "1 day").alias("time_window"),
            col("transaction_type")
        ) \
        .agg(
            count("*").alias("total_transactions"),
            spark_sum("amount").alias("total_amount"),
            avg("amount").alias("avg_amount"),
            count("user_id").alias("unique_users")
        ) \
        .select(
            col("time_window.start").cast("date").alias("date"),
            col("transaction_type"),
            col("total_transactions"),
            col("total_amount"),
            col("avg_amount"),
            col("unique_users"),
            current_timestamp().alias("updated_at")
        )
    
    query = result_df.writeStream \
        .format("delta") \
        .outputMode("complete") \
        .option("checkpointLocation", f"{CHECKPOINT_BASE}/transaction_summary") \
        .trigger(processingTime="1 minute") \
        .toTable(GOLD_TABLES['transaction_summary'])
    
    print(f"✅ Started: Transaction Summary")
    return query


def main():
    print("=" * 60)
    print("Gold Streaming Pipeline - Silver to Gold Materialized Views")
    print("=" * 60)
    
    # Create Spark session with Delta Lake support
    builder = SparkSession.builder \
        .appName("Gold_Streaming_Pipeline") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
        .config("spark.jars.packages", "io.delta:delta-spark_2.12:3.1.0") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.sql.streaming.statefulOperator.checkCorrectness.enabled", "false")
    
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
    
    # Create Gold tables
    create_gold_tables()
    
    # Start all streaming queries
    queries = []
    
    try:
        queries.append(build_daily_active_users(spark))
        queries.append(build_station_activity(spark))
        queries.append(build_route_usage(spark))
        queries.append(build_topup_summary(spark))
        queries.append(build_transaction_summary(spark))
    except Exception as e:
        print(f"❌ Error starting queries: {e}")
        raise
    
    print("\n" + "=" * 60)
    print("🚀 All Gold streaming queries started successfully!")
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

