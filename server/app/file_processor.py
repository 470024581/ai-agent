import asyncio
from pathlib import Path
import pandas as pd
import re # For sanitizing column names
import uuid # For unique table name suffix
from typing import Optional
from .db import update_file_processing_status, get_datasource, set_datasource_table_name, get_db_connection, add_table_to_datasource, get_datasource_tables
from .models import ProcessingStatus, DataSourceType, FileType # Ensure enums are available
import logging

logger = logging.getLogger(__name__)

def sanitize_column_name(col_name: str) -> str:
    """Converts a column name to a safe SQL column name."""
    # Remove or replace illegal characters, e.g., spaces, special symbols.
    # Convert to lowercase, replace spaces with underscores.
    col_name = str(col_name).lower()
    col_name = re.sub(r'\s+', '_', col_name) # Replace spaces with underscores
    col_name = re.sub(r'[^a-z0-9_]', '', col_name) # Remove non-alphanumeric (excluding underscore)
    if not col_name: # If empty after processing (e.g., original name was all special chars)
        col_name = "column_" + uuid.uuid4().hex[:6]
    elif col_name[0].isdigit(): # If starts with a digit, add a prefix
        col_name = "col_" + col_name
    return col_name

async def _create_table_from_df(conn, table_name: str, df: pd.DataFrame):
    """Dynamically creates an SQLite table based on DataFrame columns."""
    sanitized_columns = {col: sanitize_column_name(col) for col in df.columns}
    df_renamed = df.rename(columns=sanitized_columns)
    
    # Simplified SQLite type inference: TEXT for all, or basic inference.
    # For more robust type inference, one might inspect df.dtypes.
    # A more advanced version could map pandas dtypes to SQLite types.
    cols_with_types = ", ".join([f'"{col_name}" TEXT' for col_name in df_renamed.columns])
    
    create_table_sql = f"CREATE TABLE IF NOT EXISTS \"{table_name}\" ({cols_with_types})"
    logger.info(f"Executing SQL to create table: {create_table_sql}")
    
    cursor = conn.cursor()
    cursor.execute(create_table_sql)
    conn.commit()
    return df_renamed # Return dataframe with sanitized column names

async def _insert_df_to_table(conn, table_name: str, df_renamed: pd.DataFrame):
    """Inserts DataFrame data into the specified SQLite table."""
    logger.info(f"Inserting {len(df_renamed)} rows into table '{table_name}'")
    
    cols = df_renamed.columns
    placeholders = ", ".join(["?" for _ in cols])
    formatted_column_names = [f'"{c}"' for c in cols]
    columns_sql_string = ", ".join(formatted_column_names)
    insert_sql = f"INSERT INTO \"{table_name}\" ({columns_sql_string}) VALUES ({placeholders})"
    
    cursor = conn.cursor()
    try:
        data_to_insert = [tuple(row) for row in df_renamed.itertuples(index=False, name=None)]
        cursor.executemany(insert_sql, data_to_insert)
        conn.commit()
        logger.info(f"Successfully inserted {len(data_to_insert)} rows into '{table_name}'.")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error inserting data into '{table_name}': {e}", exc_info=True)
        raise

