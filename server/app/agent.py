import os
from typing import Optional, List, Dict, Any, Union
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain.docstore.document import Document
from .db import (
    fetch_sales_data_for_query,
    fetch_low_stock_products,
    get_product_details,
    initialize_database,  # Changed: initialize_app_database -> initialize_database
    get_files_by_datasource, # Added to get files for RAG
    DATABASE_PATH # Import DATABASE_PATH
)
from .report import generate_daily_sales_summary_report
from .models import DataSourceType # Import DataSourceType
from dotenv import load_dotenv
from pathlib import Path # Added Path
import logging # Added logging
import pandas as pd # Added pandas

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import for local embeddings
# from langchain_community.embeddings import SentenceTransformerEmbeddings # Already imported above

load_dotenv()

# Get API Key from environment variables or configuration file
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
LLM_MODEL_NAME = os.getenv("OPENAI_MODEL")
# EMBEDDING_MODEL_NAME is no longer needed for OpenAI, we'll use a fixed local model name
LOCAL_EMBEDDING_MODEL_NAME = 'intfloat/multilingual-e5-small' 

# Determine the correct upload directory relative to this file (agent.py)
# Assuming agent.py is in server/app/ and uploads are in server/data/uploads/
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "data" / "uploads"
DB_URI = f"sqlite:///{DATABASE_PATH}" # Construct DB URI for LangChain

llm = None
embeddings = None # Initialize embeddings variable

# Imports for file parsing
import PyPDF2
from docx import Document as DocxDocument

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

# Initialize LLM (OpenAI or other compatible)
if OPENAI_API_KEY and not OPENAI_API_KEY.startswith(("123456", "local_mode")):
    try:
        llm_kwargs = {
            "model_name": LLM_MODEL_NAME,
            "temperature": 0,
            "openai_api_key": OPENAI_API_KEY
        }
        if OPENAI_BASE_URL:
            llm_kwargs["openai_api_base"] = OPENAI_BASE_URL
        llm = ChatOpenAI(**llm_kwargs)
        logger.info(f"LLM initialized successfully - Model: {LLM_MODEL_NAME}")
        if OPENAI_BASE_URL:
            logger.info(f"Using custom LLM API endpoint: {OPENAI_BASE_URL}")
    except Exception as e:
        logger.error(f"LLM initialization failed: {e}", exc_info=True)
        llm = None
else:
    logger.warning("OpenAI API Key not configured or is a dummy value. LLM functionality will be limited or simulated.")

# Initialize Local Embeddings (SentenceTransformer)
try:
    logger.info(f"Starting initialization of local embedding model: {LOCAL_EMBEDDING_MODEL_NAME}")
    # Specify a cache folder for sentence-transformers models if desired, e.g., within server/data/
    # cache_folder = Path(__file__).resolve().parent.parent / "data" / "st_cache"
    # cache_folder.mkdir(parents=True, exist_ok=True)
    # embeddings = SentenceTransformerEmbeddings(model_name=LOCAL_EMBEDDING_MODEL_NAME, cache_folder=str(cache_folder))
    embeddings = SentenceTransformerEmbeddings(model_name=LOCAL_EMBEDDING_MODEL_NAME)
    logger.info(f"Local embedding model {LOCAL_EMBEDDING_MODEL_NAME} initialized successfully.")
except Exception as e:
    logger.error(f"Local embedding model {LOCAL_EMBEDDING_MODEL_NAME} initialization failed: {e}", exc_info=True)
    embeddings = None

