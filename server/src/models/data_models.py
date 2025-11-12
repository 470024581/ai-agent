from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# ================== Base Models ==================

# Generic Response Model
class BaseResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None

# ================== Data Source Management Models ==================

class DataSourceType(str, Enum):
    DEFAULT = "default"  # Built-in ERP system data source (customers, products, orders, sales, inventory)
    KNOWLEDGE_BASE = "knowledge_base"  # Document knowledge base for RAG queries (PDF, DOCX, TXT)
    HYBRID = "hybrid"  # Hybrid data source: supports both document uploads and RAG processing

class FileType(str, Enum):
    PDF = "pdf"
    TXT = "txt"
    TEXT = "txt"  # Alias for TXT
    DOCX = "docx"
    MD = "md"
    MARKDOWN = "md"  # Alias for MD
    UNKNOWN = "unknown"

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# Data Source Model
class DataSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    type: DataSourceType = DataSourceType.KNOWLEDGE_BASE

class DataSourceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

class DataSource(BaseModel):
    id: int
    name: str
    description: Optional[str]
    type: DataSourceType
    is_active: bool
    file_count: int = 0  # For SQL_TABLE_FROM_FILE, this might represent source file count (usually 1) or remain 0
    db_table_name: Optional[str] = None  # New: stores the associated database table name
    created_at: datetime
    updated_at: datetime

class DataSourceResponse(BaseResponse):
    data: Optional[DataSource] = None

class DataSourceListResponse(BaseResponse):
    data: List[DataSource] = []

# File Management Models
class FileUpload(BaseModel):
    filename: str
    file_type: FileType
    file_size: int
    datasource_id: int

