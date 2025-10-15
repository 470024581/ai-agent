import os
from typing import Optional, List, Dict, Any, Union
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain.agents import AgentType
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain.docstore.document import Document
from ..database.db_operations import (
    initialize_database,  # Changed: initialize_app_database -> initialize_database
    get_files_by_datasource, # Added to get files for RAG
    get_active_datasource, # Added to get active datasource
    DATABASE_PATH # Import DATABASE_PATH
)
from ..models.data_models import DataSourceType # Import DataSourceType
from dotenv import load_dotenv
from pathlib import Path # Added Path
import logging # Added logging
import pandas as pd # Added pandas
import re
import asyncio
from ..config.config import Config
# Factory imports
from ..models.llm_factory import get_llm, get_reasoning_llm, get_llm_status, reset_llm
from ..models.embedding_factory import get_embeddings, get_embeddings_status, reset_embeddings
# Imports for file parsing
import PyPDF2
from docx import Document as DocxDocument


# Defer logging configuration to centralized start.py
logger = logging.getLogger(__name__)

# Import for local embeddings
# from langchain_community.embeddings import SentenceTransformerEmbeddings # Already imported above

load_dotenv()


# Determine the correct upload directory relative to this file (agent.py)
# Assuming agent.py is in server/app/ and uploads are in server/data/uploads/
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
DB_URI = f"sqlite:///{DATABASE_PATH}" # Construct DB URI for LangChain

llm = None
embeddings = None # Initialize embeddings variable


# Helper functions for parsing files
def _extract_text_from_pdf(file_path: Path) -> str:
    logger.info(f"Extracting text from PDF: {file_path}")
    text = ""
    try:
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                text += page.extract_text() or ""
        logger.info(f"Successfully extracted {len(text)} characters from PDF: {file_path}")
    except Exception as e:
        logger.error(f"Error extracting text from PDF {file_path}: {e}", exc_info=True)
    return text