async def perform_rag_query(query: str, datasource: Dict[str, Any]) -> Dict[str, Any]:
    """
    Performs RAG retrieval and Q&A for the specified data source.
    """
    logger.info(f"Attempting RAG query on datasource: {datasource['name']} (ID: {datasource['id']}) for query: '{query}'")

    if not llm:
        logger.warning("LLM not initialized. RAG query cannot generate final answer effectively.")
        # Allow to proceed if embeddings are available, for retrieval-only tests, but flag it.
    
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

        logger.info(f"RAG query successful. Answer: {answer[:100]}... Sources: {len(source_documents_data)}")
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
        db = SQLDatabase.from_uri(DB_URI, include_tables=[db_table_name])
        
        logger.info(f"Creating SQL Agent for table: {db_table_name}")
        # If using a non-OpenAI LLM that doesn't support function calling well,
        # you might need to use AgentType.ZERO_SHOT_REACT_DESCRIPTION
        # sql_agent_executor = create_sql_agent(llm=llm, db=db, agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True)
        # For OpenAI models that support function calling, the default agent type is usually better.
        sql_agent_executor = create_sql_agent(llm=llm, db=db, verbose=True, handle_parsing_errors=True) # Added handle_parsing_errors
        
        logger.info(f"Executing SQL Agent with query: {query}")
        # The agent's invoke method expects a dictionary with an "input" key
        # result = await sql_agent_executor.arun(query) # arun for async execution if available and needed
        # Using run for synchronous execution as create_sql_agent typically returns a synchronous agent.
        # If create_sql_agent can be made async or if we use a different SQL chain, arun might be an option.
        # For now, we'll run it in a thread to avoid blocking if it's truly synchronous.
        # However, LangChain's agents are often designed to be run synchronously.
        # Let's assume `run` is appropriate for now, and FastAPI handles threading.
        
        # Correct way to invoke is often with a dictionary:
        # response = sql_agent_executor.invoke({"input": query})
        # The direct string input might also work depending on the agent version/type.
        
        # Let's stick to the common .invoke pattern for better compatibility
        response = await sql_agent_executor.ainvoke({"input": query}) # Using ainvoke for async
        
        answer = response.get("output", "Could not get an answer from SQL Agent.")
        logger.info(f"SQL Agent execution complete. Answer: {answer}")
        
        return {
            "query": query, "query_type": "sql_agent", "success": True,
            "answer": answer,
            "data": {
                "source_datasource_id": active_datasource['id'],
                "source_datasource_name": active_datasource['name'],
                "queried_table": db_table_name,
                # We could potentially include the generated SQL query from the agent's intermediate steps if verbose=True captures it.
            }
        }

    except Exception as e:
        logger.error(f"SQL Agent query failed for datasource {active_datasource['name']} on table {db_table_name}: {e}", exc_info=True)
        return {
            "query": query, "query_type": "sql_agent", "success": False,
            "answer": f"An error occurred while executing SQL query in data source '{active_datasource['name']}' (Table: {db_table_name}).",
            "data": {"source_datasource_id": active_datasource['id'], "source_datasource_name": active_datasource['name']},
            "error": str(e)
        }

