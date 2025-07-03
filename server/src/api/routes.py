from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, BackgroundTasks, WebSocket, WebSocketDisconnect, Request
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import os
import uuid
import aiofiles
from pathlib import Path
from ..models.data_models import (
    QueryRequest, QueryResponse, 
    BaseResponse,
    DataSourceCreate, DataSourceUpdate, DataSource, DataSourceResponse, DataSourceListResponse,
    FileInfo, FileListResponse, ProcessingStatus, FileType, DataSourceType,
    WorkflowEvent,
    WorkflowEventType,
    NodeStatus,
)
from ..agents.intelligent_agent import (
    get_answer_from, 
    initialize_app_state
)
from ..chains.langgraph_flow import process_intelligent_query
from ..websocket.websocket_manager import websocket_manager
from ..database.db_operations import (
    # Data source management functions
    get_datasources, get_datasource, create_datasource, update_datasource,
    delete_datasource, set_active_datasource, get_active_datasource,
    # File management functions
    save_file_info, get_files_by_datasource, update_file_processing_status,
    delete_file_record_and_associated_data
)
from ..utils.common_utils import (
    create_api_response, parse_query_intent
)
from ..document_loaders.file_processor import process_uploaded_file
from ..config.config import DATA_DIR
import json
import sqlite3
from fastapi.responses import FileResponse, StreamingResponse
import logging
import asyncio
from pydantic import BaseModel
import pandas as pd

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Smart  API"])

# File upload directory configuration
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE_DATA_DIR = DATA_DIR / "sample_sales"
# Ensure sample data directory exists (though generator script also does this)
SAMPLE_DATA_DIR.mkdir(parents=True, exist_ok=True)

class IntelligentAnalysisRequest(BaseModel):
    """Request model for intelligent analysis endpoint"""
    query: str
    datasource_id: int
    client_id: str

# ==================== Sample Data API ======================

@router.get("/api/v1/sample-data-files", summary="List Sample Sales Data CSV Files")
async def list_sample_data_files():
    """Lists available sample sales data CSV files."""
    try:
        files = []
        if SAMPLE_DATA_DIR.exists() and SAMPLE_DATA_DIR.is_dir():
            for item in os.listdir(SAMPLE_DATA_DIR):
                if item.startswith("sample_sales_") and item.endswith(".csv"):
                    files.append({
                        "filename": item,
                        "year": item.replace("sample_sales_", "").replace(".csv", "")
                    })
        # Sort by year if possible
        files.sort(key=lambda x: x.get("year", ""))
        return {"success": True, "data": files}
    except Exception as e:
        return {"success": False, "error": f"Failed to list sample data files: {str(e)}", "data": []}

@router.get("/api/v1/sample-data-files/{filename}", summary="Download Sample Sales Data CSV File")
async def download_sample_data_file(filename: str):
    """Downloads a specific sample sales data CSV file."""
    try:
        if not (filename.startswith("sample_sales_") and filename.endswith(".csv") and ".." not in filename):
            raise HTTPException(status_code=400, detail="Invalid filename requested.")
            
        file_path = SAMPLE_DATA_DIR / filename
        if not file_path.is_file():
            raise HTTPException(status_code=404, detail="Sample data file not found.")
        
        return FileResponse(file_path, media_type='text/csv', filename=filename)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not download file: {str(e)}")

# ==================== Data Source Management API ====================

@router.get("/api/v1/datasources", response_model=DataSourceListResponse, summary="Get Data Source List")
async def get_datasources_list():
    """Get a list of all data sources"""
    try:
        datasources_dicts = await get_datasources()
        
        # Convert dictionary objects to DataSource models
        datasources = []
        for ds_dict in datasources_dicts:
            try:
                # Ensure the type is properly converted to DataSourceType enum
                ds_dict['type'] = DataSourceType(ds_dict['type'])
                datasource = DataSource(**ds_dict)
                datasources.append(datasource)
            except ValueError as ve:
                logger.error(f"Invalid data source type '{ds_dict.get('type')}' for datasource ID {ds_dict.get('id')}: {ve}")
                continue  # Skip invalid datasources
            except Exception as pe:
                logger.error(f"Error creating DataSource model for ID {ds_dict.get('id')}: {pe}")
                continue  # Skip invalid datasources
        
        return DataSourceListResponse(
            success=True,
            data=datasources,
            message=f"Retrieved {len(datasources)} data sources"
        )
    except Exception as e:
        logger.error(f"Error in get_datasources_list: {e}")
        return DataSourceListResponse(
            success=False,
            error=f"Failed to retrieve data source list: {str(e)}",
            data=[]
        )

