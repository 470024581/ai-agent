# Remaining Implementation Steps
# 剩余实施步骤

## Completed Steps (步骤 1-13) ✅

- ✅ **步骤 1**: 文档准备（业务指标、数据模型、云服务设置）
- ✅ **步骤 2**: Supabase 配置和表结构创建
- ✅ **步骤 3**: 模拟数据生成脚本
- ✅ **步骤 4**: 数据验证脚本
- ✅ **步骤 5**: Airbyte 配置
- ✅ **步骤 6**: Databricks 配置和表结构
- ✅ **步骤 7**: 数据同步脚本（备用）
- ✅ **步骤 8**: dbt 项目初始化
- ✅ **步骤 9**: dbt Staging 模型（5个）
- ✅ **步骤 10**: dbt 维度表模型（4个）
- ✅ **步骤 11**: dbt 事实表模型（2个）
- ✅ **步骤 12**: dbt Marts 汇总表（5个）
- ✅ **步骤 13**: dbt 自定义测试和文档

## Remaining Steps (步骤 14-18) 📋

---

## 步骤 14: 调度配置 - dbt Cloud 或 Airflow ⏰

**目标**: 设置自动化调度，定期运行 dbt 管道

### 选项 A: dbt Cloud（推荐，更简单）

**优点**:
- 无需额外基础设施
- 内置调度器
- 自动文档托管
- 简单的 UI 配置
- 免费版支持基本功能

**配置步骤**:

1. **连接 dbt Cloud 项目**
   - 登录 dbt Cloud
   - 连接 GitHub/GitLab 仓库（或手动上传）
   - 配置 Databricks 连接

2. **创建 Environment**
   - Development Environment（开发）
   - Production Environment（生产）

3. **创建 Job**
   - 配置执行命令：
     ```bash
     dbt deps
     dbt run --select staging+ dimensions+ facts+ marts+
     dbt test
     ```
   - 设置超时和重试策略

4. **配置 Schedule**
   - 每日 02:00 UTC 执行
   - 或自定义 cron 表达式

5. **配置通知**
   - 邮件通知
   - Slack Webhook
   - 失败告警

**文档**: 创建 `docs/dbt_cloud_scheduling.md`

---

### 选项 B: Apache Airflow（更灵活，需要运维）

**优点**:
- 完全控制调度逻辑
- 可集成其他任务（Airbyte 同步、数据验证等）
- 支持复杂依赖关系
- 开源免费

**配置步骤**:

1. **安装 Airflow**
   ```bash
   pip install apache-airflow
   pip install apache-airflow-providers-databricks
   ```

2. **创建 DAG 文件**
   - 位置：`data_warehouse/airflow/dags/shanghai_transport_pipeline.py`
   - 包含任务：
     - Airbyte 同步（可选）
     - dbt run（staging → dimensions → facts → marts）
     - dbt test
     - 数据质量检查
     - 通知

3. **配置连接**
   - Databricks 连接
   - Airbyte 连接（如果集成）
   - 通知连接（邮件/Slack）

4. **设置调度**
   - DAG schedule_interval: `'0 2 * * *'`（每日 02:00）
   - 配置重试和告警

5. **部署 Airflow**
   - 本地运行：`airflow standalone`
   - 或部署到云：AWS MWAA, Google Cloud Composer, Astronomer

**文档**: 创建 `docs/airflow_scheduling.md`

---

**交付物**:
- `docs/dbt_cloud_scheduling.md` - dbt Cloud 调度配置指南
- `docs/airflow_scheduling.md` - Airflow 调度配置指南
- `airflow/dags/shanghai_transport_pipeline.py` - Airflow DAG 文件（如果选择 Airflow）
- `airflow/config/airflow.cfg` - Airflow 配置文件（如果选择 Airflow）

---

## 步骤 15: Power BI 连接和报表设计 📊

**目标**: 连接 Power BI 到 Databricks Marts 表，创建可视化报表

### 15.1 Power BI 连接配置

1. **安装 Power BI Desktop**
   - 下载：https://powerbi.microsoft.com/desktop/
   - 免费版本

2. **安装 Databricks ODBC 驱动**
   - 下载：https://databricks.com/spark/odbc-driver-download
   - 安装驱动

3. **连接 Databricks**
   - Get Data > Databricks
   - 填写连接信息：
     - Server Hostname: `${DATABRICKS_SERVER_HOSTNAME}`
     - HTTP Path: `${DATABRICKS_HTTP_PATH}`
     - Authentication: Personal Access Token
     - Token: `${DATABRICKS_TOKEN}`

4. **选择 Marts 表**
   - 导航到 `workspace.marts` schema
   - 选择表：
     - daily_active_users
     - daily_topup_summary
     - station_flow_daily
     - user_card_type_summary
     - route_usage_summary

5. **选择数据模式**
   - Import（导入）：快速，数据缓存在 Power BI
   - DirectQuery（直连）：实时，查询 Databricks

### 15.2 数据模型配置

1. **建立表关系**
   - 在 Model 视图中建立关系
   - 例如：daily_active_users.date ↔ daily_topup_summary.date