class FileInfo(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_type: FileType
    file_size: int
    datasource_id: int
    processing_status: ProcessingStatus
    processed_chunks: Optional[int] = 0
    error_message: Optional[str] = None
    uploaded_at: datetime
    processed_at: Optional[datetime] = None

class FileListResponse(BaseResponse):
    data: List[FileInfo] = []

# File Processing Status
class FileProcessingStatus(BaseModel):
    file_id: int
    status: ProcessingStatus
    progress: Optional[float] = None  # 0-100
    message: Optional[str] = None
    chunks_processed: Optional[int] = 0
    total_chunks: Optional[int] = 0

# ================== Existing Models ==================

# Base Request Model
class QueryRequest(BaseModel):
    """Request model for intelligent analysis queries"""
    query: str
    datasource_id: int
    client_id: Optional[str] = None # Add client_id for WebSocket association

class InventoryQueryRequest(BaseModel):
    query: str
    threshold: Optional[int] = 50
    datasource_id: Optional[int] = None

# Sales Query Response Model
class SalesQueryResponse(BaseResponse):
    query: str
    query_type: str
    answer: str
    data: Optional[Dict[str, Any]] = None
    chart_data: Optional[Dict[str, Any]] = None
    datasource_id: Optional[int] = None

# Inventory Related Models
class LowStockItem(BaseModel):
    product_name: str
    product_id: str
    stock_level: int
    predicted_need: Optional[int] = None
    status: Optional[str] = "low"  # "low" or "critical"

class InventoryResponse(BaseResponse):
    query: str
    query_type: str
    answer: str
    data: Dict[str, Any]  # Contains low_stock_items and total_count
    chart_data: Optional[Dict[str, Any]] = None
    datasource_id: Optional[int] = None

# Report Related Models
class ProductSalesInfo(BaseModel):
    name: str
    total_amount: float
    total_quantity: int

class SalesReportData(BaseModel):
    total_sales: float
    total_quantity: int
    unique_products: int
    average_order_value: float
    top_products_by_revenue: List[ProductSalesInfo]
    top_products_by_quantity: List[ProductSalesInfo]
    detailed_sales: List[Dict[str, Any]]

class SalesReportResponse(BaseResponse):
    summary: str
    report_date: str
    data: Optional[SalesReportData] = None
    chart_data: Optional[Dict[str, Any]] = None
    datasource_id: Optional[int] = None

# Backward Compatible Legacy Models
class QueryResponse(BaseModel):
    """Response model for intelligent queries"""
    answer: str
    data_for_chart: Optional[Dict[str, Any]] = None
    datasource_id: Optional[int] = None

class ReportResponse(BaseModel):
    summary: str
    report_data: Optional[Dict[str, Any]] = None
    data_for_chart: Optional[Dict[str, Any]] = None
    datasource_id: Optional[int] = None

# Chart Data Models
class ChartDataset(BaseModel):
    label: str
    data: List[float]
    backgroundColor: Optional[List[str]] = None
    borderColor: Optional[List[str]] = None
    borderWidth: Optional[int] = 1

class ChartData(BaseModel):
    type: str  # "bar", "line", "doughnut", "horizontalBar", etc.
    labels: List[str]
    datasets: List[ChartDataset]

class NodeStatus(str, Enum):
    """Node execution status"""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    ERROR = "error"

class WorkflowEventType(str, Enum):
    """Workflow event types"""
    EXECUTION_STARTED = "execution_started"
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_ERROR = "node_error"
    EDGE_ACTIVATED = "edge_activated"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_ERROR = "execution_error"
    TOKEN_STREAM = "token_stream"  # NEW: Token-level streaming
    REACT_STEP_THOUGHT = "react_step_thought"  # NEW: ReAct thinking step
    REACT_STEP_ACTION = "react_step_action"  # NEW: ReAct action step
    REACT_STEP_OBSERVATION = "react_step_observation"  # NEW: ReAct observation step

class WorkflowEvent(BaseModel):
    """Workflow event message"""
    type: WorkflowEventType
    execution_id: str
    timestamp: float
    node_id: Optional[str] = None
    edge_from: Optional[str] = None
    edge_to: Optional[str] = None
    status: Optional[NodeStatus] = None
    duration: Optional[float] = None
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    retry_count: Optional[int] = None
    quality_score: Optional[int] = None
    token: Optional[str] = None  # NEW: For TOKEN_STREAM events, contains the token text
    stream_complete: Optional[bool] = None  # NEW: Indicates if streaming is complete
    # NEW: ReAct step fields
    react_step_type: Optional[str] = None  # "thought", "action", "observation"
    react_step_index: Optional[int] = None  # Step sequence number
    react_step_content: Optional[str] = None  # Step content/description
    react_tool_name: Optional[str] = None  # Tool name (for action steps)
    react_tool_input: Optional[Dict[str, Any]] = None  # Tool input (for action steps)

class NodeExecutionDetails(BaseModel):
    """Detailed node execution information"""
    node_id: str
    node_type: str
    status: NodeStatus
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    input_summary: Optional[Dict[str, Any]] = None
    output_summary: Optional[Dict[str, Any]] = None
    error_details: Optional[str] = None
    memory_usage: Optional[int] = None
    retry_count: int = 0

class ExecutionSummary(BaseModel):
    """Complete execution summary"""
    execution_id: str
    total_duration: float
    nodes_executed: int
    nodes_failed: int
    total_memory_peak: int
    start_timestamp: float
    end_timestamp: Optional[float] = None
    final_quality_score: int
    success: bool
    node_details: List[NodeExecutionDetails] = []

class NodeState(BaseModel):
    """Node state information"""
    id: str
    status: NodeStatus
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    duration: Optional[float] = None
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    node_type: Optional[str] = None
    input_summary: Optional[Dict[str, Any]] = None
    output_summary: Optional[Dict[str, Any]] = None
    memory_usage: Optional[int] = None
    retry_count: int = 0

class ExecutionState(BaseModel):
    """Execution state information"""
    execution_id: str
    start_time: float
    end_time: Optional[float] = None
    status: NodeStatus
    current_node: Optional[str] = None
    nodes: Dict[str, NodeState] = {}
    error: Optional[str] = None 