@router.post("/api/v1/datasources", response_model=DataSourceResponse, summary="Create Data Source")
async def create_datasource_api(request: DataSourceCreate):
    """Create a new data source"""
    try:
        datasource = await create_datasource(
            name=request.name,
            description=request.description,
            ds_type=request.type.value
        )
        
        if datasource:
            return DataSourceResponse(
                success=True,
                data=DataSource(**datasource),
                message=f"Data source '{request.name}' created successfully"
            )
        else:
            return DataSourceResponse(
                success=False,
                error="Failed to create data source. Name might already exist or another issue occurred."
            )
    except sqlite3.IntegrityError as ie:
         if "UNIQUE constraint failed: datasources.name" in str(ie):
            return DataSourceResponse(success=False, error=f"Data source name '{request.name}' already exists.")
         return DataSourceResponse(success=False, error=f"Database integrity error: {str(ie)}")
    except Exception as e:
        return DataSourceResponse(
            success=False,
            error=f"Failed to create data source: {str(e)}"
        )

@router.get("/api/v1/datasources/active", response_model=DataSourceResponse, summary="Get Active Data Source")
async def get_active_datasource_api():
    """Get the currently active data source"""
    try:
        datasource_dict = await get_active_datasource()
        if datasource_dict:
            try:
                if 'type' not in datasource_dict or datasource_dict['type'] is None:
                    error_msg = f"Data source type is missing or null in database for active data source ID {datasource_dict.get('id')}."
                    raise HTTPException(status_code=500, detail=f"Invalid data source configuration: {error_msg}")
                
                datasource_dict['type'] = DataSourceType(datasource_dict['type'])
            except ValueError as ve:
                error_msg = f"Invalid data source type value '{datasource_dict.get('type')}' found in database for active data source ID {datasource_dict.get('id')}. Expected one of {list(DataSourceType.__members__.keys())}. Error: {ve}"
                raise HTTPException(status_code=500, detail=f"Invalid data source configuration: {error_msg}")

            try:
                datasource_model = DataSource(**datasource_dict)
            except Exception as pydantic_error:
                error_msg = f"Pydantic validation error for DataSource ID {datasource_dict.get('id')}: {str(pydantic_error)}"
                raise HTTPException(status_code=422, detail=f"Data validation failed for active data source: {error_msg}")

            return DataSourceResponse(
                success=True,
                data=datasource_model,
                message="Active data source retrieved successfully"
            )
        else:
            return DataSourceResponse(
                success=False,
                error="No active data source found",
                data=None
            )
    except HTTPException:
        raise
    except Exception as e:
        return DataSourceResponse(
            success=False,
            error=f"Failed to retrieve active data source: {str(e)}",
            data=None
        )

@router.get("/api/v1/datasources/{datasource_id}", response_model=DataSourceResponse, summary="Get Specific Data Source")
async def get_datasource_detail(datasource_id: int):
    """Get details of a specific data source"""
    try:
        datasource_dict = await get_datasource(datasource_id)
        if datasource_dict:
            datasource_dict['type'] = DataSourceType(datasource_dict['type'])
            datasource = DataSource(**datasource_dict)
            return DataSourceResponse(
                success=True,
                data=datasource,
                message=f"Data source {datasource_id} retrieved successfully"
            )
        else:
            raise HTTPException(status_code=404, detail="Data source not found")
    except HTTPException:
        raise
    except Exception as e:
        return DataSourceResponse(
            success=False,
            error=f"Failed to retrieve data source {datasource_id}: {str(e)}",
            data=None
        )