def _extract_text_from_docx(file_path: Path) -> str:
    logger.info(f"Extracting text from DOCX: {file_path}")
    text = ""
    try:
        doc = DocxDocument(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
        logger.info(f"Successfully extracted {len(text)} characters from DOCX: {file_path}")
    except Exception as e:
        logger.error(f"Error extracting text from DOCX {file_path}: {e}", exc_info=True)
    return text

def _extract_text_from_csv_pandas(file_path: Path) -> str:
    logger.info(f"Extracting text from CSV using pandas: {file_path}")
    text = ""
    try:
        df = pd.read_csv(file_path, on_bad_lines='skip')
        # Convert each row to a string, then join all row strings
        # We include column names for context for each row, and join with a clear separator.
        # For example: "column1: value1, column2: value2, ..."
        row_texts = []
        for index, row in df.iterrows():
            row_text = ", ".join([f"{col}: {str(val)}" for col, val in row.astype(str).items()])
            row_texts.append(row_text)
        text = "\n".join(row_texts) # Each original row becomes a line in the text document
        logger.info(f"Successfully extracted text from CSV {file_path}. Total characters: {len(text)}")
    except Exception as e:
        logger.error(f"Error extracting text from CSV {file_path} with pandas: {e}", exc_info=True)
    return text

def _extract_text_from_xlsx_pandas(file_path: Path) -> str:
    logger.info(f"Extracting text from XLSX using pandas: {file_path}")
    text = ""
    try:
        xls = pd.ExcelFile(file_path)
        sheet_texts = []
        for sheet_name in xls.sheet_names:
            df = xls.parse(sheet_name)
            # Convert each row to a string, then join all row strings for this sheet
            row_texts = []
            for index, row in df.iterrows():
                row_text = ", ".join([f"{col}: {str(val)}" for col, val in row.astype(str).items()])
                row_texts.append(row_text)
            sheet_texts.append(f"Sheet: {sheet_name}\n" + "\n".join(row_texts))
        text = "\n\n".join(sheet_texts) # Separate sheets by a double newline
        logger.info(f"Successfully extracted text from XLSX {file_path}. Total characters: {len(text)}")
    except Exception as e:
        logger.error(f"Error extracting text from XLSX {file_path} with pandas: {e}", exc_info=True)
    return text

# Initialize LLM using factory (strict mode - no simulation)
try:
    llm = get_llm()
    llm_status = get_llm_status()
    logger.info(f"LLM initialized successfully - Provider: {llm_status.get('provider')}, Model: {llm_status.get('model')}")
    if llm_status.get('base_url'):
        logger.info(f"Using API endpoint: {llm_status.get('base_url')}")
except Exception as e:
    logger.error(f"LLM initialization failed: {e}")
    
    # Check if it's a Bedrock SSO issue and try to refresh
    if "bedrock" in str(e).lower() and "sso" in str(e).lower():
        logger.warning("Detected Bedrock SSO issue, attempting automatic refresh...")
        try:
            from ..models.llm_factory import refresh_sso_token
            from ..config.config import Config
            
            if Config.ENABLE_AUTO_SSO_REFRESH:
                profile = Config.AWS_PROFILE or "DevOpsPermissionSet-412381743093"
                if refresh_sso_token(profile):
                    logger.info("SSO refreshed, retrying LLM initialization...")
                    llm = get_llm()
                    llm_status = get_llm_status()
                    logger.info(f"LLM initialized successfully after SSO refresh - Provider: {llm_status.get('provider')}, Model: {llm_status.get('model')}")
                else:
                    logger.error("SSO refresh failed, LLM initialization aborted")
                    llm = None
            else:
                logger.error("Auto-SSO refresh is disabled")
                llm = None
        except Exception as sso_error:
            logger.error(f"SSO refresh attempt failed: {sso_error}")
            llm = None
    else:
        logger.error("Please check your LLM configuration in .env file")
        llm = None

# Initialize Embeddings using factory
try:
    logger.info("Starting initialization of embedding model using factory...")
    embeddings = get_embeddings()
    embedding_status = get_embeddings_status()
    logger.info(f"Embedding model initialized successfully - Provider: {embedding_status.get('provider')}, Model: {embedding_status.get('model')}")
except Exception as e:
    logger.error(f"Embedding model initialization failed: {e}", exc_info=True)
    
    # Check if it's a Bedrock SSO issue and try to refresh
    if "bedrock" in str(e).lower() and "sso" in str(e).lower():
        logger.warning("Detected Bedrock SSO issue for embeddings, attempting automatic refresh...")
        try:
            from ..models.llm_factory import refresh_sso_token
            from ..config.config import Config
            
            if Config.ENABLE_AUTO_SSO_REFRESH:
                profile = Config.AWS_PROFILE or "DevOpsPermissionSet-412381743093"
                if refresh_sso_token(profile):
                    logger.info("SSO refreshed, retrying embedding initialization...")
                    embeddings = get_embeddings()
                    embedding_status = get_embeddings_status()
                    logger.info(f"Embedding model initialized successfully after SSO refresh - Provider: {embedding_status.get('provider')}, Model: {embedding_status.get('model')}")
                else:
                    logger.error("SSO refresh failed, embedding initialization aborted")
                    embeddings = None
            else:
                logger.error("Auto-SSO refresh is disabled")
                embeddings = None
        except Exception as sso_error:
            logger.error(f"SSO refresh attempt failed: {sso_error}")
            embeddings = None
    else:
        embeddings = None

async def perform_rag_query(query: str, datasource: Dict[str, Any]) -> Dict[str, Any]:
    """
    Performs RAG retrieval and Q&A for the specified data source.
    """
    logger.info(f"Attempting RAG query on datasource: {datasource['name']} (ID: {datasource['id']}) for query: '{query}'")

    if not llm:
        raise RuntimeError("LLM not initialized. RAG query cannot be processed without LLM.")
    
    if not embeddings:
        logger.error("Local embedding model not initialized. RAG query cannot perform vectorization and retrieval.")
        return {
            "query": query, "query_type": "rag", "success": False,
            "answer": "RAG functionality cannot be executed because a dependent component is not initialized. Please check API keys and configuration.",
            "data": {"source_datasource_id": datasource['id'], "source_datasource_name": datasource['name']},
            "error": "Local embeddings not initialized."
        }
    
    try:
        # 1. Fetch list of 'completed' files from the database
        datasource_id = datasource['id']
        logger.info(f"Fetching completed files for datasource_id: {datasource_id}")
        db_files = await get_files_by_datasource(datasource_id)
        
        completed_files = [f for f in db_files if f['processing_status'] == 'completed']
        logger.info(f"Found {len(completed_files)} completed files for datasource {datasource_id}.")

        if not completed_files:
            return {
                "query": query, "query_type": "rag", "success": True, # Success=True as it's a valid state
                "answer": f"No successfully processed files available for query in data source '{datasource['name']}'. Please upload files and wait for processing to complete.",
                "data": {"source_datasource_id": datasource['id'], "source_datasource_name": datasource['name'], "retrieved_documents": []}
            }

        all_docs = []
        # 2. Load and parse file content
        for file_info in completed_files:
            file_path = UPLOAD_DIR / file_info['filename']
            text_content = ""
            file_type = file_info['file_type']
            original_filename = file_info['original_filename']

            logger.info(f"Processing file: {file_path} (Original: {original_filename}, Type: {file_type})")

            if not file_path.exists():
                logger.warning(f"File not found: {file_path} for file_info: {original_filename}")
                continue
            
            try:
                if file_type == 'txt':
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text_content = f.read()
                elif file_type == 'pdf':
                    text_content = _extract_text_from_pdf(file_path)
                elif file_type == 'docx':
                    text_content = _extract_text_from_docx(file_path)
                # Add other file types like CSV, XLSX later
                elif file_type == 'csv':
                    text_content = _extract_text_from_csv_pandas(file_path)
                elif file_type == 'xlsx':
                    text_content = _extract_text_from_xlsx_pandas(file_path)
                else:
                    logger.info(f"Skipping file {original_filename} due to unsupported file type: {file_type}")
                    continue
                
                if text_content.strip():
                    doc = Document(page_content=text_content, metadata={"source": original_filename, "file_id": file_info['id']})
                    all_docs.append(doc)
                    logger.info(f"Successfully processed and created Document for {original_filename}. Length: {len(text_content)}")
                else:
                    logger.warning(f"No text content extracted from {original_filename} (Type: {file_type})")

            except Exception as e:
                logger.error(f"Error processing file {original_filename}: {e}", exc_info=True)
                # Optionally, update file status to 'failed' here if processing fails at this stage
                # await update_file_processing_status(file_info['id'], status=ProcessingStatus.FAILED.value, error_message=f"Content extraction failed: {str(e)}")

        if not all_docs:
             return {
                "query": query, "query_type": "rag", "success": True,
                "answer": f"No processable (TXT, PDF, DOCX, CSV, XLSX) file content found in data source '{datasource['name']}'.",
                "data": {"source_datasource_id": datasource['id'], "source_datasource_name": datasource['name'], "retrieved_documents": []}
            }

        # 3. Text chunking
        logger.info(f"Splitting {len(all_docs)} documents into chunks.")
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunked_docs = text_splitter.split_documents(all_docs)
        logger.info(f"Created {len(chunked_docs)} chunks.")

        if not chunked_docs:
            logger.warning("No chunks were created from the documents. Cannot proceed with RAG.")
            return {
                "query": query, "query_type": "rag", "success": True,
                "answer": f"Could not extract valid content chunks from files in data source '{datasource['name']}' for querying.",
                "data": {"source_datasource_id": datasource['id'], "source_datasource_name": datasource['name'], "retrieved_documents": []}
            }

        # 4. Create in-memory vector store (FAISS)
        logger.info("Creating FAISS vector store from chunks...")
        vector_store = FAISS.from_documents(chunked_docs, embeddings)
        logger.info("FAISS vector store created.")

        # 5. Perform retrieval (RetrievalQA chain)
        logger.info("Setting up RetrievalQA chain...")
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff", # Other types: map_reduce, refine, map_rerank
            retriever=vector_store.as_retriever(search_kwargs={"k": 3}), # Retrieve top 3 chunks
            return_source_documents=True
        )
        logger.info(f"Executing RAG query: '{query}'")
        result = await qa_chain.ainvoke({"query": query})
        
        answer = result.get("result", "Could not find a clear answer in the knowledge base.")
        source_documents_data = []
        if result.get("source_documents"):
            for doc_source in result["source_documents"]:
                source_documents_data.append({
                    "source": doc_source.metadata.get("source", "Unknown source"),
                    "content_preview": doc_source.page_content[:200] + "..." # Preview of content
                })

        logger.info(f"RAG query successful. Answer: {answer[:200]}... Sources: {len(source_documents_data)}")
        return {
            "query": query,
            "query_type": "rag",
            "answer": answer,
            "data": {
                "source_datasource_id": datasource['id'],
                "source_datasource_name": datasource['name'],
                "retrieved_documents": source_documents_data
            },
            "success": True
        }

    except Exception as e:
        logger.error(f"Error during RAG for datasource {datasource['name']}: {e}", exc_info=True)
        return {
            "query": query, "query_type": "rag", "success": False,
            "answer": f"A critical error occurred while processing your query '{query}' in data source '{datasource['name']}'.",
            "data": {"source_datasource_id": datasource['id'], "source_datasource_name": datasource['name']},
            "error": str(e)
        }

