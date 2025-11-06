from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, BackgroundTasks, WebSocket, WebSocketDisconnect, Request
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import os
import uuid
import aiofiles
from pathlib import Path
from ..models.data_models import (
    BaseResponse,
    DataSourceCreate, DataSourceUpdate, DataSource, DataSourceResponse, DataSourceListResponse,
    FileInfo, FileListResponse, ProcessingStatus, FileType, DataSourceType,
    WorkflowEvent,
    WorkflowEventType,
    NodeStatus,
)
from ..agents.intelligent_agent import (
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
    delete_file_record_and_associated_data,
    # HITL functions
    list_hitl_interrupts, get_hitl_interrupt, update_hitl_interrupt_status,
    create_hitl_execution_history, get_hitl_execution_history
)
from ..utils.common_utils import (
    create_api_response
)
from ..utils.rate_limiter import rate_limit
from ..document_loaders.file_processor import process_uploaded_file
from ..config.config import DATA_DIR
import json
import time
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

class IntelligentAnalysisRequest(BaseModel):
    """Request model for intelligent analysis endpoint"""
    query: str
    datasource_id: int
    client_id: str

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

        # Determine file type (only document types supported)
        file_type_mapping = {
            '.pdf': FileType.PDF,
            '.docx': FileType.DOCX,
            '.doc': FileType.DOCX,
            '.txt': FileType.TEXT,
            '.md': FileType.MD
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

@router.get("/api/v1/datasources/{datasource_id}/files/{file_id}/download", summary="Download File from Data Source")
async def download_file(datasource_id: int, file_id: int):
    """Download a file from a specific data source"""
    try:
        # Verify data source exists
        datasource = await get_datasource(datasource_id)
        if not datasource:
            raise HTTPException(status_code=404, detail="Data source not found")
        
        # Get file information from database
        files = await get_files_by_datasource(datasource_id)
        file_info = next((f for f in files if f['id'] == file_id), None)
        
        if not file_info:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Construct file path
        file_path = UPLOAD_DIR / file_info['filename']
        
        if not os.path.exists(file_path):
            logger.error(f"File not found at path: {file_path}")
            raise HTTPException(
                status_code=404,
                detail="File not found on server"
            )
        
        # Determine media type based on file extension
        file_ext = os.path.splitext(file_info['original_filename'])[1].lower()
        media_type_map = {
            '.pdf': 'application/pdf',
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.csv': 'text/csv',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel'
        }
        
        media_type = media_type_map.get(file_ext, 'application/octet-stream')
        
        # Return the file
        return FileResponse(
            path=str(file_path),
            filename=file_info['original_filename'],
            media_type=media_type
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")

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
        
        # If it's a DEFAULT datasource, use built-in ERP data
        if ds_type == DataSourceType.DEFAULT.value:
            # Built-in ERP datasource is always available for SQL queries
            pass
        # For KNOWLEDGE_BASE and HYBRID datasources, check if they have processed files
        elif ds_type in [DataSourceType.KNOWLEDGE_BASE.value, DataSourceType.HYBRID.value]:
            # Get files for this datasource to check if any are completed
            from ..database.db_operations import get_files_by_datasource
            files = await get_files_by_datasource(datasource['id'])
            completed_files = [f for f in files if f['processing_status'] == 'completed']
            
            if not completed_files:
                error_msg = (
                    f"The active data source '{ds_name}' is a document data source but doesn't have "
                    "any processed files. Please upload PDF, DOCX, or TXT documents and wait for processing to complete."
                )
                raise HTTPException(status_code=400, detail=error_msg)
        else:
            error_msg = (
                f"The active data source '{ds_name}' has an unsupported type '{ds_type}'. "
                "Please create a document data source (knowledge_base or hybrid) for document queries."
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
@rate_limit
async def intelligent_analysis(request: Request, data: IntelligentAnalysisRequest):
    logger.info(f"Intelligent analysis request - query: {data.query[:50]}..., datasource: {data.datasource_id}")
    
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
            
            try:
                message = json.loads(data)
                message_type = message.get("type")
                
                logger.info(f"Received WebSocket message from client {client_id}: type={message_type}, data={message}")
                
                # Handle HITL messages
                if message_type in ["hitl_pause", "hitl_interrupt", "hitl_resume", "hitl_cancel"]:
                    logger.info(f"Processing HITL message: {message_type} for client {client_id}")
                    await websocket_manager.handle_hitl_message(client_id, message)
                # Handle legacy ping-pong
                elif message_type == "ping":
                    await websocket_manager.send_to_client(client_id, {
                        "type": "pong",
                        "timestamp": time.time()
                    })
                else:
                    logger.warning(f"Unknown message type: {message_type}")
                    
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received from client {client_id}: {data}")
                await websocket_manager.send_to_client(client_id, {
                    "type": "error",
                    "message": "Invalid JSON format",
                    "timestamp": time.time()
                })
                
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

# ==================== HITL (Human-in-the-Loop) API ======================

@router.get("/api/v1/hitl/interrupts", summary="Get HITL Interrupt History")
async def get_hitl_interrupts(
    status: Optional[str] = Query(None, description="Filter by status (interrupted, cancelled, restored)"),
    limit: int = Query(100, description="Maximum number of records to return")
):
    """Get list of HITL interrupts for history restoration"""
    try:
        interrupts = list_hitl_interrupts(status=status, limit=limit)
        
        # Format the response for frontend
        formatted_interrupts = []
        for interrupt in interrupts:
            formatted_interrupts.append({
                "id": interrupt["id"],
                "execution_id": interrupt["execution_id"],
                "user_input": interrupt["user_input"],
                "datasource_id": interrupt["datasource_id"],
                "node_name": interrupt["node_name"],
                "interrupted_at": interrupt["interrupted_at"],
                "status": interrupt["status"],
                "reason": interrupt["reason"],
                "state_data": interrupt["state_data"] if interrupt["state_data"] else None
            })
        
        return create_api_response(
            success=True,
            data={"interrupts": formatted_interrupts},
            message=f"Retrieved {len(formatted_interrupts)} interrupt records"
        )
        
    except Exception as e:
        logger.error(f"Error getting HITL interrupts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get interrupt history: {str(e)}")

@router.get("/api/v1/hitl/interrupts/{execution_id}", summary="Get Specific HITL Interrupt")
async def get_hitl_interrupt(execution_id: str):
    """Get specific HITL interrupt by execution ID"""
    try:
        interrupt = get_hitl_interrupt(execution_id)
        
        if not interrupt:
            raise HTTPException(status_code=404, detail="Interrupt not found")
        
        return create_api_response(
            success=True,
            data={
                "id": interrupt["id"],
                "execution_id": interrupt["execution_id"],
                "user_input": interrupt["user_input"],
                "datasource_id": interrupt["datasource_id"],
                "node_name": interrupt["node_name"],
                "interrupted_at": interrupt["interrupted_at"],
                "status": interrupt["status"],
                "reason": interrupt["reason"],
                "state_data": interrupt["state_data"] if interrupt["state_data"] else None
            },
            message="Interrupt retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting HITL interrupt {execution_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get interrupt: {str(e)}")

@router.put("/api/v1/hitl/interrupts/{execution_id}/status", summary="Update HITL Interrupt Status")
async def update_interrupt_status(execution_id: str, status: str):
    """Update the status of an HITL interrupt"""
    try:
        success = update_hitl_interrupt_status(execution_id, status)
        
        if not success:
            raise HTTPException(status_code=404, detail="Interrupt not found or update failed")
        
        return create_api_response(
            success=True,
            data={"execution_id": execution_id, "status": status},
            message="Interrupt status updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating interrupt status for {execution_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update interrupt status: {str(e)}")

@router.post("/api/v1/hitl/interrupts/{execution_id}/restore", summary="Restore HITL Interrupt")
async def restore_interrupt(execution_id: str):
    """Restore an interrupted execution"""
    try:
        # Get the interrupt record
        interrupt = get_hitl_interrupt(execution_id)
        
        if not interrupt:
            raise HTTPException(status_code=404, detail="Interrupt not found")
        
        if interrupt["status"] != "interrupted":
            raise HTTPException(status_code=400, detail="Interrupt is not in interrupted status")
        
        # Update status to restored
        success = update_hitl_interrupt_status(execution_id, "restored")
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update interrupt status")
        
        # Create execution history record
        create_hitl_execution_history(
            execution_id=execution_id,
            operation_type="restore",
            node_name=interrupt["node_name"],
            user_action="restore_from_history"
        )
        
        return create_api_response(
            success=True,
            data={
                "execution_id": execution_id,
                "status": "restored",
                "node_name": interrupt["node_name"],
                "user_input": interrupt["user_input"]
            },
            message="Interrupt restored successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring interrupt {execution_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to restore interrupt: {str(e)}")

@router.post("/api/v1/hitl/interrupts/{execution_id}/cancel", summary="Cancel HITL Interrupt")
async def cancel_interrupt(execution_id: str):
    """Cancel an interrupted execution"""
    try:
        # Get the interrupt record
        interrupt = get_hitl_interrupt(execution_id)
        
        if not interrupt:
            raise HTTPException(status_code=404, detail="Interrupt not found")
        
        if interrupt["status"] != "interrupted":
            raise HTTPException(status_code=400, detail="Interrupt is not in interrupted status")
        
        # Update status to cancelled
        success = update_hitl_interrupt_status(execution_id, "cancelled")
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update interrupt status")
        
        # Create execution history record
        create_hitl_execution_history(
            execution_id=execution_id,
            operation_type="cancel",
            node_name=interrupt["node_name"],
            user_action="cancel_from_history"
        )
        
        return create_api_response(
            success=True,
            data={
                "execution_id": execution_id,
                "status": "cancelled",
                "node_name": interrupt["node_name"]
            },
            message="Interrupt cancelled successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling interrupt {execution_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel interrupt: {str(e)}")

# ==================== Health and Info ======================
@router.get("/health", summary="Health Check")
async def health_check():
    return {"status": "OK"} 