@router.put("/api/v1/datasources/{datasource_id}", response_model=DataSourceResponse, summary="Update Data Source")
async def update_datasource_api(datasource_id: int, request: DataSourceUpdate):
    """Update an existing data source"""
    try:
        datasource = await update_datasource(
            datasource_id=datasource_id,
            name=request.name,
            description=request.description
        )
        
        if datasource:
            datasource['type'] = DataSourceType(datasource['type'])
            return DataSourceResponse(
                success=True,
                data=DataSource(**datasource),
                message=f"Data source {datasource_id} updated successfully"
            )
        else:
            raise HTTPException(status_code=404, detail="Data source not found")
    except HTTPException:
        raise
    except Exception as e:
        return DataSourceResponse(
            success=False,
            error=f"Failed to update data source {datasource_id}: {str(e)}"
        )

@router.delete("/api/v1/datasources/{datasource_id}", response_model=BaseResponse, summary="Delete Data Source")
async def delete_datasource_api(datasource_id: int):
    """Delete a data source"""
    try:
        success = await delete_datasource(datasource_id)
        if success:
            return BaseResponse(
                success=True,
                message=f"Data source {datasource_id} deleted successfully"
            )
        else:
            raise HTTPException(status_code=404, detail="Data source not found")
    except HTTPException:
        raise
    except Exception as e:
        return BaseResponse(
            success=False,
            error=f"Failed to delete data source {datasource_id}: {str(e)}"
        )

@router.post("/api/v1/datasources/{datasource_id}/activate", response_model=BaseResponse, summary="Activate Data Source")
async def activate_datasource(datasource_id: int):
    """Activate a specific data source"""
    try:
        datasource = await get_datasource(datasource_id)
        if not datasource:
            raise HTTPException(status_code=404, detail="Data source not found")
        
        success = await set_active_datasource(datasource_id)
        if success:
            return BaseResponse(
                success=True,
                message=f"Data source {datasource_id} activated successfully"
            )
        else:
            return BaseResponse(
                success=False,
                error=f"Failed to activate data source {datasource_id}"
            )
    except HTTPException:
        raise
    except Exception as e:
        return BaseResponse(
            success=False,
            error=f"Failed to activate data source {datasource_id}: {str(e)}"
        )

@router.put("/api/v1/datasources/{datasource_id}/deactivate", response_model=BaseResponse, summary="Deactivate Data Source")
async def deactivate_datasource_api(datasource_id: int):
    """Deactivate a data source (sets Default as Active)"""
    try:
        datasource = await get_datasource(datasource_id)
        if not datasource:
            raise HTTPException(status_code=404, detail="Data source not found")
        
        # When deactivating, set the default datasource (ID=1) as active
        success = await set_active_datasource(1)  # Assuming default datasource has ID=1
        if success:
            return BaseResponse(
                success=True,
                message=f"Data source {datasource_id} deactivated, default datasource activated"
            )
        else:
            return BaseResponse(
                success=False,
                error=f"Failed to deactivate data source {datasource_id}"
            )
    except HTTPException:
        raise
    except Exception as e:
        return BaseResponse(
            success=False,
            error=f"Failed to deactivate data source {datasource_id}: {str(e)}"
        )