async def process_uploaded_file(
    file_id: int, 
    datasource_id: int, 
    file_path: Path, 
    original_filename: str, 
    file_type: str 
):
    """
    Background task to process uploaded files.
    - If data source type is SQL_TABLE_FROM_FILE and file is CSV/XLSX, parse and store in a new table.
    - If data source type is HYBRID:
      - CSV/XLSX files -> SQL table processing
      - TXT/PDF/DOCX files -> RAG processing (knowledge base)
    - Other cases (e.g., knowledge base files) currently simulate processing and update status.
    """
    logger.info(f"[FileProcessor] Starting processing for file ID: {file_id}, DS_ID: {datasource_id}, Name: {original_filename}")

    datasource_details = await get_datasource(datasource_id)
    if not datasource_details:
        logger.error(f"[FileProcessor] Datasource {datasource_id} not found. Cannot process file {file_id}.")
        await update_file_processing_status(file_id, status=ProcessingStatus.FAILED.value, error_message="Associated datasource not found.")
        return

    ds_type = datasource_details.get('type')
    conn = None

    try:
        await update_file_processing_status(file_id, status=ProcessingStatus.PROCESSING.value)
        logger.info(f"[FileProcessor] File ID: {file_id} - Status set to PROCESSING. Datasource type: {ds_type}")

        # Handle SQL table processing for SQL_TABLE_FROM_FILE and HYBRID data sources
        if ((ds_type == DataSourceType.SQL_TABLE_FROM_FILE.value) or 
            (ds_type == DataSourceType.HYBRID.value)) and file_type.lower() in [FileType.CSV.value, FileType.XLSX.value]:
            
            logger.info(f"[FileProcessor] Processing '{file_type}' file '{original_filename}' for SQL table ingestion (DS type: {ds_type}).")
            
            if not file_path.exists():
                logger.error(f"[FileProcessor] File not found at path: {file_path}. Cannot ingest.")
                raise FileNotFoundError(f"Source file {original_filename} not found at {file_path}")

            df = None
            if file_type.lower() == FileType.CSV.value:
                df = pd.read_csv(file_path, on_bad_lines='skip')
            elif file_type.lower() == FileType.XLSX.value:
                xls = pd.ExcelFile(file_path)
                if xls.sheet_names:
                    df = xls.parse(xls.sheet_names[0])
                else:
                    raise ValueError("Excel file contains no sheets.")
            
            if df is None or df.empty:
                logger.warning(f"[FileProcessor] DataFrame is empty for file {original_filename}. No data to ingest.")
                await update_file_processing_status(file_id, status=ProcessingStatus.COMPLETED.value, chunks=0, error_message="File was empty or unreadable as table.")
                return

            conn = get_db_connection()
            
            # Check if there's an existing table with the same structure
            existing_table = await _find_compatible_table(conn, datasource_id, df)
            
            if existing_table:
                # Append to existing table
                logger.info(f"[FileProcessor] Found compatible table '{existing_table}', appending data")
                df_renamed = await _prepare_df_for_existing_table(conn, existing_table, df)
                await _insert_df_to_table(conn, existing_table, df_renamed)
                table_name = existing_table
            else:
                # Create new table
                base_name = Path(original_filename).stem
                unique_suffix = uuid.uuid4().hex[:8]
                sane_base_name = re.sub(r'\W|\s', '_', base_name)
                table_name = f"dstable_{datasource_id}_{sane_base_name}_{unique_suffix}" 
                table_name = table_name[:60]
                logger.info(f"[FileProcessor] Creating new table: {table_name}")
                
                df_renamed = await _create_table_from_df(conn, table_name, df)
                await _insert_df_to_table(conn, table_name, df_renamed)
            
            # Add table to datasource (support multiple tables per datasource)
            await add_table_to_datasource(datasource_id, table_name)
            logger.info(f"[FileProcessor] Successfully linked table '{table_name}' to datasource {datasource_id}")
            
            await update_file_processing_status(file_id, status=ProcessingStatus.COMPLETED.value, chunks=len(df))
            logger.info(f"[FileProcessor] File ID: {file_id} - SQL table ingestion COMPLETED. Rows: {len(df)}")

        # Handle RAG processing for KNOWLEDGE_BASE and HYBRID data sources
        elif ((ds_type == DataSourceType.KNOWLEDGE_BASE.value) or 
              (ds_type == DataSourceType.HYBRID.value and file_type.lower() in [FileType.TXT.value, FileType.TEXT.value, FileType.PDF.value, FileType.DOCX.value])):
            
            logger.info(f"[FileProcessor] Processing '{file_type}' file '{original_filename}' for RAG/knowledge base (DS type: {ds_type}).")
            await _process_for_rag(file_id, file_path, original_filename, file_type)

        else:
            # For other data source types or unsupported file types in HYBRID mode
            if ds_type == DataSourceType.HYBRID.value:
                logger.warning(f"[FileProcessor] File ID: {file_id} - Unsupported file type '{file_type}' for HYBRID data source. Expected CSV/XLSX for SQL or TXT/PDF/DOCX for RAG.")
                await update_file_processing_status(file_id, status=ProcessingStatus.FAILED.value, 
                                                  error_message=f"Unsupported file type '{file_type}' for hybrid data source. Use CSV/XLSX for SQL processing or TXT/PDF/DOCX for RAG processing.")
                return
            else:
                # For other data source types, use placeholder processing
                logger.info(f"[FileProcessor] File ID: {file_id} - Using placeholder processing for DS type: {ds_type}")
                await asyncio.sleep(3)  # Simulate processing
                processed_chunks_count = 10  # Placeholder
                await update_file_processing_status(file_id, status=ProcessingStatus.COMPLETED.value, chunks=processed_chunks_count)
                logger.info(f"[FileProcessor] File ID: {file_id} - Placeholder processing COMPLETED.")

    except Exception as e:
        logger.error(f"[FileProcessor] Error processing file ID: {file_id}, Name: {original_filename}. Error: {str(e)}", exc_info=True)
        await update_file_processing_status(file_id, status=ProcessingStatus.FAILED.value, error_message=str(e))
    finally:
        if conn:
            conn.close()
        logger.info(f"[FileProcessor] Finished processing attempt for file ID: {file_id}, Name: {original_filename}")