async def get_answer_from(query: str, query_type: str = "sales", active_datasource: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Main function to get answers from the  system.
    Routes the query based on the query_type and active_datasource.
    """
    logger.info(f"get_answer_from called with query: '{query}', query_type: '{query_type}', active_datasource: {active_datasource['name'] if active_datasource else 'None'}")

    if not llm and (not active_datasource or active_datasource.get('type') != DataSourceType.DEFAULT.value):
         # If LLM is not available AND we are not using the default  (which might have non-LLM paths)
        logger.warning("LLM not initialized. Query processing will be significantly limited or simulated.")
        # Allow default  queries to proceed if they don't rely on LLM for their basic logic.
        # For RAG or SQL Agent, LLM is crucial.
        if active_datasource and active_datasource.get('type') != DataSourceType.DEFAULT.value:
            return {
                "query": query, "query_type": query_type, "success": False,
                "answer": "Core question answering service not initialized. Unable to process your request. Please check system configuration.",
                "data": {"source_datasource_name": active_datasource['name'] if active_datasource else "N/A"},
                "error": "LLM not initialized."
            }

    # Determine the type of the active datasource
    ds_type = active_datasource.get('type') if active_datasource else DataSourceType.DEFAULT.value
    ds_name = active_datasource.get('name', 'Default ') if active_datasource else 'Default '

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
    
    elif ds_type != DataSourceType.DEFAULT.value: # Any other custom datasource type (knowledge_base, document_collection) uses RAG
        logger.info(f"Routing to RAG for datasource: {ds_name}")
        if not active_datasource: # Should not happen if ds_type is not DEFAULT, but good check
             return {"answer": "Error: Attempting to use RAG without specifying a custom data source."}
        return await perform_rag_query(query, active_datasource)

    # Fallback to default  logic (SQLite queries for products, sales, inventory)
    logger.info(f"Routing to default  logic for datasource: {ds_name} (Query Type Hint: {query_type})")
    
    # Existing  logic based on query_type (sales, inventory, report)
    # This part might need LLM for interpretation or can use direct DB queries for simple cases.
    # For now, it assumes direct DB queries or simplified LLM interaction.
    if query_type == "sales":
        answer, data = await get_sales_query_response(query)
        return {"answer": answer, "data": data, "query_type": "sales", "source_datasource_name": ds_name}
    elif query_type == "inventory":
        data, answer = await get_inventory_check_response_by_query(query)
        return {"answer": answer, "data": {"low_stock_items": data}, "query_type": "inventory", "source_datasource_name": ds_name}
    elif query_type == "report" or "report" in query or "summary" in query:
        answer, report_data, chart_data = await get_daily_sales_report_response_from_agent()
        return {"answer": answer, "data": report_data, "chart_data": chart_data, "query_type": "report", "source_datasource_name": ds_name}
    else: # Default/Fallback for  if query_type is not specific
        # This could be a generic LLM call against the schema or a predefined set of actions.
        # For simplicity, let's route to sales as a general default for now.
        logger.info(f"Default  query type not specific ('{query_type}'), defaulting to sales-like query.")
        answer, data = await get_sales_query_response(query) # Or a more generic  query handler
        return {"answer": answer, "data": data, "query_type": "general", "source_datasource_name": ds_name}


async def get_sales_query_response(query: str) -> tuple[str, Optional[dict]]:
    """
    Handles sales-related queries for the default  datasource.
    (This is part of the original  logic)
    """
    logger.info(f"Processing sales query for default : {query}")
    # This function would contain logic to parse the query, fetch data from 
    # the 'sales', 'products' tables in SQLite, and formulate an answer.
    # It might use LLM for understanding the query and formatting the response,
    # or use simpler rule-based logic for predefined questions.
    
    # Example: Fetch raw data first
    sales_data = await fetch_sales_data_for_query(query) # This function already exists

    if not sales_data:
        return "Based on your query, I couldn't find related sales data.", None

    # Simplified response for now. A real scenario might use LLM to summarize.
    if llm:
        # Prepare a prompt for the LLM to summarize the sales_data based on the query
        prompt = f"""
        User query: "{query}"
        Relevant sales data (JSON):
        {str(sales_data[:5])} ... (showing first 5 records for brevity)
        
        Please generate a concise answer in English based on the user query and the data above.
        If the user query asks for specific metrics (e.g., total sales, average order value), calculate and include them.
        """
        try:
            response = llm.invoke(prompt)
            answer = response.content
            logger.info(f"LLM generated sales answer: {answer}")
            return answer, {"detailed_sales": sales_data}
        except Exception as e:
            logger.error(f"LLM invocation failed for sales query summarization: {e}", exc_info=True)
            return f"Found {len(sales_data)} related sales records. Unable to provide detailed summary due to LLM processing error.", {"detailed_sales": sales_data}
    else:
        # Fallback if LLM is not available for sales query
        num_records = len(sales_data)
        total_sales_amount = sum(item['total_amount'] for item in sales_data)
        
        answer = f"Found {num_records} sales records. Total sales amount approximately {total_sales_amount:.2f}."
        if "best selling" in query or "top selling" in query:
            # Simple logic for top selling - could be more sophisticated
            from collections import Counter
            product_counts = Counter(item['product_name'] for item in sales_data)
            top_product, count = product_counts.most_common(1)[0] if product_counts else ("Unknown", 0)
            answer += f" The most frequently sold product is '{top_product}' (sold {count} times)."

        return answer, {"detailed_sales": sales_data, "summary_stats": {"total_records": num_records, "total_amount": total_sales_amount}}

async def get_inventory_check_response_by_query(query: str) -> tuple[List[Dict[str, Any]], str]:
    """
    Handles inventory-related queries by trying to extract a product ID or using general low stock.
    (This is part of the original  logic)
    """
    logger.info(f"Processing inventory query for default : {query}")
    # Simple check for a product ID (e.g., "库存 P001") - this could be more robust
    # For a more general query, it might default to showing low stock items.
    
    # Attempt to find a product ID in the query (very basic)
    # A more robust solution would use NER or pattern matching.
    potential_product_id = None
    words = query.split()
    for word in words:
        if word.upper().startswith("P") and word[1:].isdigit(): # Simple check for "PXXX" format
            potential_product_id = word.upper()
            break
            
    items_to_report = []
    response_summary = ""

    if potential_product_id:
        logger.info(f"Found potential product ID in inventory query: {potential_product_id}")
        product_detail = await get_product_details(potential_product_id) # Assumes get_product_details also fetches inventory
        if product_detail:
            # This assumes get_product_details would be extended to include stock info
            # or we make another call here. For now, let's assume it's part of product_detail.
            # items_to_report.append(product_detail) # Adjust based on actual structure
            # response_summary = f"Product {product_detail.get('product_name', potential_product_id)} 的库存信息..."
            
            # Let's refine this - get_product_details gets product info, then we need inventory for it.
            # This part needs to be aligned with how inventory is fetched per product.
            # For now, let's simulate:
            # Assume we have a function like `get_inventory_for_product(product_id)`
            # This is a placeholder - actual implementation would query inventory table.
            # For demonstration, we'll just say "Details for PXXX..." and rely on general low stock if not specific.
            # This logic is a bit convoluted due to missing specific inventory function per product.
            # Let's simplify: if specific product ID, try to get its details. Otherwise, low stock.
            
            # A better approach for "inventory of P001" is to make `get_product_details` more comprehensive
            # or have a dedicated `get_inventory_for_product(product_id)` function.
            # Given the current `get_low_stock_products`, we might not have a direct single product inventory view easily.
            
            # Let's assume the query "库存 P001" means "is P001 low stock?" for simplicity with current tools.
            low_stock_items = await fetch_low_stock_products(threshold=1000) # High threshold to get most items
            found_product_in_low_stock = False
            for item in low_stock_items:
                if item['product_id'] == potential_product_id:
                    items_to_report.append(item)
                    response_summary = f"Product {item['product_name']} (ID: {item['product_id']}) current stock level is {item['stock_level']}."
                    if item['stock_level'] < 50: # Example threshold
                        response_summary += " Stock level is low."
                    else:
                        response_summary += " Stock is sufficient."
                    found_product_in_low_stock = True
                    break
            if not found_product_in_low_stock:
                # If not in low_stock_items, assume it's not low or doesn't exist.
                # A full check would query inventory table directly.
                # For now, we say:
                response_summary = f"No low stock record found for product ID {potential_product_id}. Stock may be sufficient or product does not exist."
                # To be more accurate, we'd need a direct inventory lookup.
        else:
            response_summary = f"No product information found for product ID {potential_product_id}."

    else:  # General inventory query (corresponds to if potential_product_id)
        logger.info("General inventory query, fetching low stock items.")
        low_stock_items = await fetch_low_stock_products(threshold=50) # Default threshold
        if low_stock_items:
            items_to_report = low_stock_items
            response_summary = f"Currently {len(low_stock_items)} products have low stock (below 50 units). Please replenish."
            # For brevity, we don't list them all in the summary string here, they are in `data`.
        else: # Corresponds to if low_stock_items
            response_summary = "Currently all products have stock above the warning threshold (50 units)."
            # items_to_report will remain empty
            
    # If LLM is available, it could rephrase `response_summary` or interpret `items_to_report`
    if llm:
        prompt = f"""
        User inventory query: "{query}"
        Retrieved inventory information/summary: "{response_summary}"
        Relevant product data (JSON):
        {str(items_to_report[:3])} ... (showing first 3 items for brevity if many)

        Please generate a natural answer in English based on the user query and the data above.
        """
        try:
            llm_response = llm.invoke(prompt)
            final_answer = llm_response.content
            logger.info(f"LLM generated inventory answer: {final_answer}")
            return items_to_report, final_answer
        except Exception as e:
            logger.error(f"LLM invocation failed for inventory query summarization: {e}", exc_info=True)
            # Fallback to pre-LLM summary if LLM fails during try block
            return items_to_report, response_summary
    else: # This is the corrected else for 'if llm:'
        return items_to_report, response_summary

async def get_inventory_check_response() -> tuple[List[Dict[str, Any]], str]:
    # This is a simplified version, assuming a general "check inventory" means "show low stock"
    # Kept for backward compatibility or direct calls if any.
    low_stock_items = await fetch_low_stock_products(threshold=50)
    if low_stock_items:
        answer = f"Found {len(low_stock_items)} low stock products (below 50 units):"
        # for item in low_stock_items:
        #     answer += f"\n- {item['product_name']} (ID: {item['product_id']}), 当前库存: {item['stock_level']}"
    else:
        answer = "All products have stock above the warning threshold (50 units)."
    return low_stock_items, answer

async def get_daily_sales_report_response_from_agent() -> tuple[str, Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Generates a daily sales report summary using the report generation utility.
    (This is part of the original  logic)
    """
    logger.info("Generating daily sales report for default .")
    # This uses the existing report generation logic.
    # If LLM is available, it could enhance the summary.
    summary, report_data, chart_data = await generate_daily_sales_summary_report(llm=llm) # Pass LLM if needed by report
    
    # The summary from generate_daily_sales_summary_report might already be LLM-generated or template-based.
    # If not, and LLM is available here, we could try to enhance it.
    # For now, we assume the summary is good as is.
    
    return summary, report_data, chart_data

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

# Example of how to call (for testing or direct use if needed)
# async def main():
#     initialize_app_state()
#     # Test default  query
#     response = await get_answer_from("What are today's sales figures?", query_type="sales")
#     print("Default  Sales Query Response:", response)

#     # Simulate a RAG datasource
#     mock_rag_datasource = {"id": 2, "name": "My Test RAG Source", "type": "knowledge_base"}
#     # Ensure you have some files uploaded and processed for this datasource_id in your DB
#     # and the UPLOAD_DIR contains them.
#     # response_rag = await get_answer_from("What is the main topic of the documents?", active_datasource=mock_rag_datasource)
#     # print("RAG Query Response:", response_rag)

#     # Simulate a SQL Table datasource
#     # mock_sql_datasource = {"id": 3, "name": "My CSV Data", "type": "sql_table_from_file", "db_table_name": "dstable_3_my_data_xyz123"}
#     # response_sql = await get_answer_from("How many rows in the table?", active_datasource=mock_sql_datasource)
#     # print("SQL Table Query Response:", response_sql)


# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(main())