@router.post("/api/v1/datasources/{datasource_id}/files/upload", summary="Upload File to Data Source")
async def upload_file(
    datasource_id: int,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    """Upload a file to a specific data source"""
    try:
        # Verify data source exists
        datasource = await get_datasource(datasource_id)
        if not datasource:
            raise HTTPException(status_code=404, detail="Data source not found")

        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}{file_extension}"
        file_path = UPLOAD_DIR / unique_filename

        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)

        # Determine file type
        file_type_mapping = {
            '.pdf': FileType.PDF,
            '.docx': FileType.DOCX,
            '.doc': FileType.DOCX,
            '.csv': FileType.CSV,
            '.xlsx': FileType.XLSX,
            '.xls': FileType.XLSX,
            '.txt': FileType.TEXT
        }
        
        file_type = file_type_mapping.get(file_extension, FileType.UNKNOWN)
        
        # Save file information to database
        file_id = await save_file_info(
            filename=unique_filename,
            original_filename=file.filename,
            file_type=file_type.value,
            file_size=len(content),
            datasource_id=datasource_id
        )
        
        if file_id:
            # Process file in background if supported
            if file_type != FileType.UNKNOWN:
                try:
                    await process_uploaded_file(
                        file_id=file_id, 
                        datasource_id=datasource_id,
                        file_path=Path(str(file_path)), 
                        original_filename=file.filename,
                        file_type=file_type.value
                    )
                    await update_file_processing_status(file_id, ProcessingStatus.COMPLETED.value)
                except Exception as processing_error:
                    await update_file_processing_status(file_id, ProcessingStatus.FAILED.value)
                    print(f"File processing failed: {processing_error}")
            
            return {
                "success": True,
                "message": f"File '{file.filename}' uploaded successfully",
                "file_id": file_id,
                "filename": unique_filename,
                "processing_status": ProcessingStatus.COMPLETED.value if file_type != FileType.UNKNOWN else ProcessingStatus.PENDING.value
            }
        else:
            # Cleanup uploaded file if DB entry failed
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(status_code=500, detail="Failed to save file information to database.")

    except HTTPException:
        raise
    except Exception as e:
        # General error, attempt cleanup if file_path was defined
        if 'file_path' in locals() and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e_remove:
                print(f"Failed to remove partially uploaded file {file_path}: {e_remove}")
        return {"success": False, "error": f"File upload failed: {str(e)}"}

@router.get("/api/v1/datasources/{datasource_id}/files", response_model=FileListResponse, summary="Get Data Source File List")
async def get_datasource_files(datasource_id: int):
    """Get all files for a specific data source"""
    try:
        datasource = await get_datasource(datasource_id)
        if not datasource:
            raise HTTPException(status_code=404, detail="Data source not found")
        
        files = await get_files_by_datasource(datasource_id)
        file_list = [FileInfo(**file_data) for file_data in files]
        
        return FileListResponse(
            success=True,
            data=file_list,
            message=f"Retrieved {len(file_list)} files"
        )
    except HTTPException:
        raise
    except Exception as e:
        return FileListResponse(
            success=False,
            error=f"Failed to retrieve file list: {str(e)}",
            data=[]
        )

@router.delete("/api/v1/datasources/{datasource_id}/files/{file_id}", response_model=BaseResponse, summary="Delete File from Data Source")
async def delete_file_from_datasource(datasource_id: int, file_id: int):
    """Delete a specific file and its associated data from a data source."""
    try:
        success = await delete_file_record_and_associated_data(file_id)
        if success:
            return BaseResponse(success=True, message=f"File ID {file_id} and its associated data deleted successfully.")
        else:
            raise HTTPException(status_code=404, detail=f"Failed to delete File ID {file_id}. File may not exist or operation was not completed.")
    except HTTPException:
        raise
    except Exception as e:
        return BaseResponse(success=False, error=f"An internal server error occurred while deleting File ID {file_id}: {str(e)}")

# ==================== Intelligent Q&A API ====================