async def get_answer_from_hybrid_datasource(query: str, active_datasource: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handles queries for hybrid data sources.
    Analyzes the query and available files to determine whether to use SQL or RAG processing.
    
    Decision logic:
    1. If the datasource has SQL tables (db_table_name) and query seems structured -> SQL
    2. If query seems document-related or no SQL tables available -> RAG
    3. Can potentially combine both approaches for complex queries
    """
    logger.info(f"Processing hybrid query for datasource: {active_datasource['name']} (ID: {active_datasource['id']})")
    
    datasource_id = active_datasource['id']
    ds_name = active_datasource['name']
    
    try:
        # Get available files and their types
        db_files = await get_files_by_datasource(datasource_id)
        completed_files = [f for f in db_files if f['processing_status'] == 'completed']
        
        # Categorize files by processing type
        sql_files = [f for f in completed_files if f['file_type'].lower() in ['csv', 'xlsx']]
        rag_files = [f for f in completed_files if f['file_type'].lower() in ['txt', 'pdf', 'docx']]
        
        logger.info(f"Hybrid datasource analysis - SQL files: {len(sql_files)}, RAG files: {len(rag_files)}")
        
        # Determine query routing strategy
        query_lower = query.lower()
        
        # Keywords that suggest SQL operations
        sql_keywords = ['sum', 'count', 'average', 'total', 'sales', 'revenue', 'amount', 'quantity', 
                       'statistics', 'report', 'calculate', 'how many', 'how much', 'trend', 'analysis']
        
        # Keywords that suggest document/RAG operations  
        rag_keywords = ['what is', 'explain', 'describe', 'definition', 'meaning', 'content', 
                       'document', 'text', 'information about', 'tell me about', 'summary of']
        
        has_sql_indicators = any(keyword in query_lower for keyword in sql_keywords)
        has_rag_indicators = any(keyword in query_lower for keyword in rag_keywords)
        
        # Decision logic
        if sql_files and active_datasource.get("db_table_name") and (has_sql_indicators or not has_rag_indicators):
            # Route to SQL if we have SQL data and query seems numerical/analytical
            logger.info(f"Routing hybrid query to SQL processing for datasource: {ds_name}")
            return await get_answer_from_sqltable_datasource(query, active_datasource)
            
        elif rag_files and (has_rag_indicators or not has_sql_indicators):
            # Route to RAG if we have documents and query seems informational
            logger.info(f"Routing hybrid query to RAG processing for datasource: {ds_name}")
            return await perform_rag_query(query, active_datasource)
            
        elif sql_files and active_datasource.get("db_table_name"):
            # Default to SQL if available
            logger.info(f"Defaulting hybrid query to SQL processing for datasource: {ds_name}")
            return await get_answer_from_sqltable_datasource(query, active_datasource)
            
        elif rag_files:
            # Default to RAG if SQL not available
            logger.info(f"Defaulting hybrid query to RAG processing for datasource: {ds_name}")
            return await perform_rag_query(query, active_datasource)
            
        else:
            # No processed files available
            return {
                "query": query, "query_type": "hybrid", "success": True,
                "answer": f"Hybrid data source '{ds_name}' doesn't have any processed files available. Please upload CSV/Excel files for SQL queries or TXT/PDF/Word files for document queries.",
                "data": {
                    "source_datasource_id": datasource_id,
                    "source_datasource_name": ds_name,
                    "available_sql_files": len(sql_files),
                    "available_rag_files": len(rag_files),
                    "routing_decision": "no_files_available"
                }
            }
            
    except Exception as e:
        logger.error(f"Error in hybrid datasource processing: {e}", exc_info=True)
        return {
            "query": query, "query_type": "hybrid", "success": False,
            "answer": f"Error processing hybrid query for data source '{ds_name}': {str(e)}",
            "data": {"source_datasource_name": ds_name},
            "error": str(e)
        }

async def get_answer_from_sqltable_datasource(query: str, active_datasource: Dict[str, Any]) -> Dict[str, Any]:
    """
    Queries the dynamically created SQL table associated with the specified data source using LangChain SQL Agent.
    """
    logger.info(f"Attempting SQL Agent query on datasource: {active_datasource['name']} (ID: {active_datasource['id']}) for query: '{query}'")

    if not llm:
        logger.error("LLM not initialized. SQL Agent query cannot be performed.")
        return {
            "query": query, "query_type": "sql_agent", "success": False,
            "answer": "SQL Agent functionality cannot be executed because LLM is not initialized.",
            "data": {"source_datasource_id": active_datasource['id'], "source_datasource_name": active_datasource['name']},
            "error": "LLM not initialized for SQL Agent."
        }

    db_table_name = active_datasource.get("db_table_name")
    if not db_table_name:
        logger.error(f"Data source '{active_datasource['name']}' is not fully configured. Missing associated database table name.")
        return {
            "query": query, "query_type": "sql_agent", "success": False,
            "answer": f"Data source '{active_datasource['name']}' is not fully configured. Missing associated database table name.",
            "data": {"source_datasource_id": active_datasource['id'], "source_datasource_name": active_datasource['name']},
            "error": "Missing db_table_name for SQL_TABLE_FROM_FILE datasource."
        }

    try:
        logger.info(f"Initializing SQLDatabase for table: {db_table_name} using URI: {DB_URI}")
        # SQLDatabase will connect to the main smart.db, but we tell it to only include the specific table.
        db = SQLDatabase.from_uri(DB_URI, include_tables=[db_table_name], sample_rows_in_table_info=3)
        
        # Get schema info for validation
        schema_info = db.get_table_info()
        
        # Process time expressions in query
        processed_query = _process_time_expressions(query)

        # Get available tables
        available_tables = db.get_usable_table_names()
        logger.info(f"Available tables: {available_tables}")

        # Detect if this is a time series/trend query
        is_trend_query = any(keyword in processed_query.lower() for keyword in [
            'trend', 'monthly', 'weekly', 'yearly', 'over time', 'by month', 'by year', 
            'time series', 'quarterly'
        ])

        # Generate SQL using direct LLM call with enhanced time series support
        sql_generation_prompt = f"""
        User query: "{processed_query}"

        Available tables: {available_tables}
        Table schema: {schema_info}

        NOTE: Ignore any year in the table name; data may span multiple years. Always filter using the date column to satisfy the query.\n        
        **CRITICAL ANALYSIS**: This query appears to be a {'TIME SERIES/TREND' if is_trend_query else 'STANDARD'} query.

        Please generate a SQLite query to answer the user's question. The query should:
        1. Only use SELECT statements (no INSERT, UPDATE, DELETE, etc.)
        2. Only use tables that are available in the database
        3. Follow these guidelines based on query type:
        
        **FOR TIME SERIES/TREND QUERIES**:
        - If there are date/time columns, use appropriate strftime functions for grouping
        - Include proper GROUP BY clauses for aggregations
        - Order results chronologically
        - Example: 
          SELECT strftime('%Y-%m', date_column) as period, 
                 COUNT(*) as count, 
                 SUM(value_column) as total 
          FROM table_name 
          GROUP BY period 
          ORDER BY period
            
        **FOR STANDARD QUERIES**:
        - Use appropriate aggregations (SUM, COUNT, AVG) based on the question
        - Include WHERE clauses to filter data as needed
        - Order results logically (e.g., by value for rankings)
        - Handle date/time filters appropriately if present
        
        4. Use appropriate aggregations based on what user asks
        5. Include proper WHERE clauses to filter data as needed
        6. Order results appropriately
        7. Limit results to a reasonable number (LIMIT 50 by default)

        **IMPORTANT**: 
        - Return results in a format that matches the query intent
        - Use column names exactly as they appear in the schema
        - Ensure all referenced tables and columns exist in the schema

        Only return the SQL query, no explanations or other text.
        """

        try:
            # Execute query with timeout from config
            # Use reasoning model for SQL generation
            reasoning_llm = get_reasoning_llm() if llm else None
            active_llm = reasoning_llm or llm
            sql_response = await asyncio.wait_for(
                active_llm.ainvoke(sql_generation_prompt),
                timeout=Config.LLM_TIMEOUT
            )
            
            # Extract SQL from response - handle different LLM response formats
            if hasattr(sql_response, 'content'):
                # OpenAI/OpenRouter format
                sql = sql_response.content.strip()
            elif hasattr(sql_response, 'text'):
                # Some LLM formats
                sql = sql_response.text.strip()
            else:
                # Fallback - treat as string
                sql = str(sql_response).strip()
            
            # Clean and validate SQL
            clean_sql = _clean_sql_statement(sql)
            if not _validate_sql_statement(clean_sql, schema_info):
                raise ValueError(f"Invalid SQL statement generated: {clean_sql}")
            
            try:
                # Execute the cleaned SQL
                query_result = db.run(clean_sql)
                
                # Handle different result types
                if isinstance(query_result, str):
                    # If result is a string, it might be an error or a single value
                    logger.warning(f"Query returned string result: {query_result}")
                    
                    # Try to parse if it's a string representation of data
                    parsed_data = _parse_string_query_result(query_result, db_table_name)
                    if parsed_data:
                        # Get actual column names from database
                        actual_columns = _get_table_columns(db_table_name)
                        # Successfully parsed tuple list string
                        structured_data = {
                            "rows": parsed_data,
                            "columns": actual_columns if actual_columns else list(parsed_data[0].keys()),
                            "executed_sql": clean_sql,
                            "queried_table": db_table_name
                        }
                        logger.info(f"Successfully converted string result to structured data with {len(parsed_data)} rows")
                    else:
                        # Fallback: treat as raw result
                        structured_data = {
                            "rows": [{"result": query_result}],
                            "columns": ["result"],
                            "executed_sql": clean_sql,
                            "queried_table": db_table_name
                        }
                        logger.warning("Failed to parse string result, using fallback format")
                else:
                    # Normal case: result is a list of dictionaries
                    if not query_result:
                        return {
                            "success": False,
                            "error": "Query returned no results. Please check if the time period contains data.",
                            "query": processed_query,
                            "executed_sql": clean_sql
                        }
                        
                    # Ensure query_result is a list
                    if not isinstance(query_result, list):
                        query_result = [query_result]
                        
                    structured_data = {
                        "rows": query_result,
                        "columns": list(query_result[0].keys()) if query_result else [],
                        "executed_sql": clean_sql,
                        "queried_table": db_table_name
                    }
                
                return {
                    "success": True,
                    "data": structured_data,
                    "answer": f"Here are the results for your query about {processed_query}",
                    "executed_sql": clean_sql,
                    "query": processed_query
                }
                
            except Exception as e:
                error_msg = str(e)
                if "no such table" in error_msg.lower():
                    error_msg = f"Table not found. Available tables are: {', '.join(available_tables)}"
                elif "no such column" in error_msg.lower():
                    error_msg = f"Column not found in schema: {error_msg}"
                elif "no such function: strtofloat" in error_msg.lower():
                    error_msg = "SQLite does not support strtofloat function. Please use CAST(column AS REAL) or column * 1.0 to convert text to numbers."
                elif "strtofloat" in error_msg.lower():
                    error_msg = "The query contains an unsupported function. Please rephrase your question to avoid using strtofloat or similar functions."
                    
                logger.error(f"SQL execution failed: {error_msg}")
                return {
                    "success": False,
                    "error": f"Error executing SQL query: {error_msg}",
                    "query": processed_query,
                    "executed_sql": clean_sql
                }

        except asyncio.TimeoutError:
            logger.warning(f"Query SQL generation timed out for query: {processed_query}")
            return {
                "success": False,
                "error": "Query generation timed out",
                "query": processed_query
            }

    except Exception as e:
        logger.error(f"Error during SQL Agent query: {e}")
        return {
            "query": query, "query_type": "sql_agent", "success": False,
            "answer": f"Error during SQL Agent query: {str(e)}",
            "data": {"source_datasource_id": active_datasource['id'], "source_datasource_name": active_datasource['name']},
            "error": str(e)
        }

async def get_answer_from(query: str, query_type: str = "sales", active_datasource: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Main function to get answers from the system.
    Routes the query based on the query_type and active_datasource.
    """
    # If no active_datasource provided, get the current active datasource from database
    if not active_datasource:
        active_datasource = await get_active_datasource()
        if not active_datasource:
            return {
                "query": query, "query_type": query_type, "success": False,
                "answer": "No active data source found. Please select or create a data source first.",
                "error": "No active datasource"
            }

    logger.info(f"get_answer_from called with query: '{query}', query_type: '{query_type}', active_datasource: {active_datasource['name']}")

    if not llm and active_datasource.get('type') != DataSourceType.DEFAULT.value:
        # If LLM is not available AND we are not using the default (which might have non-LLM paths)
        return {
            "query": query, "query_type": query_type, "success": False,
            "answer": "Core question answering service not initialized. Unable to process your request. Please check system configuration.",
            "data": {"source_datasource_name": active_datasource['name']},
            "error": "LLM not initialized."
        }

    # Determine the type of the active datasource
    ds_type = active_datasource.get('type')
    ds_name = active_datasource.get('name')

    logger.info(f"Routing query. Datasource type: {ds_type}, Datasource name: {ds_name}")

    if ds_type == DataSourceType.SQL_TABLE_FROM_FILE.value:
        logger.info(f"Routing to SQL Agent for datasource: {ds_name}")
        if not active_datasource or not active_datasource.get("db_table_name"):
            logger.error(f"SQL_TABLE_FROM_FILE datasource '{ds_name}' is missing 'db_table_name'.")
            return {
                "query": query, "query_type": "sql_agent", "success": False,
                "answer": f"Data source '{ds_name}' is not fully configured. Unable to perform SQL query.",
                "data": {"source_datasource_name": ds_name},
                "error": "Missing db_table_name."
            }
        return await get_answer_from_sqltable_datasource(query, active_datasource)
    
    elif ds_type == DataSourceType.HYBRID.value:
        logger.info(f"Routing to Hybrid Agent for datasource: {ds_name}")
        return await get_answer_from_hybrid_datasource(query, active_datasource)
    
    elif ds_type == DataSourceType.KNOWLEDGE_BASE.value: # Knowledge base uses RAG
        logger.info(f"Routing to RAG for datasource: {ds_name}")
        if not active_datasource: # Should not happen if ds_type is not DEFAULT, but good check
             return {"answer": "Error: Attempting to use RAG without specifying a custom data source."}
        return await perform_rag_query(query, active_datasource)

async def attempt_direct_query_fallback(query: str, db, table_name: str, active_datasource: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Fallback solution: execute simple database queries directly to avoid Agent parsing issues
    """
    try:
        # Generate simple SQL based on query content
        if "sales" in query.lower() or "trend" in query.lower():
            # Sales trend query
            direct_sql = f"SELECT date, sales FROM {table_name} ORDER BY date LIMIT 10"
        elif "product" in query.lower():
            # Product query
            direct_sql = f"SELECT product, SUM(sales) as total_sales FROM {table_name} GROUP BY product LIMIT 10"
        elif "total" in query.lower():
            # Total query
            direct_sql = f"SELECT SUM(sales) as total_sales FROM {table_name}"
        else:
            # Default query
            direct_sql = f"SELECT * FROM {table_name} LIMIT 10"
        
        logger.info(f"Executing direct fallback query: {direct_sql}")
        result = db.run(direct_sql)
        
        if result:
            # Parse results and generate answer
            if "trend" in query.lower():
                answer = "The sales trend shows data from the database query results."
            elif "total" in query.lower():
                answer = f"The total sales amount is {result}."
            else:
                answer = f"Found {len(result.split(',')) if isinstance(result, str) else 'several'} records based on your query."
            
            return {
                "query": query,
                "query_type": "sql_agent",
                "success": True,
                "answer": answer,
                "data": {
                    "source_datasource_id": active_datasource['id'],
                    "source_datasource_name": active_datasource['name'],
                    "queried_table": table_name,
                    "rows": result,
                    "recovery_method": "direct_query_fallback"
                }
            }
    except Exception as e:
        logger.error(f"Direct query fallback failed: {e}")
        return None

def extract_answer_from_timeout(timeout_response: str, original_query: str, db, table_name: str) -> str:
    """
    Try to extract useful information from timeout Agent response, or execute simple direct query
    """
    try:
        from sqlalchemy import text
        # Try executing a simple table data query as fallback solution
        simple_query = f"SELECT * FROM {table_name} LIMIT 5"
        
        with db._engine.connect() as connection:
            result = connection.execute(text(simple_query))
            rows = result.fetchall()
            columns = result.keys()
            
            if rows:
                data_preview = []
                for row in rows:
                    data_preview.append(dict(zip(columns, row)))
                
                # Generate simple answer based on query content
                if "sales" in original_query.lower() or "trend" in original_query.lower():
                    total_amount = sum(float(row.get('total_amount', 0)) for row in data_preview if row.get('total_amount'))
                    return f"Based on recent data from {table_name}, I found {len(data_preview)} records with a total amount of approximately {total_amount:.2f}. Due to processing limitations, this is a simplified analysis."
                elif "count" in original_query.lower() or "how many" in original_query.lower():
                    count_query = f"SELECT COUNT(*) as count FROM {table_name}"
                    count_result = connection.execute(text(count_query))
                    count = count_result.fetchone()[0]
                    return f"The table {table_name} contains {count} total records."
                else:
                    return f"I found {len(data_preview)} sample records in {table_name}. Here's a preview of the data structure."
            else:
                return f"The table {table_name} appears to be empty or inaccessible."
                
    except Exception as e:
        logger.error(f"Fallback query also failed: {e}")
        return "I encountered processing difficulties. Please try simplifying your question or contact support."

def initialize_app_state():
    """
    Initializes critical application state, like database and LLM/Embedding models.
    Called at application startup.
    """
    logger.info("Starting initialization of application state (database, LLM, embedding model)...")
    
    # 1. Initialize Database (ensure schema and base data)
    try:
        initialize_database() # Changed: Call the renamed function in db.py
        logger.info("Database initialization completed.")
    except Exception as e:
        logger.error(f"An error occurred during database initialization: {e}", exc_info=True)
        # Depending on severity, might want to raise to stop app, or continue with limited functionality.

    # LLM and Embeddings are already initialized when this module is imported.
    # We can add checks here or re-log their status.
    if llm:
        logger.info("LLM model was initialized when this module was loaded.")
    else:
        logger.warning("LLM model not initialized. Question answering and report functionality will be limited.")

    if embeddings:
        logger.info("Embedding model was initialized when this module was loaded.")
    else:
        logger.warning("Embedding model not initialized. RAG functionality will be unavailable.")
        
    logger.info("Application state initialization completed.")

# Add new function for query SQL processing
async def get_query_from_sqltable_datasource(
    query: str, 
    active_datasource: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get answer from SQL table datasource with improved error handling and SQL cleaning
    Specifically optimized for data queries (not charts)
    """
    logger.info(f"Attempting Query SQL on datasource: {active_datasource['name']} (ID: {active_datasource['id']}) for query: '{query}'")

    if not llm:
        return {
            "success": False,
            "error": "LLM not initialized. SQL query cannot be processed.",
            "query": query
        }

    try:
        # Get table name from datasource
        table_name = active_datasource.get('db_table_name')
        if not table_name:
            logger.error(f"Missing db_table_name for datasource: {active_datasource['name']}")
            return {
                "success": False,
                "error": "Missing table name in datasource configuration",
                "query": query
            }
            
        logger.info(f"Initializing SQLDatabase for query: {table_name}")
        
        # Initialize database connection
        db = SQLDatabase.from_uri(DB_URI, include_tables=[table_name])
        
        # Get schema info for validation
        schema_info = db.get_table_info()
        
        # Process time expressions in query
        processed_query = _process_time_expressions(query)

        # Get available tables
        available_tables = db.get_usable_table_names()
        logger.info(f"Available tables: {available_tables}")

        # Detect if this is a time series/trend query
        is_trend_query = any(keyword in processed_query.lower() for keyword in [
            'trend', 'monthly', 'weekly', 'yearly', 'over time', 'by month', 'by year', 
            'time series', 'quarterly'
        ])

        # Generate SQL using direct LLM call with enhanced time series support
        sql_generation_prompt = f"""
        User query: "{processed_query}"

        Available tables: {available_tables}
        Table schema: {schema_info}

        NOTE: Ignore any year in the table name; data may span multiple years. Always filter using the date column to satisfy the query.\n        
        **CRITICAL ANALYSIS**: This query appears to be a {'TIME SERIES/TREND' if is_trend_query else 'STANDARD'} query.

        Please generate a SQLite query to answer the user's question. The query should:
        1. Only use SELECT statements (no INSERT, UPDATE, DELETE, etc.)
        2. Only use tables that are available in the database
        3. Follow these guidelines based on query type:
        
        **FOR TIME SERIES/TREND QUERIES**:
        - If there are date/time columns, use appropriate strftime functions for grouping
        - Include proper GROUP BY clauses for aggregations
        - Order results chronologically
        - Example: 
          SELECT strftime('%Y-%m', date_column) as period, 
                 COUNT(*) as count, 
                 SUM(value_column) as total 
          FROM table_name 
          GROUP BY period 
          ORDER BY period
            
        **FOR STANDARD QUERIES**:
        - Use appropriate aggregations (SUM, COUNT, AVG) based on the question
        - Include WHERE clauses to filter data as needed
        - Order results logically (e.g., by value for rankings)
        - Handle date/time filters appropriately if present
        
        4. Use appropriate aggregations based on what user asks
        5. Include proper WHERE clauses to filter data as needed
        6. Order results appropriately
        7. Limit results to a reasonable number (LIMIT 50 by default)

        **IMPORTANT**: 
        - Return results in a format that matches the query intent
        - Use column names exactly as they appear in the schema
        - Ensure all referenced tables and columns exist in the schema

        Only return the SQL query, no explanations or other text.
        """

        try:
            # Execute query with timeout from config
            sql_response = await asyncio.wait_for(
                llm.ainvoke(sql_generation_prompt),
                timeout=Config.LLM_TIMEOUT
            )
            
            # Extract SQL from response - handle different LLM response formats
            if hasattr(sql_response, 'content'):
                # OpenAI/OpenRouter format
                sql = sql_response.content.strip()
            elif hasattr(sql_response, 'text'):
                # Some LLM formats
                sql = sql_response.text.strip()
            else:
                # Fallback - treat as string
                sql = str(sql_response).strip()
            
            # Clean and validate SQL
            clean_sql = _clean_sql_statement(sql)
            if not _validate_sql_statement(clean_sql, schema_info):
                raise ValueError(f"Invalid SQL statement generated: {clean_sql}")
            
            try:
                # Execute the cleaned SQL
                query_result = db.run(clean_sql)
                
                # Handle different result types
                if isinstance(query_result, str):
                    # If result is a string, it might be an error or a single value
                    logger.warning(f"Query returned string result: {query_result}")
                    
                    # Try to parse if it's a string representation of data
                    parsed_data = _parse_string_query_result(query_result, table_name)
                    if parsed_data:
                        # Get actual column names from database
                        actual_columns = _get_table_columns(table_name)
                        # Successfully parsed tuple list string
                        structured_data = {
                            "rows": parsed_data,
                            "columns": actual_columns if actual_columns else list(parsed_data[0].keys()),
                            "executed_sql": clean_sql,
                            "queried_table": table_name
                        }
                        logger.info(f"Successfully converted string result to structured data with {len(parsed_data)} rows")
                    else:
                        # Fallback: treat as raw result
                        structured_data = {
                            "rows": [{"result": query_result}],
                            "columns": ["result"],
                            "executed_sql": clean_sql,
                            "queried_table": table_name
                        }
                        logger.warning("Failed to parse string result, using fallback format")
                else:
                    # Normal case: result is a list of dictionaries
                    if not query_result:
                        return {
                            "success": False,
                            "error": "Query returned no results. Please check if the time period contains data.",
                            "query": processed_query,
                            "executed_sql": clean_sql
                        }
                        
                    # Ensure query_result is a list
                    if not isinstance(query_result, list):
                        query_result = [query_result]
                        
                    structured_data = {
                        "rows": query_result,
                        "columns": list(query_result[0].keys()) if query_result else [],
                        "executed_sql": clean_sql,
                        "queried_table": table_name
                    }
                
                return {
                    "success": True,
                    "data": structured_data,
                    "answer": f"Here are the results for your query about {processed_query}",
                    "executed_sql": clean_sql,
                    "query": processed_query
                }
                
            except Exception as e:
                error_msg = str(e)
                if "no such table" in error_msg.lower():
                    error_msg = f"Table not found. Available tables are: {', '.join(available_tables)}"
                elif "no such column" in error_msg.lower():
                    error_msg = f"Column not found in schema: {error_msg}"
                elif "no such function: strtofloat" in error_msg.lower():
                    error_msg = "SQLite does not support strtofloat function. Please use CAST(column AS REAL) or column * 1.0 to convert text to numbers."
                elif "strtofloat" in error_msg.lower():
                    error_msg = "The query contains an unsupported function. Please rephrase your question to avoid using strtofloat or similar functions."
                    
                logger.error(f"SQL execution failed: {error_msg}")
                return {
                    "success": False,
                    "error": f"Error executing SQL query: {error_msg}",
                    "query": processed_query,
                    "executed_sql": clean_sql
                }

        except asyncio.TimeoutError:
            logger.warning(f"Query SQL generation timed out for query: {processed_query}")
            return {
                "success": False,
                "error": "Query generation timed out",
                "query": processed_query
            }

    except Exception as e:
        logger.error(f"Error in get_query_from_sqltable_datasource: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to process query: {str(e)}",
            "query": query
        }

def _clean_sql_statement(sql: str) -> str:
    """Clean SQL statement by removing comments and extra text"""
    # Remove comments
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)  # Remove /* ... */ comments
    sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)   # Remove -- comments
    
    # Remove explanation text after semicolon
    sql = sql.split(';')[0] + ';' if ';' in sql else sql
    
    # Clean whitespace
    sql = ' '.join(sql.split())
    
    # Apply SQLite-specific fixes (date filters, placeholders)
    sql = _apply_sqlite_fixes(sql)
    
    return sql

