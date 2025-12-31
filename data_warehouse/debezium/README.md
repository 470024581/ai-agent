# CDC Pipeline - 核心文件说明

## 架构

```
PostgreSQL (Docker) → Debezium → Kafka → Structured Streaming → Databricks
```

## 核心文件

1. **`postgres.json`** - Debezium connector 配置
2. **`../scripts/cdc_streaming.py`** - Structured Streaming 程序
3. **`../scripts/register_connector.sh`** - Connector 注册脚本
4. **`../scripts/requirements.txt`** - Python 依赖

## 快速开始

### 1. 配置 PostgreSQL 逻辑复制

```bash
# 方法1: 使用 SQL 脚本（推荐）
docker exec -i postgres psql -U dbuser -d transport_dw < ../scripts/setup_postgres_replication.sql
docker restart postgres

# 方法2: 直接执行 SQL 命令
docker exec -it postgres psql -U dbuser -d transport_dw -c "ALTER SYSTEM SET wal_level = 'logical';"
docker exec -it postgres psql -U dbuser -d transport_dw -c "ALTER USER dbuser WITH REPLICATION;"
docker restart postgres

# 验证配置（重启后）
docker exec -it postgres psql -U dbuser -d transport_dw -c "SHOW wal_level;"
# 应该返回: logical
```

### 2. 注册 Debezium Connector

```bash
cd data_warehouse/scripts
bash register_connector.sh

# 或者直接用 curl:
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d @../debezium/postgres.json
```

### 3. 设置环境变量

```bash
export DATABRICKS_SERVER_HOSTNAME=your-workspace.cloud.databricks.com
export DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id
export DATABRICKS_TOKEN=your_token
export DATABRICKS_CATALOG=hive_metastore  # 可选，默认值
export DATABRICKS_SCHEMA=public  # 可选，默认值
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092  # 可选，默认值
export CHECKPOINT_BASE=dbfs:/checkpoints/cdc  # 可选，默认值
export TABLE_DISCOVERY_INTERVAL=600  # 可选，新表发现扫描间隔（秒），默认 600（10分钟）
```

### 4. 安装依赖

```bash
pip install -r data_warehouse/scripts/requirements.txt
```

### 5. 运行 Streaming 程序

```bash
spark-submit \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
  data_warehouse/scripts/cdc_streaming.py
```

## 功能特性

- ✅ 自动处理所有 `transport_dw.public.*` 主题
- ✅ 处理快照数据 (op='r') 和 CDC 数据 (op='c'/'u'/'d')
- ✅ 自动 Schema Evolution（Delta Lake mergeSchema）
- ✅ 自动添加元数据列（_debezium_op, _debezium_ts_ms, _is_deleted 等）
- ✅ Checkpoint 支持，支持故障恢复
- ✅ 表自动创建（如果不存在）

## 数据流程

1. **快照阶段**: Debezium 读取所有历史数据，发送到 Kafka（op='r'）
2. **CDC 阶段**: PostgreSQL 变更实时捕获，发送到 Kafka（op='c'/'u'/'d'）
3. **Streaming**: 从 Kafka 读取，写入 Databricks Delta Lake
4. **Schema Evolution**: 新列自动添加，使用 Delta Lake mergeSchema

## 注意事项

- 首次运行会处理所有历史数据（snapshot）
- 表会自动创建（如果不存在），使用 `cdc_` 前缀
- Schema 变更会自动合并（添加新列）
- 删除操作会标记 `_is_deleted=true`，不会物理删除
- Checkpoint 位置在 `dbfs:/checkpoints/cdc/{table_name}`

## 验证

检查 Kafka 主题：
```bash
docker exec -it kafka kafka-topics --list --bootstrap-server localhost:9092
```

检查 Connector 状态：
```bash
curl http://localhost:8083/connectors/postgres-transport-cdc/status | jq
```

检查 Databricks 表：
```sql
SHOW TABLES IN hive_metastore.public LIKE 'cdc_*';
SELECT COUNT(*) FROM cdc_users;
```