@router.post("/api/v1/query", response_model=Dict[str, Any], summary="Intelligent Q&A")
async def query_endpoint(request: QueryRequest):
    """
    Generic intelligent Q&A interface - query  data using natural language.
    
    Supported query types:
    - Sales data queries
    - Inventory status queries
    - Document/knowledge base queries
    - SQL table queries
    """
    try:
        intent = parse_query_intent(request.query)
        active_datasource_dict = await get_active_datasource()
        ds_id_for_response = active_datasource_dict['id'] if active_datasource_dict else 1
        
        query_type_for_agent = intent['type']
        # Default routing logic based on intent and datasource type
        if active_datasource_dict and active_datasource_dict['type'] != DataSourceType.DEFAULT.value:
            # If custom data source is active, prioritize RAG or SQL Agent based on its type
            if active_datasource_dict['type'] == DataSourceType.SQL_TABLE_FROM_FILE.value:
                query_type_for_agent = "sql_agent"
            else: # KNOWLEDGE_BASE or other future non-default types
                query_type_for_agent = "rag"
        elif intent['type'] not in ["sales", "inventory", "report"]:
             # If default  and intent is unclear, fallback to general  / sales
            query_type_for_agent = "sales"

        result = await get_answer_from(request.query, query_type_for_agent, active_datasource=active_datasource_dict)
        
        return create_api_response(
            success=True,
            query=request.query,
            query_type=result.get("query_type", intent['type']),
            intent=intent,
            answer=result.get("answer", "No answer could be generated."),
            data=result.get("data", {}),
            charts=result.get("chart_data"),
            suggestions=result.get("suggestions", []),
            datasource_id=ds_id_for_response,
            source_datasource_name=result.get("source_datasource_name", "Default ")
        )
        
    except Exception as e:
        return create_api_response(
            success=False,
            error=f"Query processing failed: {str(e)}",
            query=request.query,
            datasource_id=request.datasource_id if hasattr(request, 'datasource_id') else None
        )

# ==================== LangGraph Intelligent Analysis API ====================

