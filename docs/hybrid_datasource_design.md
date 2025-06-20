# 混合数据源设计文档

## 概述

混合数据源是一种新的数据源类型，能够智能地处理不同类型的文件，将结构化数据（CSV/Excel）路由到SQL处理流程，将非结构化数据（TXT/PDF/Word）路由到RAG处理流程。这种设计为LangGraph等高级工作流程提供了灵活的数据处理基础。

## 架构设计

### 1. 数据源类型扩展

在 `DataSourceType` 枚举中添加了新的 `HYBRID` 类型：

```python
class DataSourceType(str, Enum):
    DEFAULT = "default"
    KNOWLEDGE_BASE = "knowledge_base"
    SQL_TABLE_FROM_FILE = "sql_table_from_file"
    HYBRID = "hybrid"  # 新增：混合数据源
```

### 2. 文件处理路由

混合数据源根据文件类型自动选择处理方式：

#### SQL处理路径（结构化数据）
- **支持文件类型**: CSV, Excel (.xlsx)
- **处理流程**: 
  1. 解析文件内容到 DataFrame
  2. 创建 SQLite 数据表
  3. 插入数据到表中
  4. 设置数据源的 `db_table_name`
- **查询方式**: 使用 LangChain SQL Agent 进行自然语言到SQL的转换

#### RAG处理路径（非结构化数据）
- **支持文件类型**: TXT, PDF, Word (.docx)
- **处理流程**:
  1. 提取文本内容
  2. 分块处理（chunking）
  3. 生成嵌入向量
  4. 存储到向量数据库
- **查询方式**: 使用向量检索和生成式AI进行问答

### 3. 智能查询路由

混合数据源的查询处理器 `get_answer_from_hybrid_datasource` 实现了智能路由逻辑：

#### 路由决策算法

```python
# SQL指示词
sql_keywords = ['sum', 'count', 'average', 'total', 'sales', 'revenue', 
                'amount', 'quantity', 'statistics', 'report', 'calculate', 
                'how many', 'how much', 'trend', 'analysis']

# RAG指示词
rag_keywords = ['what is', 'explain', 'describe', 'definition', 'meaning', 
                'content', 'document', 'text', 'information about', 
                'tell me about', 'summary of']
```

#### 决策逻辑

1. **优先级路由**: 如果查询包含SQL指示词且有可用的SQL表 → SQL处理
2. **内容路由**: 如果查询包含RAG指示词且有可用的文档 → RAG处理
3. **默认路由**: 按可用数据类型的优先级（SQL > RAG）
4. **无数据处理**: 提示用户上传相应类型的文件

## 实现细节

### 1. 文件处理器更新

在 `file_processor.py` 中扩展了处理逻辑：

```python
# 处理SQL文件（CSV/Excel）
if ((ds_type == DataSourceType.SQL_TABLE_FROM_FILE.value) or 
    (ds_type == DataSourceType.HYBRID.value)) and file_type.lower() in ['csv', 'xlsx']:
    # SQL处理逻辑
    
# 处理RAG文件（TXT/PDF/Word）  
elif ((ds_type == DataSourceType.KNOWLEDGE_BASE.value) or 
      (ds_type == DataSourceType.HYBRID.value and file_type.lower() in ['txt', 'pdf', 'docx'])):
    # RAG处理逻辑
```

### 2. 前端界面更新

在数据源管理界面添加了混合数据源选项：

- 新增混合数据源类型选择
- 添加文件类型说明和帮助信息
- 支持多种文件类型的上传和处理状态显示

### 3. 多语言支持

更新了中英文翻译文件：

```json
{
  "dataSourceType": {
    "hybrid": "混合数据源"
  },
  "hybridDataSourceDescription": "混合数据源支持多种文件类型：CSV/Excel文件将进行SQL处理，TXT/PDF/Word文件将进行RAG处理",
  "hybridDataSourceHelp": "适用于需要同时处理结构化数据（表格）和非结构化数据（文档）的场景"
}
```

## 使用场景

### 1. 企业知识管理
- **结构化数据**: 销售数据、财务报表（CSV/Excel）
- **非结构化数据**: 政策文档、操作手册（PDF/Word）
- **查询示例**: 
  - "本月销售额是多少？"（SQL）
  - "公司的休假政策是什么？"（RAG）

### 2. 客户服务系统
- **结构化数据**: 客户信息、订单数据（CSV）
- **非结构化数据**: FAQ文档、产品说明书（PDF/TXT）
- **查询示例**:
  - "客户ID 12345的订单状态？"（SQL）
  - "如何使用产品功能X？"（RAG）

### 3. 研究分析平台
- **结构化数据**: 实验数据、统计表格（Excel）
- **非结构化数据**: 研究报告、文献资料（PDF/Word）
- **查询示例**:
  - "实验组的平均值是多少？"（SQL）
  - "相关研究的主要发现是什么？"（RAG）

## LangGraph 集成准备

### 1. 节点设计

混合数据源为LangGraph提供了以下节点类型：

```python
# SQL查询节点
class SQLQueryNode:
    def execute(self, query: str) -> Dict[str, Any]:
        return get_answer_from_sqltable_datasource(query, datasource)

# RAG查询节点  
class RAGQueryNode:
    def execute(self, query: str) -> Dict[str, Any]:
        return perform_rag_query(query, datasource)

# 混合路由节点
class HybridRouterNode:
    def execute(self, query: str) -> Dict[str, Any]:
        return get_answer_from_hybrid_datasource(query, datasource)
```

### 2. 工作流设计

```python
# 示例工作流：智能客服
workflow = {
    "start": "query_classifier",
    "query_classifier": {
        "sql_query": "sql_processor", 
        "rag_query": "rag_processor",
        "complex_query": "hybrid_processor"
    },
    "sql_processor": "response_formatter",
    "rag_processor": "response_formatter", 
    "hybrid_processor": "response_formatter",
    "response_formatter": "end"
}
```

### 3. 状态管理

```python
class HybridDataSourceState:
    query: str
    query_type: str  # "sql", "rag", "hybrid"
    sql_result: Optional[Dict[str, Any]]
    rag_result: Optional[Dict[str, Any]]
    final_answer: str
    routing_decision: str
```

## 测试和验证

### 1. 单元测试

- 文件处理路由测试
- 查询路由决策测试
- SQL和RAG处理集成测试

### 2. 集成测试

- 端到端文件上传和处理测试
- 多种查询类型的路由测试
- 前端界面交互测试

### 3. 性能测试

- 大文件处理性能
- 并发查询处理能力
- 内存使用优化

## 扩展计划

### 1. 高级路由算法

- 基于机器学习的查询分类
- 上下文感知的路由决策
- 多轮对话的状态保持

### 2. 更多文件类型支持

- JSON/XML文件处理
- 图片文件的OCR处理
- 音频/视频文件的转录

### 3. 混合查询处理

- SQL和RAG结果的智能融合
- 跨数据源的关联查询
- 复杂分析工作流的自动化

## 总结

混合数据源的设计为AI助手系统提供了强大的数据处理能力，能够智能地处理不同类型的数据源，为用户提供统一的查询界面。这种设计不仅提高了系统的灵活性，也为未来的LangGraph集成奠定了坚实的基础。

通过智能路由机制，系统能够自动选择最适合的处理方式，为用户提供准确、高效的查询结果。这种设计模式可以广泛应用于企业知识管理、客户服务、研究分析等多个领域。 