2. **创建度量值（DAX）**
   ```dax
   // 日活用户
   DAU = SUM(daily_active_users[active_users])
   
   // 总充值金额
   Total Topup = SUM(daily_topup_summary[total_amount])
   
   // 平均交易金额
   Avg Transaction Amount = 
       SUM(daily_active_users[total_amount]) / 
       SUM(daily_active_users[total_transactions])
   
   // 周环比增长
   WoW Growth = 
       DIVIDE(
           [DAU] - CALCULATE([DAU], DATEADD(daily_active_users[date], -7, DAY)),
           CALCULATE([DAU], DATEADD(daily_active_users[date], -7, DAY))
       )
   ```

### 15.3 报表设计

**页面 1: 概览仪表盘**
- KPI 卡片：
  - 今日活跃用户
  - 今日交易量
  - 今日充值金额
- 折线图：日活用户趋势（最近 30 天）
- 柱状图：每日交易量趋势
- 面积图：充值金额趋势

**页面 2: 站点分析**
- 地图可视化：站点热力图（使用经纬度）
- 条形图：站点流量排名（Top 20）
- 表格：站点详细数据
- 切片器：站点类型筛选

**页面 3: 用户分析**
- 饼图：卡类型分布
- 柱状图：各卡类型交易量对比
- 散点图：充值习惯分析
- 矩阵表：用户行为详细数据

**页面 4: 线路分析**
- 条形图：线路受欢迎程度排名
- 柱状图：地铁 vs 公交对比
- 折线图：线路使用趋势
- 表格：线路详细指标

**页面 5: 支付分析**
- 饼图：支付方式分布
- 堆叠柱状图：每日支付方式趋势
- KPI：各支付方式占比

### 15.4 交互控件

- **时间切片器**：日期范围选择
- **线路筛选器**：下拉列表
- **用户类型筛选器**：切片器
- **站点类型筛选器**：按钮

### 15.5 性能优化

- 使用 DirectQuery 模式（实时数据）
- 或使用 Import 模式 + 定期刷新
- 设置数据刷新计划（Power BI Service）
- 优化 DAX 查询

**交付物**:
- `docs/powerbi_setup.md` - Power BI 连接设置文档（已创建）
- `docs/powerbi_reports.md` - 报表设计文档（已创建）
- `powerbi/connection_string.txt` - 连接字符串模板（已创建）
- `powerbi/dax_measures.txt` - DAX 度量值模板（已创建）
- `powerbi/shanghai_transport.pbix` - Power BI 报表文件（需要手动创建）

---

## 步骤 16: 数据流验证和监控 🔍

**目标**: 创建端到端数据流验证和监控工具

### 16.1 数据流验证脚本

创建 `scripts/validate_pipeline.py`：

**功能**:
1. 验证 Supabase → Databricks 数据同步
   - 行数对比
   - 最新数据时间戳对比
   - 数据完整性检查

2. 验证 dbt 模型执行
   - 检查所有模型是否存在
   - 检查最后更新时间
   - 检查行数是否合理

3. 验证指标一致性
   - 对比不同层级的指标
   - 例如：fact_transactions 总金额 = daily_active_users 总金额之和

4. 生成验证报告
   - HTML 报告
   - JSON 报告
   - 发送邮件/Slack 通知

### 16.2 监控脚本

创建 `scripts/monitor.py`：

**功能**:
1. 数据更新监控
   - 检查最后更新时间
   - 告警数据延迟

2. 数据质量监控
   - 运行 dbt tests
   - 检查测试失败
   - 告警数据质量问题

3. 异常检测
   - 检测异常值（例如：日活突然下降）
   - 检测数据缺失
   - 告警异常情况

4. 告警机制
   - 邮件告警
   - Slack Webhook
   - 钉钉/企业微信（可选）

### 16.3 监控配置

创建 `config/monitor_config.yml`：

```yaml
monitoring:
  # Data freshness thresholds
  freshness:
    max_delay_hours: 24
    
  # Data quality thresholds
  quality:
    min_daily_users: 100
    max_daily_users: 100000
    min_daily_transactions: 500
    
  # Alert channels
  alerts:
    email:
      enabled: true
      recipients: ["team@example.com"]
    slack:
      enabled: true
      webhook_url: "${SLACK_WEBHOOK_URL}"
```

**交付物**:
- `scripts/validate_pipeline.py` - 数据流验证脚本
- `scripts/monitor.py` - 监控脚本
- `config/monitor_config.yml` - 监控配置
- `docs/validate_pipeline.md` - 验证脚本文档
- `docs/monitoring.md` - 监控文档

---

## 步骤 17: 性能优化 ⚡

**目标**: 优化数据仓库性能

### 17.1 Databricks 优化

1. **表优化**
   ```sql
   -- Optimize Delta tables
   OPTIMIZE workspace.facts.fact_transactions;
   OPTIMIZE workspace.facts.fact_topups;
   
   -- Z-Ordering for frequently filtered columns
   OPTIMIZE workspace.facts.fact_transactions
   ZORDER BY (user_key, station_key, transaction_type);
   ```