async def _process_for_rag(file_id: int, file_path: Path, original_filename: str, file_type: str):
    """
    Process files for RAG (Retrieval-Augmented Generation) pipeline.
    This function handles text extraction, chunking, and embedding creation for knowledge base.
    """
    try:
        logger.info(f"[RAG Processor] Starting RAG processing for file ID: {file_id}, type: {file_type}")
        
        if not file_path.exists():
            logger.error(f"[RAG Processor] File not found at path: {file_path}")
            raise FileNotFoundError(f"Source file {original_filename} not found at {file_path}")
        
        # Get file size for processing estimation
        file_size = file_path.stat().st_size
        
        # Extract text based on file type
        extracted_text = ""
        
        if file_type.lower() in [FileType.TXT.value, FileType.TEXT.value]:
            # Process text files
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                extracted_text = f.read()
            logger.info(f"[RAG Processor] Extracted {len(extracted_text)} characters from TXT file")
            
        elif file_type.lower() == FileType.PDF.value:
            # PDF processing requires additional dependencies
            logger.error(f"[RAG Processor] PDF processing not implemented. Please install required libraries (PyPDF2, pdfplumber, or pymupdf)")
            raise NotImplementedError("PDF processing requires additional dependencies. Please install PyPDF2, pdfplumber, or pymupdf")
            
        elif file_type.lower() == FileType.DOCX.value:
            # DOCX processing requires additional dependencies
            logger.error(f"[RAG Processor] DOCX processing not implemented. Please install python-docx library")
            raise NotImplementedError("DOCX processing requires python-docx library")
            
        else:
            raise ValueError(f"Unsupported file type for RAG processing: {file_type}")
        
        # Chunk the text for RAG processing
        chunks = _chunk_text_for_rag(extracted_text, chunk_size=1000, overlap=200)
        logger.info(f"[RAG Processor] Created {len(chunks)} text chunks")
        
        # Simulate embedding creation and storage
        # In a real implementation, this would:
        # 1. Generate embeddings using a model like sentence-transformers
        # 2. Store chunks and embeddings in a vector database (e.g., Chroma, Pinecone, FAISS)
        # 3. Create metadata for retrieval
        
        processing_time = min(15, max(3, len(chunks) * 0.1))  # Simulate processing time
        await asyncio.sleep(processing_time)
        
        # Update processing status
        await update_file_processing_status(file_id, status=ProcessingStatus.COMPLETED.value, chunks=len(chunks))
        logger.info(f"[RAG Processor] RAG processing COMPLETED for file ID: {file_id}. Chunks: {len(chunks)}")
        
    except Exception as e:
        logger.error(f"[RAG Processor] Error in RAG processing for file ID: {file_id}. Error: {str(e)}")
        await update_file_processing_status(file_id, status=ProcessingStatus.FAILED.value, error_message=str(e))
        raise