def _apply_sqlite_fixes(sql: str) -> str:
    """Patch common SQL issues produced by LLM for SQLite.
    - Fix patterns like: saledate LIKE '%%%Y-%%-%m-%%' → strftime('%Y-%m', saledate) = strftime('%Y-%m','now')
    """
    try:
        # Generic: any column name that contains 'date' surrounded by word chars
        # Match excessive % with %Y and %m placeholders in quotes
        pattern = re.compile(r"(?i)(\b\w*date\w*\b)\s+LIKE\s+'%+%Y%*-?%+%m%*%+'")
        def replace_like_current_month(match: re.Match) -> str:
            col = match.group(1)
            return f"strftime('%Y-%m', {col}) = strftime('%Y-%m','now')"
        patched = re.sub(pattern, replace_like_current_month, sql)
        return patched
    except Exception:
        # If anything goes wrong, return original SQL
        return sql

def _validate_sql_statement(sql: str, schema_info: str) -> bool:
    """Validate SQL statement against schema and basic rules"""
    sql_lower = sql.lower()
    
    # Basic security checks
    dangerous_keywords = ['drop', 'truncate', 'delete', 'update', 'insert', 'alter', 'create']
    if any(keyword in sql_lower for keyword in dangerous_keywords):
        return False
    
    # Must be a SELECT statement
    if not sql_lower.strip().startswith('select'):
        return False
    
    return True