2. **Vacuum 清理**
   ```sql
   -- Clean up old versions (keep 7 days)
   VACUUM workspace.facts.fact_transactions RETAIN 168 HOURS;
   ```

3. **表统计信息**
   ```sql
   -- Analyze tables for query optimization
   ANALYZE TABLE workspace.facts.fact_transactions COMPUTE STATISTICS;
   ```

### 17.2 dbt 优化

1. **增量模型**
   - 将大型 fact 表改为增量模型
   - 只处理新/更新的记录

2. **并行执行**
   - 增加 threads 数量（profiles.yml）
   - 优化模型依赖关系

3. **物化策略**
   - 评估 view vs table 的选择
   - 考虑使用 ephemeral 模型

### 17.3 Airbyte 优化

1. **同步频率**
   - 根据数据量调整同步频率
   - 使用增量同步（CDC）

2. **批量大小**
   - 调整批量大小
   - 平衡速度和资源使用

### 17.4 Power BI 优化

1. **数据模式**
   - 评估 Import vs DirectQuery
   - 使用聚合表

2. **DAX 优化**
   - 优化复杂 DAX 查询
   - 使用变量减少重复计算

3. **视觉对象**
   - 减少页面上的视觉对象数量
   - 使用书签和按钮切换视图

**交付物**:
- `docs/optimization.md` - 性能优化文档
- `sql/optimize_tables.sql` - 表优化 SQL 脚本
- `scripts/optimize_databricks.py` - 自动化优化脚本

---

## 步骤 18: 最终验证和文档整理 📝

**目标**: 完整验证整个数据仓库闭环，整理所有文档

### 18.1 端到端测试

1. **数据流测试**
   - 在 Supabase 插入测试数据
   - 验证 Airbyte 同步
   - 验证 dbt 模型更新
   - 验证 Power BI 显示

2. **调度测试**
   - 手动触发调度任务
   - 验证执行成功
   - 验证告警机制

3. **性能测试**
   - 测试查询响应时间
   - 测试 Power BI 报表加载速度
   - 验证并发查询性能

### 18.2 文档整理

1. **更新 README**
   - 项目概述
   - 快速开始指南
   - 架构图
   - 文档索引

2. **创建架构图**
   - 数据流图
   - 系统架构图
   - ER 图

3. **操作手册**
   - 日常运维指南
   - 故障排查指南
   - 常见问题 FAQ

### 18.3 知识转移

1. **团队培训**
   - dbt 使用培训
   - Power BI 报表使用培训
   - 故障排查培训

2. **文档交付**
   - 所有技术文档
   - 操作手册
   - 培训材料

**交付物**:
- `README.md` - 项目主文档（更新）
- `docs/architecture.md` - 架构文档
- `docs/operations.md` - 运维手册
- `docs/troubleshooting.md` - 故障排查指南
- `docs/faq.md` - 常见问题

---

## 步骤优先级和时间估算

| 步骤 | 优先级 | 预估时间 | 依赖 |
|-----|--------|---------|------|
| 步骤 14: 调度配置 | 🔴 高 | 4-8 小时 | 步骤 1-13 |
| 步骤 15: Power BI | 🔴 高 | 8-16 小时 | 步骤 1-13 |
| 步骤 16: 验证监控 | 🟡 中 | 4-6 小时 | 步骤 14 |
| 步骤 17: 性能优化 | 🟡 中 | 2-4 小时 | 步骤 14-16 |
| 步骤 18: 最终验证 | 🟢 低 | 2-4 小时 | 步骤 14-17 |

## 推荐实施顺序

### 阶段 1: 核心功能（必须完成）
1. ✅ **步骤 14**: 调度配置（选择 dbt Cloud 或 Airflow）
2. ✅ **步骤 15**: Power BI 连接和基础报表

### 阶段 2: 监控和优化（推荐完成）
3. ✅ **步骤 16**: 数据流验证和监控
4. ✅ **步骤 17**: 性能优化

### 阶段 3: 完善和交付（可选）
5. ✅ **步骤 18**: 最终验证和文档整理

## 调度工具选择建议

### 选择 dbt Cloud 如果：
- ✅ 团队规模小，无专职运维
- ✅ 只需要运行 dbt 管道
- ✅ 希望快速上线
- ✅ 预算有限（免费版够用）

### 选择 Airflow 如果：
- ✅ 需要集成多个数据源和工具
- ✅ 需要复杂的依赖关系和条件逻辑
- ✅ 有运维团队支持
- ✅ 需要完全控制调度逻辑
- ✅ 已有 Airflow 基础设施

## 下一步行动

**立即执行**:
1. 选择调度工具（dbt Cloud 或 Airflow）
2. 开始步骤 14：调度配置
3. 并行开始步骤 15：Power BI 连接

**告诉我您的选择**:
- 您倾向于使用 dbt Cloud 还是 Airflow？
- 是否需要我详细展开步骤 14 的具体配置？