def _chunk_text_for_rag(text: str, chunk_size: int = 1000, overlap: int = 200) -> list:
    """
    Split text into overlapping chunks for RAG processing.
    
    Args:
        text: Input text to chunk
        chunk_size: Target size of each chunk in characters
        overlap: Number of characters to overlap between chunks
    
    Returns:
        List of text chunks
    """
    if not text or len(text) <= chunk_size:
        return [text] if text else []
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Try to break at sentence boundaries
        if end < len(text):
            # Look for sentence endings near the chunk boundary
            for i in range(end, max(start + chunk_size // 2, end - 100), -1):
                if text[i] in '.!?':
                    end = i + 1
                    break
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # Move start position with overlap
        start = end - overlap if end < len(text) else len(text)
    
    return chunks

# Additional helper functions for real implementations:
# async def extract_pdf_text(file_path: Path) -> str:
#     """Extract text from PDF using PyPDF2 or similar library"""
#     pass
# 
# async def extract_docx_text(file_path: Path) -> str:
#     """Extract text from DOCX using python-docx library"""
#     pass
# 
# async def create_embeddings(chunks: List[str]) -> List[List[float]]:
#     """Create embeddings for text chunks using sentence-transformers or similar"""
#     pass
# 
# async def store_in_vector_db(chunks: List[str], embeddings: List[List[float]], metadata: dict):
#     """Store chunks and embeddings in vector database"""
#     pass
# async def generate_embeddings(chunks: List[str]) -> List[List[float]]: ...
# async def store_vector_chunks(file_id: int, chunks: List[str], embeddings: List[List[float]]): ...

async def _find_compatible_table(conn, datasource_id: int, df: pd.DataFrame) -> Optional[str]:
    """Find an existing table with compatible structure for the given DataFrame."""
    try:
        # Get all tables for this datasource
        from .db import get_datasource_tables
        tables = await get_datasource_tables(datasource_id)
        
        if not tables:
            return None
            
        # Check each table for compatibility
        for table_name in tables:
            if await _is_table_compatible(conn, table_name, df):
                return table_name
                
        return None
        
    except Exception as e:
        logger.error(f"[FileProcessor] Error finding compatible table: {str(e)}")
        return None

async def _is_table_compatible(conn, table_name: str, df: pd.DataFrame) -> bool:
    """Check if a table has compatible structure with the DataFrame."""
    try:
        cursor = conn.cursor()
        
        # Get table schema
        cursor.execute(f"PRAGMA table_info({table_name})")
        table_columns = cursor.fetchall()
        
        if not table_columns:
            return False
            
        # Extract column names from table (excluding potential id column)
        table_col_names = set()
        for col in table_columns:
            col_name = col[1]  # column name is at index 1
            if col_name.lower() != 'id':  # Skip auto-generated ID columns
                table_col_names.add(col_name.lower())
        
        # Get DataFrame column names (sanitized)
        df_col_names = set()
        for col in df.columns:
            sanitized_col = sanitize_column_name(col).lower()
            df_col_names.add(sanitized_col)
        
        # Check if column sets match
        return table_col_names == df_col_names
        
    except Exception as e:
        logger.error(f"[FileProcessor] Error checking table compatibility: {str(e)}")
        return False

async def _prepare_df_for_existing_table(conn, table_name: str, df: pd.DataFrame) -> pd.DataFrame:
    """Prepare DataFrame to match existing table structure."""
    try:
        cursor = conn.cursor()
        
        # Get table schema to determine column order
        cursor.execute(f"PRAGMA table_info({table_name})")
        table_columns = cursor.fetchall()
        
        # Extract column names in table order (excluding id column)
        table_col_order = []
        for col in table_columns:
            col_name = col[1]  # column name is at index 1
            if col_name.lower() != 'id':  # Skip auto-generated ID columns
                table_col_order.append(col_name)
        
        # Rename DataFrame columns to match table
        df_renamed = df.copy()
        
        # Create mapping from sanitized names to table column names
        col_mapping = {}
        for original_col in df.columns:
            sanitized_col = sanitize_column_name(original_col)
            # Find matching table column
            for table_col in table_col_order:
                if table_col.lower() == sanitized_col.lower():
                    col_mapping[original_col] = table_col
                    break
        
        # Rename columns
        df_renamed = df_renamed.rename(columns=col_mapping)
        
        # Reorder columns to match table
        df_renamed = df_renamed[table_col_order]
        
        return df_renamed
        
    except Exception as e:
        logger.error(f"[FileProcessor] Error preparing DataFrame for existing table: {str(e)}")
        raise 