def _extract_sql_from_result(result: Dict[str, Any]) -> Optional[str]:
    """Extract SQL statement from agent result"""
    if not result or not isinstance(result, dict):
        return None
        
    # Try to find SQL in the output
    output = result.get("output", "")
    if not output:
        return None
        
    # Look for SQL between backticks or after "SQL:" or similar markers
    sql_markers = [
        r"```sql\n(.*?)\n```",
        r"```(.*?)```",
        r"SQL:\s*(.*?)(?:\n|$)",
        r"Query:\s*(.*?)(?:\n|$)",
        r"Generated SQL:\s*(.*?)(?:\n|$)"
    ]
    
    for marker in sql_markers:
        match = re.search(marker, output, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # If no SQL found in markers, try to find the first statement that looks like SQL
    lines = output.split('\n')
    for line in lines:
        if line.strip().lower().startswith('select'):
            return line.strip()
    
    return None

def _process_time_expressions(query: str) -> str:
    """Process time-related expressions in the query"""
    # Convert "last X weeks/months/years" to specific date ranges
    patterns = [
        (r'last (\d+) weeks?', lambda m: f'in the past {m.group(1)} weeks'),
        (r'last (\d+) months?', lambda m: f'in the past {m.group(1)} months'),
        (r'last (\d+) years?', lambda m: f'in the past {m.group(1)} years'),
        (r'past (\d+) weeks?', lambda m: f'in the past {m.group(1)} weeks'),
        (r'past (\d+) months?', lambda m: f'in the past {m.group(1)} months'),
        (r'past (\d+) years?', lambda m: f'in the past {m.group(1)} years'),
        (r'previous (\d+) weeks?', lambda m: f'in the past {m.group(1)} weeks'),
        (r'previous (\d+) months?', lambda m: f'in the past {m.group(1)} months'),
        (r'previous (\d+) years?', lambda m: f'in the past {m.group(1)} years')
    ]
    
    processed = query
    for pattern, replacement in patterns:
        processed = re.sub(pattern, replacement, processed, flags=re.IGNORECASE)
    
    return processed

def _get_table_columns(table_name: str) -> Optional[List[str]]:
    """Get actual column names from database table"""
    try:
        from ..database.db_operations import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get column information
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns_info = cursor.fetchall()
        
        # Extract column names
        column_names = [col[1] for col in columns_info]  # col[1] is the column name
        
        conn.close()
        return column_names
    except Exception as e:
        logger.error(f"Error getting table columns for {table_name}: {e}")
        return None

def _parse_string_query_result(result: str, table_name: str = None) -> Optional[List[Dict[str, Any]]]:
    """Parse a string result that contains Python tuple list representation"""
    try:
        # Check if the result looks like a Python tuple list string
        if result.startswith('[') and result.endswith(']') and '(' in result and ')' in result:
            # Try to safely evaluate the string as Python literal
            import ast
            try:
                # Use ast.literal_eval for safe parsing of Python literals
                parsed_tuples = ast.literal_eval(result)
                
                if isinstance(parsed_tuples, list) and all(isinstance(item, tuple) for item in parsed_tuples):
                    # Convert tuples to dictionaries with meaningful column names
                    parsed_data = []
                    for tuple_item in parsed_tuples:
                        if len(tuple_item) == 1:
                            # Single value result from aggregation like SUM/COUNT
                            parsed_data.append({
                                "value": tuple_item[0]
                            })
                        elif len(tuple_item) == 2:
                            # Common case: (category, value) pairs - use descriptive names
                            parsed_data.append({
                                "category": str(tuple_item[0]),
                                "value": float(tuple_item[1]) if isinstance(tuple_item[1], (int, float)) else tuple_item[1]
                            })
                        else:
                            # Multiple columns: use actual column names from database
                            row_dict = {}
                            actual_columns = _get_table_columns(table_name) if table_name else None
                            
                            for i, value in enumerate(tuple_item):
                                if actual_columns and i < len(actual_columns):
                                    # Use actual column name from database
                                    row_dict[actual_columns[i]] = value
                                else:
                                    # Fallback to generic column names
                                    row_dict[f"col_{i}"] = value
                            parsed_data.append(row_dict)
                    
                    logger.info(f"Successfully parsed {len(parsed_data)} rows from string result")
                    return parsed_data
                    
            except (ValueError, SyntaxError) as e:
                logger.warning(f"Failed to parse tuple list string: {e}")
                return None
        
        # If not a tuple list format, return None to use fallback logic
        return None
        
    except Exception as e:
        logger.error(f"Error parsing string query result: {e}")
        return None

