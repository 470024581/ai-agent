import asyncio
from pathlib import Path
from typing import Optional
from ..database.db_operations import update_file_processing_status, get_datasource
from ..models.data_models import ProcessingStatus, DataSourceType, FileType
import logging

logger = logging.getLogger(__name__)

async def process_uploaded_file(
    file_id: int, 
    datasource_id: int, 
    file_path: Path, 
    original_filename: str, 
    file_type: str 
):
    """
    Background task to process uploaded files for RAG (document knowledge base).
    Only supports PDF, DOCX, and TXT files for document processing.
    """
    logger.info(f"[FileProcessor] Starting processing for file ID: {file_id}, DS_ID: {datasource_id}, Name: {original_filename}")

    datasource_details = await get_datasource(datasource_id)
    if not datasource_details:
        logger.error(f"[FileProcessor] Datasource {datasource_id} not found. Cannot process file {file_id}.")
        await update_file_processing_status(file_id, status=ProcessingStatus.FAILED.value, error_message="Associated datasource not found.")
        return

    ds_type = datasource_details.get('type')

    try:
        await update_file_processing_status(file_id, status=ProcessingStatus.PROCESSING.value)
        logger.info(f"[FileProcessor] File ID: {file_id} - Status set to PROCESSING. Datasource type: {ds_type}")

        # Only process document files for KNOWLEDGE_BASE and HYBRID data sources
        if ds_type in [DataSourceType.KNOWLEDGE_BASE.value, DataSourceType.HYBRID.value] and file_type.lower() in [FileType.PDF.value, FileType.DOCX.value, FileType.TEXT.value]:
            
            logger.info(f"[FileProcessor] Processing '{file_type}' file '{original_filename}' for document knowledge base (DS type: {ds_type}).")
            
            # Simulate document processing (text extraction and chunking)
            # In a real implementation, this would:
            # 1. Extract text from PDF/DOCX/TXT files
            # 2. Split text into chunks
            # 3. Generate embeddings
            # 4. Store in vector database
            
            # For now, simulate processing time
            await asyncio.sleep(2)
            
            # Update processing status to completed (compat without processed_chunks kw)
            try:
                await update_file_processing_status(file_id, status=ProcessingStatus.COMPLETED.value, processed_chunks=10)
            except TypeError:
                await update_file_processing_status(file_id, status=ProcessingStatus.COMPLETED.value)
            logger.info(f"[FileProcessor] File ID: {file_id} - Document processing completed successfully.")
            
        else:
            # Unsupported file type or datasource type
            error_msg = f"File type '{file_type}' is not supported for datasource type '{ds_type}'. Only PDF, DOCX, and TXT files are supported for document processing."
            logger.warning(f"[FileProcessor] {error_msg}")
            await update_file_processing_status(file_id, status=ProcessingStatus.FAILED.value, error_message=error_msg)

    except Exception as e:
        logger.error(f"[FileProcessor] Error processing file ID: {file_id}, Error: {e}", exc_info=True)
        await update_file_processing_status(file_id, status=ProcessingStatus.FAILED.value, error_message=str(e))