async def process_query(query: str, datasource_id: int, execution_id: str) -> Dict[str, Any]:
    """Process an intelligent analysis query."""
    try:
        # Get the active datasource
        datasource = await get_active_datasource()
        if not datasource:
            raise HTTPException(status_code=404, detail="No active data source found. Please select or create a data source first.")
        
        # Check if the active datasource is properly configured for queries
        ds_type = datasource.get('type')
        ds_name = datasource.get('name', 'Unknown')
        
        # If it's a DEFAULT datasource without proper configuration, provide guidance
        if ds_type == DataSourceType.DEFAULT.value:
            # Default datasources should not be used for SQL queries anymore
            error_msg = (
                f"The active data source '{ds_name}' is a default data source that doesn't support queries. "
                "Please create a new data source by uploading CSV/Excel files for SQL queries or "
                "TXT/PDF/Word documents for knowledge-based queries, then activate it."
            )
            raise HTTPException(status_code=400, detail=error_msg)
        
        # For SQL_TABLE_FROM_FILE datasources, check if they have a proper table
        if ds_type == DataSourceType.SQL_TABLE_FROM_FILE.value and not datasource.get('db_table_name'):
            error_msg = (
                f"The active data source '{ds_name}' is configured for SQL queries but doesn't have "
                "an associated database table. Please upload a CSV or Excel file to this data source "
                "and wait for processing to complete."
            )
            raise HTTPException(status_code=400, detail=error_msg)
        
        # For HYBRID datasources, check if they have any processed files
        if ds_type == DataSourceType.HYBRID.value:
            # Get files for this datasource to check if any are completed
            from ..database.db_operations import get_files_by_datasource
            files = await get_files_by_datasource(datasource['id'])
            completed_files = [f for f in files if f['processing_status'] == 'completed']
            
            if not completed_files:
                error_msg = (
                    f"The active data source '{ds_name}' is a hybrid data source but doesn't have "
                    "any processed files. Please upload CSV/Excel files for SQL queries or "
                    "TXT/PDF/Word documents for knowledge-based queries, and wait for processing to complete."
                )
                raise HTTPException(status_code=400, detail=error_msg)
            
        # Run the analysis
        result = await process_intelligent_query(
            user_input=query,
            datasource=datasource,
            execution_id=execution_id
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error processing query: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/v1/intelligent-analysis")
async def intelligent_analysis(data: IntelligentAnalysisRequest):
    try:
        # Get the client ID from the request
        client_id = data.client_id
        
        # Create a new execution ID
        execution_id = str(uuid.uuid4())
        
        # Clean up previous execution for this client if it exists
        previous_execution = websocket_manager.get_client_execution(client_id)
        if previous_execution:
            # Instead of cleaning up immediately, mark it for cleanup
            websocket_manager.mark_for_cleanup(previous_execution)
        
        # Create new execution
        logger.info(f"Attempting to associate client {client_id} with execution {execution_id}")
        success = websocket_manager.associate_execution(client_id, execution_id)
        
        if not success:
            logger.warning(f"Failed to associate client {client_id} with execution {execution_id}")
            # Instead of failing, we'll retry the association after a short delay
            await asyncio.sleep(0.5)  # Give WebSocket time to reconnect
            success = websocket_manager.associate_execution(client_id, execution_id)
            if not success:
                logger.error(f"Failed to associate client {client_id} with execution {execution_id} after retry")
                return {"error": "Failed to establish WebSocket connection"}
        
        # Start the execution
        logger.info(f"Successfully associated client {client_id} with execution {execution_id}")
        
        # Process the query
        result = await process_query(data.query, data.datasource_id, execution_id)
        
        return {
            "execution_id": execution_id,
            "message": "Analysis completed successfully.",
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error processing intelligent analysis request: {str(e)}")
        return {"error": str(e)}

@router.websocket("/ws/workflow/{client_id}")
async def workflow_websocket(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time workflow tracking using client_id."""
    await websocket_manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Here you can handle client-side messages, e.g., pause, resume
            message = json.loads(data)
            execution_id = websocket_manager.client_to_execution.get(client_id)
            
            if not execution_id:
                logger.warning(f"Received message from client {client_id} before execution association.")
                continue

            if message.get("type") == "pause":
                websocket_manager.pause_execution(execution_id)
                await websocket_manager.broadcast_to_execution(
                    execution_id,
                    WorkflowEvent(type="execution_paused", execution_id=execution_id, timestamp=datetime.now().timestamp())
                )
            elif message.get("type") == "resume":
                websocket_manager.resume_execution(execution_id)
                await websocket_manager.broadcast_to_execution(
                    execution_id,
                    WorkflowEvent(type="execution_resumed", execution_id=execution_id, timestamp=datetime.now().timestamp())
                )
            elif message.get("type") == "cancel":
                websocket_manager.cancel_execution(execution_id)
                await websocket_manager.broadcast_to_execution(
                    execution_id,
                    WorkflowEvent(type="execution_cancelled", execution_id=execution_id, timestamp=datetime.now().timestamp())
                )
                
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket, client_id)
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        websocket_manager.disconnect(websocket, client_id)

# ==================== File Download API ====================

@router.get("/api/v1/download/resume", summary="Download Resume")
async def download_resume():
    """Download the author's resume file (PDF preferred, fallback to other formats)."""
    try:
        # Look for resume file in server/data/resume/ directory
        resume_dir = DATA_DIR / "resume"
        
        if not os.path.exists(resume_dir):
            logger.error(f"Resume directory not found: {resume_dir}")
            raise HTTPException(
                status_code=404,
                detail="Resume directory not found"
            )
        
        # Priority order: PDF first, then TXT, then any other file
        file_extensions = ['.pdf', '.txt', '.doc', '.docx']
        resume_file = None
        
        for ext in file_extensions:
            files = [f for f in os.listdir(resume_dir) if f.lower().endswith(ext.lower())]
            if files:
                resume_file = files[0]
                break
        
        if not resume_file:
            logger.error(f"No resume files found in directory: {resume_dir}")
            raise HTTPException(
                status_code=404,
                detail="Resume file not found. Please contact the author directly."
            )
        
        resume_path = os.path.join(resume_dir, resume_file)
        
        if not os.path.exists(resume_path):
            logger.error(f"Resume file not found at path: {resume_path}")
            raise HTTPException(
                status_code=404,
                detail="Resume file not found"
            )
        
        # Determine media type based on file extension
        file_ext = os.path.splitext(resume_file)[1].lower()
        media_type_map = {
            '.pdf': 'application/pdf',
            '.txt': 'text/plain',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }
        
        media_type = media_type_map.get(file_ext, 'application/octet-stream')
        download_filename = f"LiangLong_Resume{file_ext}"
        
        # Return the file
        return FileResponse(
            path=resume_path,
            filename=download_filename,
            media_type=media_type
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading resume: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ==================== Health and Info ======================
@router.get("/health", summary="Health Check")
async def health_check():
    return {"status": "OK"} 