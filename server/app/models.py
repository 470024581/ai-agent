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
    DEFAULT = "default"  # Default  data source (formatted, predefined tables)
    KNOWLEDGE_BASE = "knowledge_base"  # Knowledge base/document collection (unstructured RAG, local embeddings)
    SQL_TABLE_FROM_FILE = "sql_table_from_file"  # Data source for SQL tables created from files (formatted, dynamic tables)

class FileType(str, Enum):
    PDF = "pdf"
    TXT = "txt"
    TEXT = "txt"  # Alias for TXT
    DOCX = "docx"
    CSV = "csv"
    XLSX = "xlsx"
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
    query: str
    datasource_id: Optional[int] = None  # Added data source support

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
    total_revenue: float
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