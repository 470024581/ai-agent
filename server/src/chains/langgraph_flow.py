"""
Intelligent Data Analysis Flow Based on LangGraph
"""
import json
import time
import uuid
import asyncio
import re
import os
from typing import Dict, Any, List, Optional, TypedDict
import logging
import requests
from langgraph.graph import StateGraph
from langchain_community.utilities import SQLDatabase
from ..agents.intelligent_agent import llm, perform_rag_query, get_answer_from_sqltable_datasource, get_query_from_sqltable_datasource
import re
import difflib
from ..models.data_models import WorkflowEvent, WorkflowEventType, NodeStatus, DataSourceType
from ..database.db_operations import get_active_datasource
from ..agents.intelligent_agent import DB_URI
# Removed unused import

logger = logging.getLogger(__name__)

# ==================== Streaming LLM Utility ====================

async def stream_llm_response(prompt: str, execution_id: str, node_id: str = "llm_processing_node") -> str:
    """Stream LLM response token by token via WebSocket.
    
    Args:
        prompt: The prompt to send to LLM
        execution_id: Execution ID for WebSocket routing
        node_id: Node ID generating the stream (default: llm_processing_node)
        
    Returns:
        Complete response text
    """
    from ..websocket.websocket_manager import websocket_manager
    
    if not llm:
        logger.warning("LLM not available for streaming")
        return "LLM not initialized. Cannot generate streaming response."
    
    try:
        full_response = ""
        
        # Check if LLM supports streaming
        if hasattr(llm, 'astream'):
            logger.info(f"Starting LLM token streaming for execution {execution_id}")
            
            # Stream tokens
            async for chunk in llm.astream(prompt):
                # Extract token from chunk
                token = ""
                if hasattr(chunk, 'content'):
                    token = chunk.content
                elif isinstance(chunk, str):
                    token = chunk
                else:
                    token = str(chunk)
                
                if token:
                    full_response += token
                    # Send token via WebSocket
                    await websocket_manager.stream_token(
                        execution_id=execution_id,
                        token=token,
                        node_id=node_id,
                        stream_complete=False
                    )
            
            # Send stream complete signal
            await websocket_manager.stream_token(
                execution_id=execution_id,
                token="",
                node_id=node_id,
                stream_complete=True
            )
            
            logger.info(f"LLM streaming completed for execution {execution_id}. Total length: {len(full_response)}")
            
        else:
            # Fallback to non-streaming
            logger.warning("LLM does not support streaming, falling back to invoke()")
            response = llm.invoke(prompt)
            
            if hasattr(response, 'content'):
                full_response = response.content
            elif isinstance(response, str):
                full_response = response
            else:
                full_response = str(response)
        
        return full_response
        
    except Exception as e:
        logger.error(f"Error in LLM streaming: {e}", exc_info=True)
        # Send error signal
        await websocket_manager.stream_token(
            execution_id=execution_id,
            token=f"[Error: {str(e)}]",
            node_id=node_id,
            stream_complete=True
        )
        return f"Error generating response: {str(e)}"

async def _stream_text_as_tokens(text: str, execution_id: str, node_id: str = "llm_processing_node", chunk_size: int = 5):
    """Simulate token streaming by splitting text into chunks and sending via WebSocket.
    
    Args:
        text: Complete text to stream
        execution_id: Execution ID for WebSocket routing
        node_id: Node ID generating the stream
        chunk_size: Number of characters per chunk (default: 5 for word-like chunks)
    """
    from ..websocket.websocket_manager import websocket_manager
    import asyncio
    
    if not text or not execution_id:
        return
    
    logger.debug(f"Starting simulated token streaming for execution {execution_id}, text length: {len(text)}")
    
    # Split text into chunks (simulate tokens)
    words = text.split()
    current_chunk = ""
    
    for word in words:
        current_chunk = word + " "
        
        # Send chunk as token
        await websocket_manager.stream_token(
            execution_id=execution_id,
            token=current_chunk,
            node_id=node_id,
            stream_complete=False
        )
        
        # Small delay to simulate real-time generation (10ms per word)
        await asyncio.sleep(0.01)
    
    # Send stream complete signal
    await websocket_manager.stream_token(
        execution_id=execution_id,
        token="",
        node_id=node_id,
        stream_complete=True
    )
    
    logger.debug(f"Completed simulated token streaming for execution {execution_id}")

# ==================== HITL (Human-in-the-Loop) Utilities ====================

class HITLPausedException(Exception):
    """Exception raised when execution is paused for HITL"""
    def __init__(self, execution_id: str, node_name: str, reason: str, state: dict):
        self.execution_id = execution_id
        self.node_name = node_name
        self.reason = reason
        self.state = state
        super().__init__(f"Execution {execution_id} paused at node {node_name}")

class HITLInterruptedException(Exception):
    """Exception raised when execution is interrupted for HITL"""
    def __init__(self, execution_id: str, node_name: str, reason: str, state: dict):
        self.execution_id = execution_id
        self.node_name = node_name
        self.reason = reason
        self.state = state
        super().__init__(f"Execution {execution_id} interrupted at node {node_name}")

# GraphState definition moved to top
# GraphState definition - Updated for new workflow
class GraphState(TypedDict):
    """Define graph state for new RAG mandatory + SQL-Agent optional workflow"""
    # === Basic fields ===
    user_input: str
    datasource: Dict[str, Any]
    execution_id: str  # For WebSocket routing and token streaming
    
    # === RAG path fields ===
    retrieved_documents: Optional[List[Any]]  # Retrieved Top 10 documents
    reranked_documents: Optional[List[Any]]  # Top 3 documents after reranking
    rag_answer: Optional[str]  # RAG generated answer
    rag_source_documents: Optional[List[Any]]  # RAG source documents
    retrieval_success: bool  # Whether retrieval was successful
    rerank_success: bool  # Whether reranking was successful
    rag_success: bool  # Whether RAG answer generation was successful

    # === Router fields ===
    need_sql_agent: bool  # Whether SQL-Agent is needed
    router_reasoning: Optional[str]  # Router decision reasoning

    # === SQL-Agent fields ===
    sql_agent_answer: Optional[str]  # SQL-Agent answer
    executed_sqls: Optional[List[str]]  # List of executed SQL queries
    agent_intermediate_steps: Optional[List[Any]]  # Agent intermediate steps
    sql_execution_success: bool  # Whether SQL execution was successful

    # === Chart fields ===
    chart_suitable: bool  # Whether data is suitable for chart generation
    chart_config: Optional[Dict[str, Any]]  # Chart configuration
    chart_data: Optional[List[Dict]]  # Chart data
    chart_type: Optional[str]  # Chart type
    chart_error: Optional[str]  # Chart error information
    
    # === Structured data ===
    structured_data: Optional[Dict[str, Any]]  # Query result data
    
    # === Final output ===
    answer: str  # Final natural language answer
    final_answer: Optional[str]  # Final integrated answer
    
    # === Quality and error ===
    quality_score: int
    retry_count: int
    error: Optional[str]
    
    # === HITL (Human-in-the-Loop) ===
    hitl_status: Optional[str]  # "paused", "interrupted", "resumed", None
    hitl_node: Optional[str]  # Node where HITL action occurred
    hitl_reason: Optional[str]  # Reason for HITL action
    hitl_parameters: Optional[Dict[str, Any]]  # Parameters for adjustment
    hitl_timestamp: Optional[str]  # Timestamp of HITL action
    
    # === Node outputs tracking ===
    node_outputs: Dict[str, Any]  # Track outputs from each node
    
    # === Legacy fields (for backward compatibility) ===
    query_type: Optional[str]  # "sql" or "rag" - deprecated but kept for compatibility

# LangGraph native interrupt implementation
def check_interrupt_status(state: GraphState) -> str:
    """Check if execution should be interrupted"""
    execution_id = state.get("execution_id")
    if not execution_id:
        return "continue"
    
    from ..websocket.websocket_manager import websocket_manager
    
    # Check if execution is interrupted
    if (execution_id in websocket_manager.hitl_interrupted_executions or 
        execution_id in websocket_manager.execution_cancelled):
        logger.info(f"Execution {execution_id} is interrupted, returning interrupt signal")
        return "interrupt"
    
    return "continue"

def interrupt_node(state: GraphState) -> GraphState:
    """Node that handles interrupt - saves state and stops execution"""
    execution_id = state.get("execution_id")
    logger.info(f"Interrupt node called for execution {execution_id}")
    
    # Save current state
    set_execution_final_state(execution_id, state)
    
    # Create interrupted state
    interrupted_state = state.copy()
    interrupted_state["hitl_status"] = "interrupted"
    interrupted_state["hitl_reason"] = "user_interrupted"
    interrupted_state["hitl_timestamp"] = time.time()
    
    logger.info(f"Execution {execution_id} interrupted, state saved")
    return interrupted_state

def check_hitl_action(state: Dict[str, Any], node_name: str) -> Optional[str]:
    """
    Check if HITL action should be taken at this node
    
    Returns:
        "pause", "interrupt", or None
    """
    # This would be called by external HITL controller
    # For now, return None (no automatic HITL actions)
    return None

def apply_hitl_parameters(state: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply HITL parameter adjustments to state
    
    Args:
        state: Current workflow state
        parameters: Parameters to apply
        
    Returns:
        Updated state with applied parameters
    """
    updated_state = state.copy()
    
    # Apply parameter updates
    for key, value in parameters.items():
        if key in updated_state:
            updated_state[key] = value
            logger.info(f"Applied HITL parameter update: {key} = {value}")
    
    # Update HITL status
    updated_state["hitl_status"] = "resumed"
    updated_state["hitl_parameters"] = parameters
    updated_state["hitl_timestamp"] = time.time()
    
    return updated_state

# ==================== Graph State Definition ====================

# Remove duplicate GraphState definition


def _extract_content(response) -> str:
    """Extract content from LLM response"""
    if hasattr(response, 'content'):
        return response.content.strip()
    elif isinstance(response, str):
        return response.strip()
    else:
        return str(response).strip()

def router_node(state: GraphState) -> GraphState:
    """Router Node: Determine whether to trigger SQL-Agent"""
    user_input = state["user_input"]
    rag_answer = state.get("rag_answer", "")
    reranked_documents = state.get("reranked_documents", [])
    
    logger.info(f"Router Node - Analyzing query: {user_input}")
    
    if not llm:
        logger.warning("LLM not available, using fallback rule-based router decision")
        return _fallback_router_decision(state)
    
    try:
        # Lightweight heuristics to bias decision without hardcoding logic
        heuristics = _router_heuristics(user_input, reranked_documents)
        if heuristics.get("strong_llm_only", False):
            # Strong signals indicate documentation-style Q&A; skip SQL-Agent
            logger.info(f"Router heuristics suggest LLM-only (reason: {heuristics.get('reason', 'n/a')})")
            return {
                **state,
                "need_sql_agent": False,
                "router_reasoning": f"Heuristic decision: {heuristics.get('reason', 'conceptual and high-confidence RAG doc')}",
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "router": {
                        "status": "completed",
                        "decision": "llm_only",
                        "reasoning": heuristics.get('reason', ''),
                        "timestamp": time.time()
                    }
                }
            }

        prompt = f"""
        User question: {user_input}
        RAG preliminary answer: {rag_answer}
        
        Determine whether to query structured database.
        
        Scenarios requiring SQL:
        - Numerical statistics (sales, quantities, averages)
        - Time series analysis (trends, comparisons)
        - Data aggregation and summarization
        - Rankings and sorting
        
        Scenarios not requiring SQL:
        - Concept explanations and definitions
        - Design principles and methodologies
        - Document content queries
        
        Context signals (for your reference, not mandatory):
        - text_intent_prefer_llm: {heuristics.get('text_intent_prefer_llm')}
        - top1_doc: {heuristics.get('top1_source')}
        - top1_ext: {heuristics.get('top1_ext')}
        - top1_ce_score: {heuristics.get('top1_ce_score')}
        - prefer_llm_hint: {heuristics.get('prefer_llm_hint')}
        
        Return JSON:
        {{
            "need_sql": true/false,
            "reasoning": "decision reasoning"
        }}
        """
        
        response = llm.invoke(prompt)
        decision = _parse_json_response(response)
        # Post-override: if LLM prefers SQL but heuristics strongly suggest LLM-only, override
        if decision.get("need_sql", False) and heuristics.get("prefer_llm_override", False):
            decision["need_sql"] = False
            decision["reasoning"] = f"Heuristic override: {heuristics.get('reason', '')}"
        
        logger.info(f"Router decision: need_sql={decision['need_sql']}")
        
        return {
            **state,
            "need_sql_agent": decision["need_sql"],
            "router_reasoning": decision["reasoning"],
            "node_outputs": {
                **state.get("node_outputs", {}),
                "router": {
                    "status": "completed",
                    "decision": "sql_agent" if decision["need_sql"] else "llm_only",
                    "reasoning": decision["reasoning"],
                    "timestamp": time.time()
                }
            }
        }
    except Exception as e:
        logger.error(f"Router failed: {e}, using fallback")
        return _fallback_router_decision(state)

def _fallback_router_decision(state: GraphState) -> GraphState:
    """Fallback: Rule-based decision using keywords"""
    user_input = state["user_input"].lower()
    reranked_documents = state.get("reranked_documents", [])
    # Positive indicators for SQL
    sql_keywords = [
        "sales", "quantity", "statistics", "trend", "chart", "how many", "average", "total", "summary", "ranking",
        "同比", "环比", "统计", "趋势", "时间", "区间", "top", "sum", "avg", "平均", "总量", "合计", "总数"
    ]
    # Indicators for conceptual/document Q&A
    conceptual_keywords = [
        "describe", "explain", "what is", "what are", "overview", "architecture", "schema", "relationship",
        "key feature", "features", "benefits", "advantages", "pros", "cons", "highlights",
        "架构", "关系", "原理", "概念", "文档", "定义", "说明", "介绍", "特点", "特性", "关键特性", "优势", "亮点", "概览"
    ]
    has_sql_signals = any(kw in user_input for kw in sql_keywords)
    has_concept_signals = any(kw in user_input for kw in conceptual_keywords)
    # Heuristic override from top documents
    h = _router_heuristics(state.get("user_input", ""), reranked_documents)
    prefer_llm_override = h.get("prefer_llm_override", False)
    need_sql = (has_sql_signals and not has_concept_signals) and not prefer_llm_override
    
    logger.info(f"Fallback router decision: need_sql={need_sql}")
    
    return {
        **state,
        "need_sql_agent": need_sql,
        "router_reasoning": "Fallback rule-based decision",
        "node_outputs": {
            **state.get("node_outputs", {}),
            "router": {
                "status": "completed",
                "decision": "sql_agent" if need_sql else "llm_only",
                "reasoning": "Fallback rule-based decision",
                "timestamp": time.time()
            }
        }
    }

def _router_heuristics(user_input: str, reranked_documents: list) -> dict:
    """Compute lightweight, general heuristics to bias router decision.
    Returns a dict with fields:
      - text_intent_prefer_llm: bool
      - top1_source: str | None
      - top1_ext: str | None
      - top1_ce_score: float | None
      - prefer_llm_hint: bool
      - strong_llm_only: bool
      - reason: str
    """
    ui = (user_input or "").lower()
    conceptual_keywords = [
        "describe", "explain", "what is", "what are", "overview", "architecture", "schema", "relationship",
        "key feature", "features", "benefits", "advantages", "pros", "cons", "highlights",
        "架构", "关系", "原理", "概念", "文档", "定义", "说明", "介绍", "特点", "特性", "关键特性", "优势", "亮点", "概览"
    ]
    sql_keywords = [
        "统计", "趋势", "同比", "环比", "top", "sum", "avg", "平均", "总量", "合计", "总数", "时间", "区间",
        "sales", "quantity", "statistics", "trend", "chart", "how many", "average", "total", "summary", "ranking"
    ]
    text_intent_prefer_llm = any(kw in ui for kw in conceptual_keywords) and not any(kw in ui for kw in sql_keywords)
    top1 = reranked_documents[0] if reranked_documents else None
    top2 = reranked_documents[1] if len(reranked_documents) > 1 else None
    top3 = reranked_documents[2] if len(reranked_documents) > 2 else None
    top1_meta = getattr(top1, "metadata", {}) if top1 else {}
    import os as _os
    src = (top1_meta.get("source") or top1_meta.get("file_path") or "") if top1 else ""
    ext = _os.path.splitext(src)[1].lower() if src else None
    ce_score = top1_meta.get("ce_score") if isinstance(top1_meta, dict) else None
    doc_like_exts = {".md", ".docx", ".txt", ".pdf"}
    doc_like = ext in doc_like_exts if ext else False
    ce_ok = (float(ce_score) >= 0.6) if ce_score is not None else False

    # Aggregate top-3 doc signals
    def _doc_like_with_ce(d):
        if not d:
            return False
        m = getattr(d, "metadata", {}) or {}
        p = m.get("source") or m.get("file_path") or ""
        e = _os.path.splitext(p)[1].lower() if p else None
        s = m.get("ce_score")
        return (e in doc_like_exts) and (s is not None) and (float(s) >= 0.7)

    doc_like_topk = sum(1 for d in (top1, top2, top3) if _doc_like_with_ce(d))

    has_stats_intent = any(kw in ui for kw in sql_keywords)
    strong_top1 = bool(doc_like and (ce_score is not None) and (float(ce_score) >= 0.8))
    strong_llm_only = bool(text_intent_prefer_llm and strong_top1)
    prefer_llm_override = (not has_stats_intent) and (strong_top1 or doc_like_topk >= 2)

    prefer_llm_hint = bool(text_intent_prefer_llm or (doc_like and ce_ok) or doc_like_topk >= 2)

    reason_parts = []
    if text_intent_prefer_llm:
        reason_parts.append("conceptual intent detected")
    if doc_like:
        reason_parts.append(f"top1 doc-type {ext}")
    if ce_score is not None:
        reason_parts.append(f"ce_score={ce_score}")
    if doc_like_topk >= 2:
        reason_parts.append("top3_doc_like>=2")

    return {
        "text_intent_prefer_llm": text_intent_prefer_llm,
        "top1_source": _os.path.basename(src) if src else None,
        "top1_ext": ext,
        "top1_ce_score": ce_score,
        "prefer_llm_hint": prefer_llm_hint,
        "strong_llm_only": strong_llm_only,
        "prefer_llm_override": prefer_llm_override,
        "reason": ", ".join(reason_parts) or ""
    }

def _parse_json_response(response) -> dict:
    """Parse LLM's JSON response"""
    try:
        import json
        if hasattr(response, 'content'):
            response_text = response.content
        else:
            response_text = str(response)
        
        # Find JSON part
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            return json.loads(json_str)
        else:
            raise ValueError("No valid JSON found in response")
    except Exception as e:
        logger.warning(f"Failed to parse JSON response: {e}")
        # Return default value
        return {"need_sql": False, "reasoning": "Failed to parse response"}


def extract_table_names_from_rag(rag_answer: str, user_input: str) -> List[str]:
    """Extract relevant table names from RAG answer and user input"""
    import re
    
    # Common table names in the system
    known_tables = [
        'customers', 'products', 'orders', 'sales', 'inventory',
        'dim_customer', 'dim_product', 'dwd_sales_detail', 'dwd_inventory_detail',
        'dws_sales_cube', 'dws_inventory_cube'
    ]
    
    # Extract table names from RAG answer and user input
    text_to_search = f"{rag_answer} {user_input}".lower()
    relevant_tables = []
    
    for table in known_tables:
        if table.lower() in text_to_search:
            relevant_tables.append(table)
    
    # Additional pattern matching for table references
    table_patterns = [
        r'\b(sales?|sale)\b',
        r'\b(product|products?)\b', 
        r'\b(customer|customers?)\b',
        r'\b(order|orders?)\b',
        r'\b(inventory|stock)\b'
    ]
    
    for pattern in table_patterns:
        if re.search(pattern, text_to_search):
            # Map patterns to actual table names
            if 'sales' in pattern or 'sale' in pattern:
                if 'dws_sales_cube' not in relevant_tables:
                    relevant_tables.append('dws_sales_cube')
                if 'sales' not in relevant_tables:
                    relevant_tables.append('sales')
            elif 'product' in pattern:
                if 'dim_product' not in relevant_tables:
                    relevant_tables.append('dim_product')
                if 'products' not in relevant_tables:
                    relevant_tables.append('products')
            elif 'customer' in pattern:
                if 'dim_customer' not in relevant_tables:
                    relevant_tables.append('dim_customer')
                if 'customers' not in relevant_tables:
                    relevant_tables.append('customers')
            elif 'order' in pattern:
                if 'orders' not in relevant_tables:
                    relevant_tables.append('orders')
            elif 'inventory' in pattern or 'stock' in pattern:
                if 'dws_inventory_cube' not in relevant_tables:
                    relevant_tables.append('dws_inventory_cube')
                if 'inventory' not in relevant_tables:
                    relevant_tables.append('inventory')
    
    logger.info(f"Extracted relevant tables from RAG: {relevant_tables}")
    return relevant_tables


async def sql_agent_node(state: GraphState) -> GraphState:
    """SQL Agent Node: Use ReAct mode to autonomously explore database"""
    user_input = state["user_input"]
    rag_answer = state.get("rag_answer", "")
    datasource = state["datasource"]
    execution_id = state.get("execution_id", "unknown")
    
    logger.info(f"SQL Agent Node - Starting ReAct exploration for: {user_input}")
    
    try:
        # 1. Extract relevant table names from RAG answer
        relevant_tables = extract_table_names_from_rag(rag_answer, user_input)
        
        # 2. Initialize database connection with table restrictions
        if datasource['type'] == DataSourceType.DEFAULT.value:
            # Use default database with RAG-extracted table restrictions
            include_tables = relevant_tables if relevant_tables else None
            if include_tables:
                logger.info(f"SQL Agent - Using RAG-extracted tables: {include_tables}")
            else:
                logger.warning("SQL Agent - No relevant tables found in RAG answer, exploring all tables")
        else:
            table_name = datasource.get("db_table_name")
            if not table_name:
                # If no table name specified, use RAG-extracted tables
                include_tables = relevant_tables if relevant_tables else None
                if include_tables:
                    logger.info(f"SQL Agent - Using RAG-extracted tables: {include_tables}")
                else:
                    logger.warning("SQL Agent - No relevant tables found in RAG answer, exploring all tables")
            else:
                include_tables = [table_name]
        
        db = SQLDatabase.from_uri(
            f"sqlite:///{os.path.abspath('data/smart.db')}",
            include_tables=include_tables,
            sample_rows_in_table_info=3
        )
        
        # 2. Create SQL Toolkit
        from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
        
        toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        tools = toolkit.get_tools()
        
        # 3. Manual ReAct Loop Implementation
        logger.info("Starting manual ReAct SQL exploration...")
        
        # Step 1: List all tables
        list_tables_tool = None
        for tool in tools:
            if tool.name == 'sql_db_list_tables':
                list_tables_tool = tool
                break
        
        tables_result = ""
        if list_tables_tool:
            try:
                tables_result = list_tables_tool.invoke({})
                logger.info(f"Found tables: {tables_result}")
            except Exception as e:
                logger.error(f"Error listing tables: {e}")
                tables_result = "Error listing tables"
        
        # Step 2: Get table structure information
        executed_sqls = []
        structured_data = None
        
        # Get schema information for relevant tables
        schema_info = ""
        try:
            # Get structure for sales-related tables
            sales_tables = ['sales', 'dws_sales_cube', 'dwd_sales_detail']
            for table in sales_tables:
                if table in tables_result:
                    try:
                        table_schema = db.get_table_info([table])
                        schema_info += f"\n{table} table structure:\n{table_schema}\n"
                    except Exception as e:
                        logger.warning(f"Error getting schema for table {table}: {e}")
                        logger.warning(f"Table {table} schema error details: {type(e).__name__}: {str(e)}")
                        import traceback
                        logger.debug(f"Full traceback: {traceback.format_exc()}")
                        # Fallback: use manual schema info
                        schema_info += f"\n{table} table structure: (schema info unavailable - {type(e).__name__}: {str(e)})\n"
            
            # Add specific column information for dws_sales_cube
            if 'dws_sales_cube' in tables_result:
                schema_info += f"""
IMPORTANT: dws_sales_cube table columns:
- sale_date (DATE): Sales date
- product_id (TEXT): Product identifier  
- category (TEXT): Product category (NOT customer_type)
- price_range (TEXT): Price range classification
- sale_value_range (TEXT): Sale value range classification
- transaction_count (INTEGER): Number of transactions
- total_quantity_sold (INTEGER): Total quantity sold
- total_amount (DECIMAL): Total revenue amount
- avg_transaction_value (DECIMAL): Average transaction value
- unique_products (INTEGER): Number of unique products
- etl_batch_id (TEXT): ETL batch identifier
- etl_timestamp (TIMESTAMP): ETL processing timestamp

NOTE: There is NO 'customer_type' column in dws_sales_cube table. Use 'category' instead.
"""
            
            # Add table relationship information
            schema_info += f"""
TABLE RELATIONSHIPS AND JOIN RULES:
1. dws_sales_cube table:
   - Contains aggregated sales data by product, customer and date
   - Has product_id field for joining with product tables
   - Has customer_id field for joining with customer tables
   - CAN be directly joined with dim_customer table using customer_id

2. dim_customer table:
   - Contains customer information including customer_type
   - Has customer_id field
   - CAN be joined with dws_sales_cube table using customer_id

3. dim_product table:
   - Contains product information
   - Has product_id field (can join with dws_sales_cube)
   - Has category field (same as dws_sales_cube.category)

4. sales table:
   - Contains individual sales transactions
   - Has product_id field (can join with dws_sales_cube)
   - Has customer_id field (can join with dim_customer)

5. dwd_sales_detail table:
   - Contains detailed sales transactions
   - Has both product_id and customer_id fields
   - Can be joined with dws_sales_cube and dim_customer
   - Has total_amount field for sales calculations

6. orders table:
   - Contains order information
   - Has customer_id field
   - Can be joined with dim_customer

JOIN RESTRICTIONS:
- dws_sales_cube CAN be directly joined with dim_customer using customer_id
- sales table CAN be used as bridge (has customer_id field)
- dwd_sales_detail table can also be used as bridge
- Example: dwd_sales_detail JOIN dim_customer ON dwd_sales_detail.customer_id = dim_customer.customer_id
- For aggregated sales by customer_type, aggregate dwd_sales_detail table first, then join
"""
        except Exception as e:
            logger.warning(f"Error getting schema info: {e}")
        
        # Build query prompt
        query_prompt = f"""
        User question: {user_input}
        
        Background knowledge (from knowledge base):
        {rag_answer}
        
        Available tables in database: {tables_result}
        
        Table structure information: {schema_info}
        
        This is a SQLite database. Please generate a SQL query based on the user question and available tables.
        
        CRITICAL RULES - MUST FOLLOW:
        1. ONLY use column names that exist in the table structure information above
        2. NEVER use 'customer_type' - it does NOT exist in dws_sales_cube table
        3. Use 'category' instead of 'customer_type' for product categorization
        4. Verify every column name against the table structure before using it
        5. dws_sales_cube CAN be joined with dim_customer using customer_id field
        6. Use appropriate JOIN conditions based on available fields
        7. Check table relationships before creating JOIN conditions
        8. IMPORTANT: For sales amount queries, use 'total_amount' in dws_sales_cube
        9. IMPORTANT: For quantity queries, use 'total_quantity_sold' NOT 'quantity_sold' in dws_sales_cube
        10. IMPORTANT: For date filtering, use 'sale_date' column with strftime() function
        
        Technical Instructions:
        - Use SQLite syntax
        - Return ONLY ONE SQL query statement, no other explanations or multiple statements
        - CRITICAL: Generate exactly ONE SELECT statement, not multiple statements
        - SQLite doesn't support EXTRACT() function, use strftime() instead
        - SQLite doesn't support YEAR() function, use strftime('%Y', date_column) instead
        - SQLite doesn't support MONTH() function, use strftime('%m', date_column) instead
        - If user asks for table list, use: SELECT name FROM sqlite_master WHERE type='table';
        - For date-related queries, use strftime() function with proper syntax: strftime('%Y-%m', date_column)
        - SQL clause order: SELECT ... FROM ... WHERE ... GROUP BY ... ORDER BY ...
        - Example: SELECT strftime('%Y-%m', sale_date) as Month, SUM(total_amount) as Sales FROM dws_sales_cube WHERE strftime('%Y', sale_date) = '2025' GROUP BY Month ORDER BY Month;
        - Example for pie chart by category: SELECT category, SUM(total_amount) as sales FROM dws_sales_cube WHERE strftime('%Y-%m', sale_date) BETWEEN '2025-07' AND '2025-09' GROUP BY category ORDER BY sales DESC;
        - IMPORTANT: strftime() function requires two parameters: format string and date column
        - IMPORTANT: Do not use backslashes in table or column names, use underscores directly
        - IMPORTANT: For SELECT * queries, use: SELECT * FROM table_name (not table_name.*)
        - IMPORTANT: Do NOT include comments, explanations, or multiple SQL statements
        
        VALIDATION CHECKLIST:
        - [ ] All column names exist in the table structure
        - [ ] No 'customer_type' column used in dws_sales_cube (use 'category' instead)
        - [ ] For sales amount: use 'total_amount' in dws_sales_cube
        - [ ] For quantity: use 'total_quantity_sold' NOT 'quantity_sold' in dws_sales_cube
        - [ ] JOIN conditions use existing fields from both tables
        - [ ] dws_sales_cube JOIN with dim_customer uses customer_id field
        - [ ] SQLite syntax used correctly
        - [ ] Query follows proper SQL clause order
        - [ ] Date filtering uses strftime() function correctly
        """
        
        try:
            # Use LLM to generate SQL query
            response = await llm.ainvoke(query_prompt)
            sql_query = response.content.strip() if hasattr(response, 'content') else str(response).strip()
            
            # Clean SQL query (remove possible markdown markers and escape characters)
            if sql_query.startswith('```sql'):
                sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
            elif sql_query.startswith('```'):
                sql_query = sql_query.replace('```', '').strip()
            
            # Remove escape characters that might be added by LLM
            sql_query = sql_query.replace('\\_', '_').replace('\\*', '*').replace('\\', '')
            
            logger.info(f"Generated SQL query: {sql_query}")

            # Validate and auto-correct table names using whitelist from discovered tables
            try:
                # Extract table names referenced in the SQL (simple regex over FROM/JOIN)
                referenced = set()
                for m in re.finditer(r"\b(?:FROM|JOIN)\s+([\w\.]+)", sql_query, re.IGNORECASE):
                    # strip aliases and schema
                    token = m.group(1)
                    base = token.split('.')[-1]
                    referenced.add(base)

                # Build whitelist from actual tables_result string (comma/space separated)
                whitelist = set()
                if isinstance(tables_result, str):
                    # tables_result like: "dim_product, dwd_sales_detail, dws_sales_cube, ..."
                    for t in re.split(r"[^A-Za-z0-9_]+", tables_result):
                        if t:
                            whitelist.add(t)

                # Known preferred names mapping to avoid layer mix-up
                canonical = {
                    'dwd_sales_cube': 'dws_sales_cube',
                }

                corrected = sql_query
                for name in referenced:
                    target = name
                    if name in canonical:
                        target = canonical[name]
                    elif whitelist and name not in whitelist:
                        # fuzzy match to closest table in whitelist
                        candidates = difflib.get_close_matches(name, list(whitelist), n=1, cutoff=0.8)
                        if candidates:
                            target = candidates[0]
                    # Apply replacement only if changed
                    if target != name:
                        logger.warning(f"Auto-correcting table name in SQL: {name} -> {target}")
                        corrected = re.sub(rf"\b{name}\b", target, corrected)

                if corrected != sql_query:
                    sql_query = corrected
                    logger.info(f"Corrected SQL query: {sql_query}")
            except Exception as v_err:
                logger.warning(f"Table name validation skipped due to error: {v_err}")
            
            # Sanitize to a single SQL statement and enforce basic clause rules
            def _sanitize_single_select_sql(q: str) -> str:
                # Keep only the first statement up to the first semicolon
                semi = q.find(';')
                if semi != -1:
                    q = q[:semi + 1]
                # Remove any trailing content after the semicolon (already truncated)
                # Normalize whitespace
                q = " ".join(q.split())
                # Ensure query ends with a single semicolon
                if not q.endswith(';'):
                    q = q + ';'
                # Optional: very light guard to avoid JOIN after WHERE
                # If ' where ' appears before ' join ', keep as-is; otherwise fine
                return q

            sanitized = _sanitize_single_select_sql(sql_query)
            if sanitized != sql_query:
                logger.info(f"Sanitized SQL query to single statement: {sanitized}")
                sql_query = sanitized

            # Execute query
            if sql_query.upper().startswith('SELECT'):
                sql_query_tool = None
                for tool in tools:
                    if tool.name == 'sql_db_query':
                        sql_query_tool = tool
                        break
                
                if sql_query_tool:
                    try:
                        query_result = sql_query_tool.invoke({"query": sql_query})
                        executed_sqls.append(sql_query)
                        structured_data = _parse_agent_query_result(query_result)
                        logger.info(f"Query executed successfully, result length: {len(str(query_result))}")
                        logger.info(f"Query result preview: {str(query_result)[:500]}...")
                    except Exception as e:
                        logger.error(f"Error executing SQL query: {e}")
                        query_result = f"Error executing query: {e}"
                else:
                    query_result = "SQL query tool not found"
            else:
                query_result = "Generated query is not a SELECT statement"
                
        except Exception as e:
            logger.error(f"Error generating SQL query: {e}")
            query_result = f"Error generating query: {e}"
        
        # Build final answer
        final_answer = f"""
        Database exploration results:
        
        Available tables: {tables_result}
        
        Generated query: {sql_query if 'sql_query' in locals() else 'N/A'}
        
        Query result: {query_result if 'query_result' in locals() else 'N/A'}
        """
        
        # Ensure variables are in scope
        if 'sql_query' not in locals():
            sql_query = "N/A"
        if 'query_result' not in locals():
            query_result = "N/A"
        
        # Check if chart generation is suitable based on user input and data
        chart_suitable = False
        if user_input:
            # Check if user input contains chart-related keywords
            chart_keywords = ["chart", "pie", "bar", "line", "graph", "visualization", "proportion", "distribution", "trend"]
            has_chart_intent = any(keyword.lower() in user_input.lower() for keyword in chart_keywords)
            
            # Check if data is suitable for charting
            if has_chart_intent:
                if structured_data and structured_data.get("rows") and len(structured_data.get("rows", [])) >= 2:
                    chart_suitable = True
                    logger.info(f"Chart generation suitable: user intent={has_chart_intent}, data rows={len(structured_data.get('rows', []))}")
                else:
                    # Even if SQL failed, if user wants chart, try to generate a simple chart
                    chart_suitable = True
                    logger.info(f"Chart generation suitable despite SQL failure: user intent={has_chart_intent}, will attempt chart generation")
            else:
                logger.info(f"Chart generation not suitable: user intent={has_chart_intent}")
            
        logger.info(f"SQL Agent completed - Executed {len(executed_sqls)} queries, chart_suitable={chart_suitable}")
        
        return {
                **state,
            "sql_agent_answer": final_answer,
            "executed_sqls": executed_sqls,
                "structured_data": structured_data,
            "chart_suitable": chart_suitable,
            "agent_intermediate_steps": [{"step": "manual_react", "tables": tables_result, "query": sql_query, "result": query_result}],
            "sql_execution_success": True,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                "sql_agent": {
                        "status": "completed",
                    "queries_count": len(executed_sqls),
                    "steps_count": 1,
                    "chart_suitable": chart_suitable,
                    "timestamp": time.time()
                }
            }
        }
        
    except Exception as e:
        logger.error(f"SQL Agent failed: {e}", exc_info=True)
        return {
            **state,
            "sql_agent_answer": "",
            "sql_execution_success": False,
            "sql_error": str(e),
            "chart_suitable": False,
            "chart_error": f"SQL Agent failed: {str(e)}",
            "node_outputs": {
                **state.get("node_outputs", {}),
                "sql_agent": {
                    "status": "error",
                    "error": str(e),
                    "timestamp": time.time()
                }
            }
        }

def _parse_agent_query_result(observation: str) -> Dict[str, Any]:
    """Parse Agent query result with improved SQLite result handling"""
    try:
        logger.info(f"Parsing query result, length: {len(observation)}")
        
        # Handle SQLite tuple results (most common case)
        if observation.startswith('[') and '(' in observation and ')' in observation:
            try:
                import ast
                # Parse the tuple list
                data = ast.literal_eval(observation)
                if isinstance(data, list) and len(data) > 0:
                    # Convert tuples to dictionaries
                    # First, we need to determine column names
                    # Try to extract column names from the SQL query if available
                    sample_row = data[0]
                    if isinstance(sample_row, tuple):
                        # Try to infer column names from SQL query context
                        columns = []
                        for i in range(len(sample_row)):
                            # Use more meaningful column names based on common patterns
                            if i == 0:
                                columns.append("category")  # Usually first column is category/name
                            elif i == 1:
                                columns.append("sales_revenue")  # Usually second column is value
                            else:
                                columns.append(f"col_{i}")
                        
                        rows = []
                        for row in data:
                            if isinstance(row, tuple):
                                row_dict = {columns[i]: row[i] for i in range(len(row))}
                                rows.append(row_dict)
                        
                        logger.info(f"Parsed tuple result with {len(rows)} rows, {len(columns)} columns")
                        return {
                            "rows": rows,
                            "columns": columns,
                            "executed_sql": "Agent generated SQL"
                        }
            except Exception as e:
                logger.warning(f"Failed to parse tuple result: {e}")
        
        # Try to parse as table format (common SQLite output format)
        lines = observation.strip().split('\n')
        if len(lines) >= 2:
            # Handle different separators
            separators = ['\t', '|', ',']
            columns = None
            separator = None
            
            for sep in separators:
                if sep in lines[0]:
                    columns = lines[0].split(sep)
                    separator = sep
                    break
            
            if columns and separator:
                # Clean column names
                columns = [col.strip() for col in columns]
                rows = []
                
                for line in lines[1:]:
                    if line.strip():
                        values = line.split(separator)
                        if len(values) == len(columns):
                            row = {col.strip(): val.strip() for col, val in zip(columns, values)}
                            rows.append(row)
                
                if rows:
                    logger.info(f"Parsed table result with {len(rows)} rows, {len(columns)} columns")
                    return {
                        "rows": rows,
                        "columns": columns,
                        "executed_sql": "Agent generated SQL"
                    }
        
        # Try to parse as simple key-value pairs
        if '=' in observation and '\n' in observation:
            lines = observation.strip().split('\n')
            rows = []
            columns = set()
            
            for line in lines:
                if '=' in line:
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        key, value = parts[0].strip(), parts[1].strip()
                        columns.add(key)
                        rows.append({key: value})
            
            if rows and columns:
                logger.info(f"Parsed key-value result with {len(rows)} entries")
                return {
                    "rows": rows,
                    "columns": list(columns),
                    "executed_sql": "Agent generated SQL"
                }
        
        # Fallback: return raw text as single row
        logger.warning("Unable to parse structured data, returning raw text")
        return {
            "rows": [{"result": observation}],
            "columns": ["result"],
            "executed_sql": "Agent generated SQL"
        }
        
    except Exception as e:
        logger.error(f"Failed to parse agent query result: {e}")
        return {
            "rows": [{"result": observation}],
            "columns": ["result"],
            "executed_sql": "Agent generated SQL"
        }


async def _perform_rag_guided_sql_query(user_input: str, datasource: Dict[str, Any], rag_metadata: str) -> Dict[str, Any]:
    """Perform SQL query with RAG metadata guidance"""
    try:
        # Enhanced prompt that includes RAG metadata
        enhanced_prompt = f"""
        User Query: "{user_input}"
        
        Metadata Context (from documents):
        {rag_metadata}
        
        Based on the metadata context above, generate an accurate SQL query that:
        1. Uses the correct table and field names mentioned in the metadata
        2. Follows the business rules and relationships described
        3. Answers the user's question using the proper data structure
        
        The metadata provides important context about:
        - Table structures and field definitions
        - Business rules and relationships
        - Data types and constraints
        - Domain-specific knowledge
        
        Use this metadata to ensure the SQL query is accurate and meaningful.
        """
        
        # Use the existing SQL query logic but with enhanced context
        result = await get_query_from_sqltable_datasource(enhanced_prompt, datasource)
        
        if result["success"]:
            # Enhance the result with metadata context
            enhanced_answer = f"""
            [Based on metadata context]
            {result.get('answer', '')}
            
            The query was generated using metadata guidance to ensure accuracy.
            """
            
            return {
                **result,
                "answer": enhanced_answer,
                "rag_guided": True,
                "metadata_used": True
            }
        else:
            return result
            
    except Exception as e:
        logger.error(f"RAG-guided SQL query error: {e}")
        return {
            "success": False,
            "error": f"RAG-guided SQL query failed: {str(e)}"
        }



async def rag_query_node(state: GraphState) -> GraphState:
    """RAG Query Node: Combined RAG retrieval, reranking, and answer generation"""
    user_input = state["user_input"]
    datasource = state["datasource"]
    execution_id = state.get("execution_id", "unknown")
    
    logger.info(f"RAG Query Node - Processing query: {user_input}")
    
    try:
        # Step 1: Perform RAG retrieval
        logger.info(f"RAG Query Node - Retrieving documents for: {user_input}")
        from ..agents.intelligent_agent import perform_rag_retrieval
        
        retrieval_result = await perform_rag_retrieval(user_input, datasource, k=20)
        
        if not retrieval_result["success"]:
            logger.error(f"RAG retrieval failed: {retrieval_result.get('error', 'Unknown error')}")
            return {
                **state,
                "retrieved_documents": [],
                "reranked_documents": [],
                "rag_answer": f"RAG retrieval failed: {retrieval_result.get('error', 'Unknown error')}",
                "retrieval_success": False,
                "retrieval_error": retrieval_result.get("error", "Unknown error"),
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "rag_query": {
                        "status": "failed",
                        "error": retrieval_result.get("error", "Unknown error"),
                        "timestamp": time.time()
                    }
                }
            }
        
        retrieved_documents = retrieval_result["documents"]
        logger.info(f"RAG Query Node - Retrieved {len(retrieved_documents)} documents")

        # Minimal debug: sample sources from retrieved set (generic, low-volume)
        try:
            sample_sources = []
            for doc in retrieved_documents[:3]:
                src = (doc.metadata or {}).get("source") or (doc.metadata or {}).get("file_path") or "unknown"
                sample_sources.append(os.path.basename(src))
            if sample_sources:
                logger.info(f"RAG Retrieval sample sources: {sample_sources}")
        except Exception:
            pass
        
        # Step 2: Rerank documents (select top 3)
        logger.info(f"RAG Query Node - Reranking {len(retrieved_documents)} documents")
        if not retrieved_documents:
            logger.warning("No documents to rerank")
            return {
                **state,
                "retrieved_documents": [],
                "reranked_documents": [],
                "rag_answer": "No relevant documents found to answer the query.",
                "retrieval_success": False,
                "retrieval_error": "No documents available for RAG processing",
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "rag_query": {
                        "status": "failed",
                        "error": "No documents available for RAG processing",
                        "timestamp": time.time()
                    }
                }
            }
        
        # Rerank using Cross-Encoder (token-based). If CE unavailable, keep original order (no fallback sorting).
        reranked_documents = []
        try:
            from src.models.reranker import rerank_with_cross_encoder  # lazy import
            reranked_documents = rerank_with_cross_encoder(user_input, retrieved_documents, top_k=3)
            rerank_mode = "cross-encoder"
        except Exception as _ce_err:
            logger.error(f"Cross-Encoder rerank failed: {_ce_err}")
            # Do not assume score semantics; keep original retrieval order
            reranked_documents = retrieved_documents[:3]
            rerank_mode = "cross-encoder-error"
        
        logger.info(f"RAG Query Node - Selected top {len(reranked_documents)} documents (mode={rerank_mode})")
        
        logger.info(f"RAG Query Node - Selected top {len(reranked_documents)} documents")

        # Minimal debug: print top-3 source and short snippet (generic)
        try:
            for i, d in enumerate(reranked_documents[:3]):
                meta = d.metadata or {}
                src = meta.get("source") or meta.get("file_path") or "unknown"
                score = meta.get("score", 0)
                snippet = (getattr(d, "page_content", "") or "").replace("\n", " ")[:80]
                logger.info(f"RAG Top{i+1}: score={score:.4f}, source={os.path.basename(src)}, snippet=\"{snippet}\"")
        except Exception:
            pass
        
        # Step 3: Generate answer using LLM with reranked documents
        logger.info(f"RAG Query Node - Generating answer from {len(reranked_documents)} documents")
        
        # Use RetrievalQA to generate answer
        from langchain.prompts import PromptTemplate
        from langchain.chains import RetrievalQA
        
        custom_prompt = PromptTemplate(
            template=(
                "You must answer ONLY the user question using the facts from the documents.\n"
                "- If the question is about a person (e.g., Long Liang/Logan), provide a concise biographical summary only.\n"
                "- Ignore and do not explain code, schemas, ETL, SQL, or any unrelated technical content.\n"
                "- Prefer content from the most relevant/top-ranked documents; if no relevant facts exist, say you don't know.\n"
                "- Keep the answer short and focused (3-7 sentences). No extra explanations.\n\n"
                "Documents:\n{context}\n\n"
                "Question: {question}\n\n"
                "Answer:"
            ),
            input_variables=["context", "question"]
        )
        
        # Create temporary retriever (returns fixed reranked documents)
        from langchain_core.retrievers import BaseRetriever
        from typing import List
        from langchain_core.documents import Document
        
        class FixedRetriever(BaseRetriever):
            def __init__(self, docs: List[Document]):
                super().__init__()
                self._docs = docs
            
            def _get_relevant_documents(self, query, *, run_manager=None):
                return self._docs
            
            async def _aget_relevant_documents(self, query, *, run_manager=None):
                return self._docs
        
        retriever = FixedRetriever(reranked_documents)
        
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True,
            chain_type_kwargs={"prompt": custom_prompt}
        )
        
        # Generate answer
        result = qa_chain.invoke({"query": user_input})
        rag_answer = (result["result"] or "").lstrip()
        
        logger.info(f"RAG Query Node - Generated answer - Length: {len(rag_answer)}")
        
        return {
            **state,
            "retrieved_documents": retrieved_documents,
            "reranked_documents": reranked_documents,
            "rag_answer": rag_answer,
            "retrieval_success": True,
            "rerank_success": True,
            "rag_success": True,
            "node_outputs": {
                **state.get("node_outputs", {}),
                "rag_query": {
                    "status": "completed",
                    "retrieved_count": len(retrieved_documents),
                    "reranked_count": len(reranked_documents),
                    "answer_length": len(rag_answer),
                    "timestamp": time.time(),
                    "datasource_id": retrieval_result.get("datasource_id"),
                    "datasource_name": retrieval_result.get("datasource_name")
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error in RAG Query Node: {e}", exc_info=True)
        return {
            **state,
            "retrieved_documents": [],
            "reranked_documents": [],
            "rag_answer": f"Error generating answer: {str(e)}",
            "retrieval_success": False,
            "rerank_success": False,
            "rag_success": False,
            "error": f"RAG query processing failed: {str(e)}",
            "node_outputs": {
                **state.get("node_outputs", {}),
                "rag_query": {
                    "status": "error",
                    "error": str(e),
                    "timestamp": time.time()
                }
            }
        }




async def _perform_metadata_rag_query(user_input: str, datasource: Dict[str, Any]) -> Dict[str, Any]:
    """Perform metadata-focused RAG query for hybrid path"""
    try:
        # Enhanced prompt for metadata retrieval
        metadata_prompt = f"""
        The user is asking: "{user_input}"
        
        Focus on retrieving metadata information that would help understand:
        - Table structures and field definitions
        - Data relationships and business rules
        - Field meanings and data types
        - Business context and domain knowledge
        
        This metadata will be used to guide a subsequent database query.
        Prioritize information that explains what the data means, not the actual data values.
        """
        
        # Use the existing perform_rag_query but with enhanced context
        result = await perform_rag_query(metadata_prompt, datasource)
        
        if result["success"]:
            # Enhance the result with metadata-specific information
            enhanced_answer = f"""
            [Metadata Context]
            {result['answer']}
            
            This metadata information will help guide the subsequent data query.
            """
            
            return {
                **result,
                "answer": enhanced_answer,
                "confidence": result.get("confidence", 0.9),  # Higher confidence for metadata
                "metadata_focused": True
            }
        else:
            return result
            
    except Exception as e:
        logger.error(f"Metadata RAG query error: {e}")
        return {
            "success": False,
            "error": f"Metadata RAG query failed: {str(e)}"
        }



async def llm_processing_node(state: GraphState) -> GraphState:
    """Enhanced LLM Processing Node: Integrate RAG + SQL-Agent + Chart inputs"""
    try:
        user_input = state["user_input"]
        execution_id = state.get("execution_id")
        
        # Get various inputs
        rag_answer = state.get("rag_answer", "")
        sql_agent_answer = state.get("sql_agent_answer", "")
        structured_data = state.get("structured_data")
        chart_config = state.get("chart_config")
        chart_suitable = state.get("chart_suitable", False)
        
        logger.info(f"LLM Processing Node - Integrating inputs: RAG={bool(rag_answer)}, SQL={bool(sql_agent_answer)}, Chart={chart_suitable}")
        
        # Build comprehensive prompt
        prompt_parts = []
        
        # 1. Basic question
        prompt_parts.append(f"User question: {user_input}")
        
        # 2. RAG answer (if available)
        if rag_answer:
            prompt_parts.append(f"Knowledge base answer: {rag_answer}")
        
        # 3. SQL-Agent answer (if available)
        if sql_agent_answer:
            prompt_parts.append(f"Database query results: {sql_agent_answer}")
            
            # Add structured data summary
            if structured_data:
                data_summary = _summarize_structured_data(structured_data)
                prompt_parts.append(f"Data summary: {data_summary}")
        
        # 4. Chart information (if available)
        if chart_suitable and chart_config:
            chart_type = chart_config.get("type", "unknown")
            prompt_parts.append(f"Generated {chart_type} chart, please explain the chart content")
        
        # 5. Integration instructions
        prompt_parts.append("""
Please generate a comprehensive, accurate, and natural answer based on the above information:
1. Prioritize specific data from database query results
2. Combine background information from knowledge base for explanation
3. If there's a chart, explain what the chart shows
4. Keep the answer concise and clear, avoid repetition
5. If information is insufficient, please state honestly
""")
        
        final_prompt = "\n\n".join(prompt_parts)
        
        # Generate final answer
        if llm:
            logger.info("Generating final integrated answer...")
            response = await llm.ainvoke(final_prompt)
            final_answer = (response.content if hasattr(response, 'content') else str(response)).lstrip()
        else:
            # Fallback: simple concatenation
            final_answer = _create_fallback_answer(rag_answer, sql_agent_answer, chart_suitable).lstrip()
        
        logger.info(f"LLM Processing completed - Answer length: {len(final_answer)}")
        
        return {
            **state,
            "answer": final_answer,
            "final_answer": final_answer,
            "node_outputs": {
                **state.get("node_outputs", {}),
                "llm_processing": {
                    "status": "completed",
                    "answer_length": len(final_answer),
                    "has_rag": bool(rag_answer),
                    "has_sql": bool(sql_agent_answer),
                    "has_chart": chart_suitable,
                    "timestamp": time.time()
                }
            }
        }
        
    except Exception as e:
        error_msg = f"Error in LLM Processing Node: {str(e)}"
        logger.error(error_msg)
        return {
            **state,
            "error": error_msg,
            "node_outputs": {
                **state.get("node_outputs", {}),
                "llm_processing": {
                    "status": "error",
                    "timestamp": time.time(),
                    "error": error_msg
                }
            }
        }

def _summarize_structured_data(structured_data: Dict[str, Any]) -> str:
    """Summarize structured data"""
    try:
        rows = structured_data.get("rows", [])
        columns = structured_data.get("columns", [])
        
        if not rows or not columns:
            return "No valid data"
        
        summary_parts = []
        summary_parts.append(f"Data contains {len(rows)} rows, {len(columns)} columns")
        summary_parts.append(f"Column names: {', '.join(columns)}")
        
        # Show first few rows of data
        if len(rows) <= 5:
            summary_parts.append("Complete data:")
            for i, row in enumerate(rows):
                row_str = ", ".join([f"{col}: {row.get(col, '')}" for col in columns])
                summary_parts.append(f"  {i+1}. {row_str}")
        else:
            summary_parts.append("First 3 rows of data:")
            for i, row in enumerate(rows[:3]):
                row_str = ", ".join([f"{col}: {row.get(col, '')}" for col in columns])
                summary_parts.append(f"  {i+1}. {row_str}")
            summary_parts.append(f"  ... and {len(rows)-3} more rows")
        
        return "\n".join(summary_parts)
        
    except Exception as e:
        logger.warning(f"Failed to summarize structured data: {e}")
        return "Data summary generation failed"

def _create_fallback_answer(rag_answer: str, sql_answer: str, has_chart: bool) -> str:
    """Create fallback answer"""
    parts = []
    
    if sql_answer:
        parts.append(f"Based on database query: {sql_answer}")
    
    if rag_answer:
        parts.append(f"Related knowledge: {rag_answer}")
    
    if has_chart:
        parts.append("Related charts have been generated for reference")
    
    if not parts:
        return "Sorry, unable to retrieve relevant information to answer your question."
    
    return "\n\n".join(parts)

async def _process_rag_only_output(state: GraphState, execution_id: str) -> GraphState:
    """Process RAG-only path output"""
    rag_answer = state.get("rag_answer", "")
    
    if not rag_answer:
        error_msg = "No RAG answer available for processing"
        logger.error(error_msg)
        return {**state, "error": error_msg}
    
    logger.info("LLM Processing - Processing RAG-only output")
    
    # Stream the RAG answer
    await _stream_text_as_tokens(rag_answer, execution_id, "llm_processing_node")
    
    final_result = {
        "text": rag_answer,
        "data": None,
        "chart": None,
        "path": "rag_only"
    }
    
    return {
        **state,
        "answer": rag_answer,
        "final_result": final_result,
        "node_outputs": {
            **state.get("node_outputs", {}),
            "llm_processing": {
                "status": "completed",
                "timestamp": time.time(),
                "path": "rag_only",
                "output_type": "text_only"
            }
        }
    }

async def _process_sql_only_output(state: GraphState, execution_id: str) -> GraphState:
    """Process SQL-only path output"""
    structured_data = state.get("structured_data")
    chart_config = state.get("chart_config")
    sql_agent_answer = state.get("sql_agent_answer", "")
    
    if not structured_data:
        error_msg = "No structured data available for processing"
        logger.error(error_msg)
        return {**state, "error": error_msg}
    
    logger.info("LLM Processing - Processing SQL-only output")
    
    # Generate intelligent response from SQL data
    rows = structured_data.get("rows", [])
    columns = structured_data.get("columns", [])
    executed_sqls = state.get("executed_sqls", [])
    
    if rows:
        # Generate structured answer
        structured_answer = _generate_intelligent_sql_response(
            state["user_input"], rows, columns, executed_sqls[0] if executed_sqls else ""
        )
        
        # Add chart context if available
        if chart_config:
            structured_answer += f"\n\nI've also generated a visualization chart to help you better understand the data."
        
        # Stream the response
        await _stream_text_as_tokens(structured_answer, execution_id, "llm_processing_node")
        final_answer = (structured_answer or "").lstrip()
    else:
        final_answer = f"No data was found matching your query '{state['user_input']}'. Please try a different question or check if the data exists.".lstrip()
        await _stream_text_as_tokens(final_answer, execution_id, "llm_processing_node")
    
    final_result = {
        "text": final_answer,
        "data": structured_data,
        "chart": chart_config,
        "path": "sql_only"
    }
    
    return {
        **state,
        "answer": final_answer,
        "final_result": final_result,
        "node_outputs": {
            **state.get("node_outputs", {}),
            "llm_processing": {
                "status": "completed",
                "timestamp": time.time(),
                "path": "sql_only",
                "output_type": "text_and_chart" if chart_config else "text_and_data",
                "data_rows": len(rows),
                "has_chart": bool(chart_config)
            }
        }
    }

async def _process_rag_sql_output(state: GraphState, execution_id: str) -> GraphState:
    """Process RAG+SQL hybrid path output"""
    rag_answer = state.get("rag_answer", "")
    sql_agent_answer = state.get("sql_agent_answer", "")
    structured_data = state.get("structured_data")
    chart_config = state.get("chart_config")
    
    # Handle case where RAG failed but SQL succeeded
    if not rag_answer and structured_data:
        logger.warning("RAG answer missing, processing SQL-only output in hybrid path")
        return await _process_sql_only_output(state, execution_id)
    
    # Handle case where SQL failed but RAG succeeded
    if rag_answer and not structured_data:
        logger.warning("SQL data missing, processing RAG-only output in hybrid path")
        return await _process_rag_only_output(state, execution_id)
    
    # Handle case where both are missing
    if not rag_answer and not structured_data:
        error_msg = "Missing both RAG answer and structured data for hybrid processing"
        logger.error(error_msg)
        return {**state, "error": error_msg}
    
    logger.info("LLM Processing - Processing RAG+SQL hybrid output")
    
    # Generate comprehensive response combining RAG and SQL data
    comprehensive_prompt = f"""
    User Query: "{state['user_input']}"
    
    RAG Context: {rag_answer}
    
    SQL Answer: {sql_agent_answer}
    
    Please provide a comprehensive response that:
    1. Explains the RAG context and what the data means
    2. Analyzes the actual SQL data results
    3. Provides insights and interpretation
    4. Mentions the visualization if available
    
    Keep the response informative but concise.
    """
    
    # Stream LLM response
    final_answer = await stream_llm_response(comprehensive_prompt, execution_id, "llm_processing_node")
    
    final_result = {
        "text": final_answer,
        "data": structured_data,
        "chart": chart_config,
        "metadata": rag_answer,
        "path": "rag_sql"
    }
    
    return {
        **state,
        "answer": final_answer,
        "final_result": final_result,
        "node_outputs": {
            **state.get("node_outputs", {}),
            "llm_processing": {
                "status": "completed",
                "timestamp": time.time(),
                "path": "rag_sql",
                "output_type": "comprehensive",
                "data_rows": len(structured_data.get("rows", [])),
                "has_chart": bool(chart_config),
                "has_rag_context": bool(rag_answer)
            }
        }
    }

def _generate_intelligent_sql_response(user_input: str, rows: list, columns: list, executed_sql: str = "") -> str:
    """Generate intelligent natural language response from SQL results"""
    try:
        logger.info(f"_generate_intelligent_sql_response called with {len(rows)} rows, columns: {columns}")
        
        if not rows:
            logger.info("No rows found, returning no results message")
            return f"No results were found for your query: '{user_input}'"
        
        # Analyze the query type and data structure
        query_lower = user_input.lower()
        row_count = len(rows)
        
        logger.info(f"Query analysis: row_count={row_count}, query_lower='{query_lower}'")
        
        # Single value result
        if row_count == 1 and len(rows[0]) == 1:
            logger.info("Processing single value result")
            value = list(rows[0].values())[0]
            if isinstance(value, (int, float)):
                formatted_value = f"{value:,.2f}" if isinstance(value, float) else f"{value:,}"
            else:
                formatted_value = str(value)
            result = f"Based on your query '{user_input}', the result is: {formatted_value}"
            logger.info(f"Single value result: {result}")
            return result
        
        # Category-value pairs (like our average price case)
        if row_count > 1 and len(columns) == 2:
            logger.info("Processing category-value pairs")
            # Check if this looks like category-value data
            first_row = rows[0]
            logger.info(f"First row structure: {first_row}")
            
            if 'category' in first_row and 'value' in first_row:
                logger.info("Detected category-value structure, processing intelligent response")
                # Sort by value for better presentation
                sorted_rows = sorted(rows, key=lambda x: x.get('value', 0), reverse=True)
                logger.info(f"Sorted rows: {sorted_rows}")
                
                response_lines = [f"Here are the results for '{user_input}':"]
                
                for i, row in enumerate(sorted_rows):
                    category = row.get('category', 'Unknown')
                    value = row.get('value', 0)
                    
                    # Format value based on the query context
                    if 'price' in query_lower or 'cost' in query_lower or 'amount' in query_lower:
                        formatted_value = f"${value:.2f}"
                    elif 'percentage' in query_lower or 'percent' in query_lower:
                        formatted_value = f"{value:.1f}%"
                    elif isinstance(value, float):
                        formatted_value = f"{value:.2f}"
                    else:
                        formatted_value = f"{value:,}"
                    
                    response_lines.append(f"• {category}: {formatted_value}")
                
                # Add insights for average/price queries
                if 'average' in query_lower and 'price' in query_lower:
                    logger.info("Adding price insights")
                    highest = sorted_rows[0]
                    lowest = sorted_rows[-1]
                    response_lines.append(f"\nKey insights:")
                    response_lines.append(f"• Highest average price: {highest['category']} (${highest['value']:.2f})")
                    response_lines.append(f"• Lowest average price: {lowest['category']} (${lowest['value']:.2f})")
                    
                    price_diff = highest['value'] - lowest['value']
                    response_lines.append(f"• Price range: ${price_diff:.2f}")
                
                result = "\n".join(response_lines)
                logger.info(f"Category-value response generated: {result[:200]}...")
                return result
        
        logger.info("Processing as generic structured data")
        # Generic structured data response
        if row_count <= 10:
            # For small result sets, show details
            response_lines = [f"Found {row_count} results for '{user_input}':"]
            
            for i, row in enumerate(rows):
                if len(row) == 1:
                    value = list(row.values())[0]
                    response_lines.append(f"{i+1}. {value}")
                else:
                    # Multi-column row
                    row_parts = []
                    for key, value in row.items():
                        if isinstance(value, (int, float)) and key.lower() in ['price', 'cost', 'amount', 'total']:
                            formatted_value = f"${value:.2f}" if isinstance(value, float) else f"${value:,}"
                        elif isinstance(value, float):
                            formatted_value = f"{value:.2f}"
                        elif isinstance(value, int):
                            formatted_value = f"{value:,}"
                        else:
                            formatted_value = str(value)
                        row_parts.append(f"{key}: {formatted_value}")
                    response_lines.append(f"{i+1}. {', '.join(row_parts)}")
            
            result = "\n".join(response_lines)
            logger.info(f"Generic detailed response: {result[:200]}...")
            return result
        else:
            # For large result sets, provide summary
            result = f"Found {row_count} results for '{user_input}'. The data contains {len(columns)} columns: {', '.join(columns)}. Use filters or more specific queries to narrow down the results."
            logger.info(f"Large dataset summary: {result}")
            return result
    
    except Exception as e:
        logger.error(f"Error generating intelligent SQL response: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return f"I found {len(rows)} results for your query '{user_input}', but had trouble formatting the response. The data is available but the presentation failed."

# Validation and retry nodes removed - processing goes directly to end node

def generate_chart_config(data: Dict[str, Any], user_input: str) -> Dict[str, Any]:
    """Use LLM to generate chart configuration based on data and user requirements for semantic analysis"""
    try:
        if not llm:
            logger.warning("LLM not available, using fallback chart generation")
            return generate_fallback_chart_config(data, user_input)
        
        # Extract data information for LLM analysis
        data_summary = extract_data_summary(data)
        
        # Use LLM to analyze user intent and data characteristics
        chart_analysis_prompt = f"""
        User query: "{user_input}"
        
        Data summary: {data_summary}
        
        You MUST return a complete JSON configuration for the chart. Analyze the user's requirements and provide ALL required fields:
        {{
            "chart_type": "pie",
            "title": "Sales Proportion by Product Category (July-September 2025)",
            "x_axis_label": "Product Category",
            "y_axis_label": "Sales Revenue ($)",
            "data_field_for_labels": "category",
            "data_field_for_values": "sales_revenue",
            "aggregation_method": "sum",
            "time_grouping": "none",
            "is_time_series": false
        }}
        
        IMPORTANT: 
        1. For pie charts about sales proportion, use chart_type: "pie"
        2. Always provide a meaningful title based on the query - NEVER leave title empty
        3. Title should be descriptive and include relevant time periods if mentioned
        4. For sales data, include time period in title (e.g., "July-September 2025")
        5. For sales data, use y_axis_label: "Sales Revenue ($)" or "Sales Amount ($)"
        6. For category data, use x_axis_label: "Product Category" or similar
        7. Return ONLY valid JSON, no additional text
        
        Based on the query "{user_input}", return the complete JSON configuration:
        """
        
        # Use reasoning model for chart inference
        try:
            from ..models.llm_factory import get_reasoning_llm
            reasoning_llm = get_reasoning_llm()
            response = reasoning_llm.invoke(chart_analysis_prompt)
        except Exception:
            # Fallback to default chat model
            response = llm.invoke(chart_analysis_prompt)
        
        # Process LLM response
        if hasattr(response, 'content'):
            analysis_text = response.content
        elif isinstance(response, str):
            analysis_text = response
        else:
            analysis_text = str(response)
        
        # Parse JSON configuration returned by LLM
        try:
            import json
            import re
            
            # Try multiple JSON extraction methods
            chart_analysis = None
            
            # Method 1: Look for complete JSON object
            json_match = re.search(r'\{.*\}', analysis_text, re.DOTALL)
            if json_match:
                try:
                    chart_analysis = json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            
            # Method 2: Look for JSON with code block markers
            if not chart_analysis:
                code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', analysis_text, re.DOTALL)
                if code_block_match:
                    try:
                        chart_analysis = json.loads(code_block_match.group(1))
                    except json.JSONDecodeError:
                        pass
            
            # Method 3: Try to extract individual fields
            if not chart_analysis:
                chart_analysis = {}
                # Extract chart_type
                chart_type_match = re.search(r'"chart_type":\s*"([^"]+)"', analysis_text)
                if chart_type_match:
                    chart_analysis["chart_type"] = chart_type_match.group(1)
                
                # Extract title
                title_match = re.search(r'"title":\s*"([^"]+)"', analysis_text)
                if title_match:
                    chart_analysis["title"] = title_match.group(1)
                
                # Extract other fields similarly
                y_axis_match = re.search(r'"y_axis_label":\s*"([^"]+)"', analysis_text)
                if y_axis_match:
                    chart_analysis["y_axis_label"] = y_axis_match.group(1)
                
                x_axis_match = re.search(r'"x_axis_label":\s*"([^"]+)"', analysis_text)
                if x_axis_match:
                    chart_analysis["x_axis_label"] = x_axis_match.group(1)
                
                # Extract aggregation method
                agg_match = re.search(r'"aggregation_method":\s*"([^"]+)"', analysis_text)
                if agg_match:
                    chart_analysis["aggregation_method"] = agg_match.group(1)
                
                # Extract time grouping
                time_match = re.search(r'"time_grouping":\s*"([^"]+)"', analysis_text)
                if time_match:
                    chart_analysis["time_grouping"] = time_match.group(1)
                
                # Extract is_time_series
                time_series_match = re.search(r'"is_time_series":\s*(true|false)', analysis_text)
                if time_series_match:
                    chart_analysis["is_time_series"] = time_series_match.group(1).lower() == 'true'
                
                # If we found at least chart_type, consider it valid
                if chart_analysis.get("chart_type"):
                    logger.info(f"Successfully extracted chart analysis: {chart_analysis}")
                else:
                    raise ValueError("No valid chart configuration found")
            
            if not chart_analysis:
                raise ValueError("No valid chart configuration found")
                
        except (json.JSONDecodeError, AttributeError, ValueError) as e:
            logger.warning(f"Failed to parse LLM chart analysis: {e}, using fallback")
            return generate_fallback_chart_config(data, user_input)
        
        # Generate chart configuration based on LLM analysis results
        # Fallback chart type detection if LLM didn't specify correctly
        detected_type = chart_analysis.get("chart_type", "bar")
        user_input_lower = user_input.lower()
        
        if "pie chart" in user_input_lower or "pie" in user_input_lower:
            detected_type = "pie"
        elif "line chart" in user_input_lower or "line" in user_input_lower:
            detected_type = "line"
        elif "bar chart" in user_input_lower or "bar" in user_input_lower:
            detected_type = "bar"
        
        # Generate intelligent chart title
        chart_title = chart_analysis.get("title", "")
        logger.info(f"LLM provided title: '{chart_title}'")
        
        if not chart_title or chart_title == "Chart title":
            # Generate title based on user input and chart type
            if detected_type == "pie":
                if "sales" in user_input_lower and "proportion" in user_input_lower:
                    chart_title = "Sales Proportion by Product Category (July-September 2025)"
                elif "sales" in user_input_lower:
                    chart_title = "Sales Distribution by Product Category"
                else:
                    chart_title = "Data Distribution"
            elif detected_type == "line":
                if "trend" in user_input_lower or "monthly" in user_input_lower:
                    chart_title = "Sales Trend Over Time"
                else:
                    chart_title = "Data Trend"
            elif detected_type == "bar":
                if "sales" in user_input_lower:
                    chart_title = "Sales by Product Category"
                else:
                    chart_title = "Data Comparison"
            else:
                chart_title = "Data Chart"
            
            logger.info(f"Generated intelligent title: '{chart_title}'")
        else:
            logger.info(f"Using LLM provided title: '{chart_title}'")
        
        # Generate intelligent Y-axis label
        y_axis_label = chart_analysis.get("y_axis_label", "Value")
        if not y_axis_label or y_axis_label == "Y-axis label":
            # Try to infer meaningful Y-axis label from user query and data
            if "sales" in user_input_lower and ("trend" in user_input_lower or "monthly" in user_input_lower):
                y_axis_label = "Sales Amount ($)"
            elif "sales" in user_input_lower and "proportion" in user_input_lower:
                y_axis_label = "Sales Proportion (%)"
            elif "count" in user_input_lower or "number" in user_input_lower:
                y_axis_label = "Count"
            elif "amount" in user_input_lower or "revenue" in user_input_lower:
                y_axis_label = "Amount ($)"
            elif "price" in user_input_lower:
                y_axis_label = "Price ($)"
            else:
                y_axis_label = "Value"
        
        chart_config = {
            "type": detected_type,
            "data": {
                "labels": [],
                "datasets": [{
                    "label": y_axis_label,
                    "data": [],
                    "backgroundColor": [
                        "rgba(54, 162, 235, 0.6)",
                        "rgba(255, 99, 132, 0.6)", 
                        "rgba(255, 206, 86, 0.6)",
                        "rgba(75, 192, 192, 0.6)",
                        "rgba(153, 102, 255, 0.6)",
                        "rgba(255, 159, 64, 0.6)",
                        "rgba(199, 199, 199, 0.6)",
                        "rgba(83, 102, 255, 0.6)"
                    ],
                    "borderColor": [
                        "rgba(54, 162, 235, 1)",
                        "rgba(255, 99, 132, 1)",
                        "rgba(255, 206, 86, 1)", 
                        "rgba(75, 192, 192, 1)",
                        "rgba(153, 102, 255, 1)",
                        "rgba(255, 159, 64, 1)",
                        "rgba(199, 199, 199, 1)",
                        "rgba(83, 102, 255, 1)"
                    ],
                    "borderWidth": 2,
                    "fill": chart_analysis.get("chart_type") != "line"
                }]
            },
            "options": {
                "responsive": True,
                "plugins": {
                    "title": {
                        "display": True,
                        "text": chart_title,
                        "font": {
                            "size": 16,
                            "weight": "bold"
                        }
                    },
                    "legend": {
                        "display": True,
                        "position": "top"
                    }
                },
                "scales": {
                    "y": {
                        "beginAtZero": True,
                        "title": {
                            "display": True,
                            "text": y_axis_label
                        }
                    },
                    "x": {
                        "title": {
                            "display": True,
                            "text": chart_analysis.get("x_axis_label", "Category")
                        }
                    }
                }
            }
        }
        
        # Process data using LLM-guided approach
        labels, values = extract_chart_data_with_llm_guidance(data, chart_analysis, user_input)
        
        if labels and values:
            chart_config["data"]["labels"] = labels
            chart_config["data"]["datasets"][0]["data"] = values

            # Ensure backgroundColor and borderColor arrays match data point count
            base_colors_bg = [
                "rgba(54, 162, 235, 0.6)",
                "rgba(255, 99, 132, 0.6)",
                "rgba(255, 206, 86, 0.6)",
                "rgba(75, 192, 192, 0.6)",
                "rgba(153, 102, 255, 0.6)",
                "rgba(255, 159, 64, 0.6)",
                "rgba(199, 199, 199, 0.6)",
                "rgba(83, 102, 255, 0.6)"
            ]
            def to_border(c):
                # Convert transparency from 0.6 to 1 for border
                if c.endswith("0.6)"):
                    return c.replace("0.6)", "1)")
                return c

            num_points = len(values)
            colors_bg = [base_colors_bg[i % len(base_colors_bg)] for i in range(num_points)]
            colors_border = [to_border(c) for c in colors_bg]

            chart_config["data"]["datasets"][0]["backgroundColor"] = colors_bg
            chart_config["data"]["datasets"][0]["borderColor"] = colors_border
            logger.info(f"LLM-guided chart data configured with {len(labels)} data points")
            logger.info(f"Final chart configuration - Type: {chart_config['type']}, Title: '{chart_config['options']['plugins']['title']['text']}'")
        else:
            logger.warning("No data extracted with LLM guidance, using fallback")
            return generate_fallback_chart_config(data, user_input)
        
        return chart_config
        
    except Exception as e:
        logger.error(f"Error in LLM-guided chart generation: {e}")
        return generate_fallback_chart_config(data, user_input)

def extract_data_summary(data: Dict[str, Any]) -> str:
    """Extract data summary for LLM analysis"""
    try:
        summary_parts = []
        
        if isinstance(data, dict):
            if "rows" in data and data["rows"]:
                rows = data["rows"]
                summary_parts.append(f"Data rows: {len(rows)}")
                
                if len(rows) > 0:
                    sample_row = rows[0]
                    summary_parts.append(f"Data columns: {len(sample_row)}")
                    summary_parts.append(f"Sample data: {sample_row}")
                    
                    # Analyze data types
                    if len(sample_row) >= 8:
                        summary_parts.append(f"Contains structured data with {len(sample_row)} fields")
                    elif len(sample_row) >= 3:
                        summary_parts.append(f"Contains structured data with {len(sample_row)} fields")
                    elif len(sample_row) == 2:
                        # Handle aggregated query results, such as month and sales
                        summary_parts.append("Contains aggregated data with time and values")
                    
            if "answer" in data:
                summary_parts.append(f"Query result description: {str(data['answer'])[:100]}...")
                
        return "; ".join(summary_parts) if summary_parts else "Data structure unclear"
        
    except Exception as e:
        logger.error(f"Error extracting data summary: {e}")
        return "Data summary extraction failed"

def extract_chart_data_with_llm_guidance(data: Dict[str, Any], chart_analysis: Dict[str, Any], user_input: str = "") -> tuple:
    """Extract chart data - simplified logic without fallback"""
    try:
        labels = []
        values = []
        
        if not isinstance(data, dict) or "rows" not in data or not data["rows"]:
            logger.error("No valid data found in extract_chart_data_with_llm_guidance")
            return labels, values
        
        rows = data["rows"]
        sample_row = rows[0] if rows else {}
        logger.info(f"Processing sample row: {sample_row}, type: {type(sample_row)}")
        
        # Handle dictionary format with category/value keys (from parsed string results)
        if isinstance(sample_row, dict) and "category" in sample_row and "value" in sample_row:
            logger.info(f"Processing {len(rows)} rows of category-value data")
            
            # Simple processing: sort by value descending and take all data points
            sorted_rows = sorted(rows, key=lambda x: float(x.get("value", 0)), reverse=True)
            processed_rows = sorted_rows  # Remove the limit to show all data points
            
            # Extract final labels and values
            for row in processed_rows:
                try:
                    label = str(row["category"]) if row["category"] else f"Item{len(labels)+1}"
                    value = float(row["value"]) if isinstance(row["value"], (int, float)) else 0
                    
                    labels.append(label)
                    values.append(value)
                    logger.info(f"Added data point: {label} -> {value}")
                    
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Error processing row: {e}")
                    continue
            
            logger.info(f"Successfully extracted {len(labels)} data points using simplified analysis")
            return labels, values
        
        # Handle original logic for other data formats
        num_cols = len(sample_row) if isinstance(sample_row, (list, tuple)) else len(sample_row.keys()) if isinstance(sample_row, dict) else 0
        
        # For time series queries, intelligently detect time and value fields
        if chart_analysis.get("is_time_series") or chart_analysis.get("time_grouping") != "none" or any(keyword in user_input.lower() for keyword in ['trend', 'monthly', 'yearly', 'over time']):
            # This is likely a time series query
            if num_cols == 2:
                # Two columns: likely (time/period, value)
                label_idx, value_idx = 0, 1
            elif isinstance(sample_row, dict) and "label" in sample_row and "value" in sample_row:
                # Dictionary format from parsed results
                label_field, value_field = "label", "value"  
                label_idx, value_idx = "label", "value"
            else:
                # Multi-column: use field specification or defaults
                label_field = chart_analysis.get("data_field_for_labels", "0")  # First column for time
                value_field = chart_analysis.get("data_field_for_values", "1")  # Second column for values
                try:
                    label_idx = int(label_field) if str(label_field).isdigit() else 0
                    value_idx = int(value_field) if str(value_field).isdigit() else 1
                    # Ensure indices are within bounds
                    if label_idx >= num_cols: label_idx = 0
                    if value_idx >= num_cols: value_idx = min(1, num_cols - 1)
                except (ValueError, TypeError):
                    label_idx, value_idx = 0, min(1, num_cols - 1)
        else:
            # Non-time series: use dynamic field selection
            label_field = chart_analysis.get("data_field_for_labels", "0")  # Default to first column
            value_field = chart_analysis.get("data_field_for_values", "1")  # Default to second column
            try:
                label_idx = int(label_field) if str(label_field).isdigit() else 0
                value_idx = int(value_field) if str(value_field).isdigit() else 1
                # Ensure indices are within bounds
                if num_cols > 0:
                    if label_idx >= num_cols: label_idx = min(0, num_cols - 1)
                    if value_idx >= num_cols: value_idx = min(1, num_cols - 1)
            except (ValueError, TypeError):
                label_idx, value_idx = 0, min(1, num_cols - 1)
        
        logger.info(f"Using label_idx: {label_idx}, value_idx: {value_idx}")
        logger.info(f"Sample row: {sample_row}")
        logger.info(f"Is time series: {chart_analysis.get('is_time_series', False)}, Time grouping: {chart_analysis.get('time_grouping', 'none')}")
        
        if chart_analysis.get("time_grouping") != "none" and len(rows[0]) > 7:
            # Time series data processing
            time_data = {}
            
            for row in rows:
                # Handle both dict and list/tuple formats
                if isinstance(row, dict):
                    row_values = list(row.values())
                    if len(row_values) > 7:
                        try:
                            date_str = str(row_values[7]) if row_values[7] else ""
                            # Handle TEXT type numeric fields
                            value_str = str(row_values[value_idx]) if row_values[value_idx] else "0"
                            # Try to convert to float
                            try:
                                value = float(value_str)
                            except ValueError:
                                # If conversion fails, try to extract numbers
                                import re
                                numbers = re.findall(r'-?\d+\.?\d*', value_str)
                                value = float(numbers[0]) if numbers else 0
                        except (IndexError, KeyError, ValueError):
                            continue
                else:
                    if len(row) > max(label_idx, value_idx, 7):
                        try:
                            date_str = str(row[7]) if row[7] else ""
                            # Handle TEXT type numeric fields
                            value_str = str(row[value_idx]) if row[value_idx] else "0"
                            # Try to convert to float
                            try:
                                value = float(value_str)
                            except ValueError:
                                # If conversion fails, try to extract numbers
                                import re
                                numbers = re.findall(r'-?\d+\.?\d*', value_str)
                                value = float(numbers[0]) if numbers else 0
                        except (IndexError, KeyError, ValueError):
                            continue
                        except (IndexError, KeyError, ValueError):
                            continue
                        
                        if date_str and len(date_str) >= 7:
                            if chart_analysis.get("time_grouping") == "month":
                                # Extract year-month, support different date formats
                                if '-' in date_str:
                                    time_key = date_str[:7] if len(date_str) >= 7 else date_str
                                else:
                                    time_key = date_str[:7] if len(date_str) >= 7 else date_str
                            elif chart_analysis.get("time_grouping") == "quarter":
                                year = date_str[:4]
                                month_str = date_str[5:7] if len(date_str) > 6 else "01"
                                try:
                                    month = int(month_str)
                                    quarter = (month - 1) // 3 + 1
                                    time_key = f"{year}-Q{quarter}"
                                except ValueError:
                                    time_key = f"{year}-Q1"
                            elif chart_analysis.get("time_grouping") == "year":
                                time_key = date_str[:4]  # YYYY
                            else:
                                time_key = date_str[:7]
                            
                            if chart_analysis.get("aggregation_method") == "sum":
                                time_data[time_key] = time_data.get(time_key, 0) + value
                            elif chart_analysis.get("aggregation_method") == "average":
                                if time_key in time_data:
                                    time_data[time_key] = (time_data[time_key] + value) / 2
                                else:
                                    time_data[time_key] = value
                            else:
                                time_data[time_key] = value
            
            # Convert time data to chart format with proper time-based sorting
            def sort_time_key(key):
                """Custom time key sorting function"""
                try:
                    if chart_analysis.get("time_grouping") == "year":
                        return int(key)
                    elif chart_analysis.get("time_grouping") == "month":
                        year, month = key.split('-')
                        return int(year) * 100 + int(month)
                    elif chart_analysis.get("time_grouping") == "week":
                        year, week_str = key.split('-W')
                        return int(year) * 100 + int(week_str)
                    elif chart_analysis.get("time_grouping") == "quarter":
                        year, quarter = key.split('-Q')
                        return int(year) * 10 + int(quarter)
                    else:
                        return key
                except:
                    return key
            
            for time_key in sorted(time_data.keys(), key=sort_time_key):
                labels.append(_format_time_label(time_key, chart_analysis.get("time_grouping", "none")))
                values.append(time_data[time_key])
                
        else:
            # Non-time series data processing
            data_dict = {}
            
            logger.info(f"Processing {len(rows)} rows of data")
            
            for i, row in enumerate(rows):
                logger.info(f"Processing row {i}: {row}, length: {len(row)}")
                
                # Handle dictionary format with label/value keys (from parsed string results)
                if isinstance(row, dict) and "label" in row and "value" in row:
                    try:
                        label = str(row["label"]) if row["label"] else f"Item{len(labels)+1}"
                        value = float(row["value"]) if isinstance(row["value"], (int, float)) else 0
                        
                        # Smart label formatting for better display based on context
                        label = _format_label_based_on_context(label, chart_analysis, user_input)
                        
                        data_dict[label] = value
                        logger.info(f"Added data point: {label} -> {value}")
                        
                    except (ValueError, TypeError, IndexError) as e:
                        logger.warning(f"Error processing dictionary row data: {e}")
                        continue
                        
                elif len(row) == 2:
                    # Handle aggregated query results (e.g., month and sales)
                    try:
                        # Handle both dict and list formats
                        if isinstance(row, dict):
                            # For dict format like {'category': 'OFFICE SUPPLIES', 'sales_revenue': 71}
                            # Get the first and second values
                            values = list(row.values())
                            if len(values) >= 2:
                                label = str(values[0]) if values[0] else f"Item{len(labels)+1}"
                                value_str = str(values[1]) if values[1] else "0"
                            else:
                                continue
                        else:
                            # For list/tuple format
                            label = str(row[0]) if row[0] else f"Item{len(labels)+1}"
                            value_str = str(row[1]) if row[1] else "0"
                        
                        # Handle TEXT type numeric fields
                        try:
                            value = float(value_str)
                        except ValueError:
                            # If conversion fails, try to extract numbers
                            import re
                            numbers = re.findall(r'-?\d+\.?\d*', value_str)
                            value = float(numbers[0]) if numbers else 0
                        
                        # Smart label formatting for better display based on context
                        label = _format_label_based_on_context(label, chart_analysis, user_input)
                        
                        data_dict[label] = value
                        logger.info(f"Added data point: {label} -> {value}")
                        
                    except (ValueError, TypeError, IndexError) as e:
                        logger.warning(f"Error processing 2-column row data: {e}")
                        continue
                        
                elif len(row) > max(label_idx, value_idx):
                    # Handle multi-column data
                    try:
                        # Handle both dict and list formats
                        if isinstance(row, dict):
                            # For dict format like {'col_0': '2025-01', 'col_1': 42, 'col_2': 88293.43}
                            row_keys = list(row.keys())
                            if label_idx < len(row_keys) and value_idx < len(row_keys):
                                label_key = row_keys[label_idx]
                                value_key = row_keys[value_idx]
                                label = str(row[label_key]) if row[label_key] else f"Item{len(labels)+1}"
                                value_str = str(row[value_key]) if row[value_key] else "0"
                            else:
                                continue
                        else:
                            # For list format
                            if label_idx < len(row) and value_idx < len(row):
                                label = str(row[label_idx]) if row[label_idx] else f"Item{len(labels)+1}"
                                value_str = str(row[value_idx]) if row[value_idx] else "0"
                            else:
                                continue
                        try:
                            value = float(value_str)
                        except ValueError:
                            # If conversion fails, try to extract numbers
                            import re
                            numbers = re.findall(r'-?\d+\.?\d*', value_str)
                            value = float(numbers[0]) if numbers else 0
                        
                        if chart_analysis.get("aggregation_method") == "sum":
                            data_dict[label] = data_dict.get(label, 0) + value
                        elif chart_analysis.get("aggregation_method") == "average":
                            if label in data_dict:
                                data_dict[label] = (data_dict[label] + value) / 2
                            else:
                                data_dict[label] = value
                        elif chart_analysis.get("aggregation_method") == "count":
                            data_dict[label] = data_dict.get(label, 0) + 1
                        else:
                            data_dict[label] = value
                            
                    except (ValueError, TypeError, IndexError) as e:
                        logger.warning(f"Error processing row data: {e}")
                        continue
            
            # Limit data points and apply intelligent sorting
            if data_dict:
                # Detect if labels represent years (numeric values in reasonable year range)
                labels_are_years = _detect_year_labels(list(data_dict.keys()))
                
                if labels_are_years:
                    # Sort by year in ascending order
                    sorted_items = sorted(data_dict.items(), key=lambda x: _extract_year_from_label(x[0]))
                    logger.info("Sorted by year (ascending)")
                else:
                    # Sort by value in descending order (show all data points)
                    sorted_items = sorted(data_dict.items(), key=lambda x: x[1], reverse=True)
                    logger.info("Sorted by value (descending)")
                
                labels = [item[0] for item in sorted_items]
                values = [item[1] for item in sorted_items]
                logger.info(f"Final chart data: labels={labels}, values={values}")
            else:
                logger.warning("No data extracted from rows")
        
        return labels, values
        
    except Exception as e:
        logger.error(f"Error extracting chart data with LLM guidance: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return [], []

def _detect_year_labels(labels: list) -> bool:
    """Detect if labels represent years by checking if they are numeric values in reasonable year range"""
    if not labels:
        return False
    
    try:
        for label in labels:
            year_value = _extract_year_from_label(label)
            if not (1900 <= year_value <= 2100):
                return False
        return True
    except:
        return False

def _extract_year_from_label(label) -> int:
    """Extract year value from label, handling various formats"""
    label_str = str(label)
    
    # Remove common year suffixes and prefixes
    import re
    # Remove non-digit characters except those that might be part of year format
    year_pattern = r'(\d{4})'
    matches = re.findall(year_pattern, label_str)
    
    if matches:
        return int(matches[0])
    
    # If no 4-digit pattern found, try to extract any digits
    digits_only = re.sub(r'[^\d]', '', label_str)
    if digits_only.isdigit():
        year_candidate = int(digits_only)
        if 1900 <= year_candidate <= 2100:
            return year_candidate
    
    # Fallback: try to convert directly
    try:
        return int(float(label_str))
    except:
        raise ValueError(f"Cannot extract year from label: {label}")

def _format_time_label(time_key: str, time_grouping: str) -> str:
    """Format time key for display based on grouping type"""
    try:
        if time_grouping == "year":
            return time_key
        elif time_grouping == "month":
            year, month = time_key.split('-')
            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            try:
                month_name = month_names[int(month) - 1]
                return f"{month_name} {year}"
            except (ValueError, IndexError):
                return time_key
        elif time_grouping == "week":
            year, week = time_key.split('-W')
            return f"Week {week}, {year}"
        elif time_grouping == "quarter":
            year, quarter = time_key.split('-Q')
            return f"Q{quarter} {year}"
        else:
            return time_key
    except:
        return time_key


def _format_label_based_on_context(label: str, chart_analysis: Dict[str, Any], user_input: str) -> str:
    """Format label based on query context and chart analysis"""
    try:
        if not str(label).isdigit():
            return label
            
        label_num = int(label)
        
        # Analyze user input to determine context
        user_input_lower = user_input.lower()
        
        # Check if it's explicitly about products
        if any(keyword in user_input_lower for keyword in ['product', 'item', 'goods', 'merchandise']):
            return f"Product {label}"
            
        # Check if it's explicitly about time periods
        elif any(keyword in user_input_lower for keyword in ['month', 'monthly', 'quarter', 'quarterly', 'year', 'yearly', 'time', 'trend']):
            if label_num >= 2020 and label_num <= 2030:
                return str(label)  # Year format
            elif label_num >= 1 and label_num <= 12:
                return f"Month {label_num}"
            elif label_num >= 202001 and label_num <= 203012:
                year = label_num // 100
                month = label_num % 100
                if 1 <= month <= 12:
                    return f"{year}-{month:02d}"
            else:
                return f"Period {label}"
                
        # Default logic based on number characteristics
        else:
            if label_num >= 2020 and label_num <= 2030:
                # Likely year
                return str(label)
            elif label_num >= 202001 and label_num <= 203012:
                # YYYYMM format
                year = label_num // 100
                month = label_num % 100
                if 1 <= month <= 12:
                    return f"{year}-{month:02d}"
            else:
                # For other numbers, assume product ID by default
                # This is safer than assuming months for 1-12
                return f"Product {label}"
                
    except (ValueError, TypeError):
        return str(label)

def format_time_label(time_key: str, time_grouping: str) -> str:
    """Format time labels for display"""
    try:
        if time_grouping == "month":
            year, month = time_key.split('-')
            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            month_idx = int(month) - 1
            if 0 <= month_idx < 12:
                return f"{month_names[month_idx]} {year[-2:]}"
        elif time_grouping == "week":
            if '-W' in time_key:
                year, week_str = time_key.split('-W')
                return f"{year}-W{week_str}"
            else:
                return time_key
        elif time_grouping == "quarter":
            return time_key  # Already formatted as YYYY-Q1
        elif time_grouping == "year":
            return time_key  # Already formatted as YYYY
        
        return time_key
    except:
        return time_key

def generate_fallback_chart_config(data: Dict[str, Any], user_input: str) -> Dict[str, Any]:
    """Generate fallback chart configuration (simplified version)"""
    
    # Detect chart type from user input
    user_input_lower = user_input.lower()
    chart_type = "bar"  # default
    
    if "pie chart" in user_input_lower or "pie" in user_input_lower:
        chart_type = "pie"
    elif "line chart" in user_input_lower or "line" in user_input_lower:
        chart_type = "line"
    elif "bar chart" in user_input_lower or "bar" in user_input_lower:
        chart_type = "bar"
    
    # Intelligent Y-axis label detection for fallback
    y_axis_label = "Data"
    if "sales" in user_input_lower and ("trend" in user_input_lower or "monthly" in user_input_lower):
        y_axis_label = "Sales Amount ($)"
    elif "sales" in user_input_lower and "proportion" in user_input_lower:
        y_axis_label = "Sales Proportion (%)"
    elif "count" in user_input_lower or "number" in user_input_lower:
        y_axis_label = "Count"
    elif "amount" in user_input_lower or "revenue" in user_input_lower:
        y_axis_label = "Amount ($)"
    elif "price" in user_input_lower:
        y_axis_label = "Price ($)"
    
    chart_config = {
        "type": chart_type,
        "data": {
            "labels": ["No Data"],
            "datasets": [{
                "label": y_axis_label,
                "data": [0],
                "backgroundColor": ["rgba(54, 162, 235, 0.6)"],
                "borderColor": ["rgba(54, 162, 235, 1)"],
                "borderWidth": 2
            }]
        },
        "options": {
            "responsive": True,
            "plugins": {
                "title": {
                    "display": True,
                    "text": "Data Chart",
                    "font": {"size": 16, "weight": "bold"}
                }
            }
        }
    }
    
            # Try to extract basic information from data
    try:
        if isinstance(data, dict) and "rows" in data and data["rows"]:
            rows = data["rows"][:5]  # Only take first 5 rows to avoid overly complex charts
            labels = []
            values = []
            
            for i, row in enumerate(rows):
                if len(row) >= 3:
                    label = str(row[2]) if row[2] else f"Item{i+1}"
                    value = float(row[6]) if len(row) > 6 and row[6] else i+1
                    labels.append(label)
                    values.append(value)
            
            if labels and values:
                chart_config["data"]["labels"] = labels
                chart_config["data"]["datasets"][0]["data"] = values
                
    except Exception as e:
        logger.warning(f"Fallback chart generation error: {e}")
    
    return chart_config

# QuickChart image generation removed - now using AntV interactive charts

# Enhanced flow processing function with WebSocket support
def get_compiled_app():
    """
    Build and compile the LangGraph workflow app.
    Centralizes workflow construction so both normal run and resume reuse identical graph.
    """
    return create_workflow()

def create_workflow():
    """Create the new workflow with mandatory RAG + optional SQL-Agent architecture"""
    workflow = StateGraph(GraphState)
    
    # Add nodes to the graph (6 nodes instead of 8)
    workflow.add_node("start_node", lambda state: state)  # Start node just passes through
    workflow.add_node("rag_query_node", rag_query_node)  # Combined RAG node
    workflow.add_node("router_node", router_node)  # Router node (binary classification)
    workflow.add_node("sql_agent_node", sql_agent_node)  # SQL-Agent node (ReAct mode)
    workflow.add_node("chart_process_node", chart_process_node)  # Chart processing node
    workflow.add_node("llm_processing_node", llm_processing_node)  # LLM integration processing node
    workflow.add_node("interrupt_node", interrupt_node)  # HITL interrupt node
    workflow.add_node("end_node", lambda state: {"success": True})

    # Set entry point
    workflow.set_entry_point("start_node")
    
    # Workflow connection: start → rag_query → router
    workflow.add_edge("start_node", "rag_query_node")
    workflow.add_edge("rag_query_node", "router_node")

    # Router node routing: Determine if SQL-Agent is needed
    workflow.add_conditional_edges(
        "router_node",
        lambda state: "sql_agent_node" if state.get("need_sql_agent", False) else "llm_processing_node",
        {
            "sql_agent_node": "sql_agent_node",  # Needs SQL-Agent
            "llm_processing_node": "llm_processing_node"  # No SQL-Agent needed
        }
    )

    # SQL-Agent node routing: Determine if chart is needed
    workflow.add_conditional_edges(
        "sql_agent_node",
        lambda state: "chart_process_node" if state.get("chart_suitable", False) else "llm_processing_node",
        {
            "chart_process_node": "chart_process_node",  # Needs chart
            "llm_processing_node": "llm_processing_node"  # No chart needed
        }
    )

    # Chart processing node → LLM processing node
    workflow.add_edge("chart_process_node", "llm_processing_node")

    # LLM processing node → End
    workflow.add_edge("llm_processing_node", "end_node")

    # Compile the workflow
    app = workflow.compile()
    
    logger.info("New workflow created with 6 nodes: start → rag_query → router → [sql_agent → chart?] → llm_processing → end")
    
    return app

    # Chart process node goes to LLM processing
    workflow.add_edge("chart_process_node", "llm_processing_node")
    
    # LLM processing goes to end
    workflow.add_edge("llm_processing_node", "end_node")
    
    # Interrupt node goes to end (workflow stops)
    workflow.add_edge("interrupt_node", "end_node")

    # Set finish point
    workflow.set_finish_point("end_node")

    # Compile the graph
    return workflow.compile()
# Chart Decision Node - determines if chart should be generated
def chart_decision_node(state: GraphState) -> GraphState:
    """Chart Decision Node: determine if chart should be generated based on query path and data"""
    query_path = state.get("query_path", "rag_only")
    need_chart = state.get("need_chart", False)
    structured_data = state.get("structured_data")
    
    logger.info(f"Chart Decision Node - Path: {query_path}, Has data: {bool(structured_data)}")
    
    # All SQL paths should try to generate charts (as per requirement)
    if query_path in ["sql_only", "rag_sql"] and structured_data:
        rows = structured_data.get("rows", [])
        if rows and len(rows) > 0:
            logger.info(f"Chart Decision - Generating chart for {query_path} path with {len(rows)} rows")
            return {
                **state,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "chart_decision": {
                        "status": "completed",
                        "timestamp": time.time(),
                        "decision": "generate_chart",
                        "reason": f"SQL path with {len(rows)} rows"
                    }
                }
            }
    
    logger.info(f"Chart Decision - No chart needed for {query_path} path")
    return {
        **state,
        "node_outputs": {
            **state.get("node_outputs", {}),
            "chart_decision": {
                "status": "completed",
                "timestamp": time.time(),
                "decision": "skip_chart",
                "reason": f"No chart needed for {query_path} path"
            }
        }
    }

# Chart Decision Router Function
def chart_decision_router(state: GraphState) -> str:
    """Chart Decision Router: determine routing based on chart decision"""
    query_path = state.get("query_path", "rag_only")
    structured_data = state.get("structured_data")
    
    # All SQL paths should try to generate charts (as per requirement)
    if query_path in ["sql_only", "rag_sql"] and structured_data:
        rows = structured_data.get("rows", [])
        if rows and len(rows) > 0:
            return "generate_chart"
    
    return "skip_chart"

# Enhanced Chart Process Node
def _analyze_chart_suitability(structured_data: Dict[str, Any], user_input: str) -> Dict[str, Any]:
    """Analyze if data is suitable for chart generation"""
    try:
        rows = structured_data.get("rows", [])
        columns = structured_data.get("columns", [])
        
        # 1. Check data row count
        if len(rows) < 2:
            return {"suitable": False, "reason": "Insufficient data rows (at least 2 rows required)"}
        
        if len(rows) > 1000:
            return {"suitable": False, "reason": "Too many data rows (exceeds 1000 rows)"}
        
        # 2. Check column count
        if len(columns) < 2:
            return {"suitable": False, "reason": "Insufficient data columns (at least 2 columns required)"}
        
        # 3. Check for numeric columns
        numeric_columns = []
        for col in columns:
            if _has_numeric_column(rows, col):
                numeric_columns.append(col)
        
        if not numeric_columns:
            return {"suitable": False, "reason": "No numeric columns found"}
        
        # 4. Check if user input contains chart-related keywords
        chart_keywords = ["chart", "pie", "bar", "line", "graph", "visualization", "proportion", "distribution", "trend"]
        has_chart_intent = any(keyword.lower() in user_input.lower() for keyword in chart_keywords)
        
        if not has_chart_intent:
            return {"suitable": False, "reason": "User question does not involve chart generation"}
        
        # 5. Data quality check
        if len(rows) > 50:
            # For large datasets, check for duplicates or excessive empty values
            sample_rows = rows[:10]
            empty_count = sum(1 for row in sample_rows if any(str(val).strip() == "" for val in row.values()))
            if empty_count > len(sample_rows) * 0.5:
                return {"suitable": False, "reason": "Poor data quality (too many empty values)"}
        
        return {
            "suitable": True,
            "reason": "Data suitable for chart generation",
            "numeric_columns": numeric_columns,
            "row_count": len(rows),
            "column_count": len(columns)
        }
        
    except Exception as e:
        logger.warning(f"Chart suitability analysis failed: {e}")
        return {"suitable": False, "reason": f"Data suitability analysis failed: {str(e)}"}

def _has_numeric_column(rows: List[Dict], column_name: str) -> bool:
    """Check if specified column contains numeric data"""
    try:
        numeric_count = 0
        total_count = 0
        
        for row in rows[:20]:  # Only check first 20 rows
            value = row.get(column_name, "")
            if value is None or str(value).strip() == "":
                continue
            
            total_count += 1
            
            # Try to convert to number
            try:
                float(str(value).replace(",", "").replace("%", ""))
                numeric_count += 1
            except (ValueError, TypeError):
                pass
        
        # If more than 50% of values are numbers, consider it a numeric column
        return total_count > 0 and (numeric_count / total_count) > 0.5
        
    except Exception:
        return False

def chart_process_node(state: GraphState) -> GraphState:
    """Enhanced Chart Process Node: Integrate data suitability analysis + generate chart config + render chart"""
    try:
        structured_data = state.get("structured_data")
        user_input = state["user_input"]
        
        if not structured_data:
            logger.warning("Chart Process Node - No structured data available")
            return {
                **state,
                "chart_suitable": False,
                "chart_error": "No structured data available",
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "chart_process": {
                        "status": "skipped",
                        "reason": "No structured data",
                        "timestamp": time.time()
                    }
                }
            }
        
        logger.info(f"Chart Process Node - Analyzing data suitability for: {user_input}")
        
        # Step 1: Data suitability analysis
        suitability_result = _analyze_chart_suitability(structured_data, user_input)
        
        if not suitability_result["suitable"]:
            logger.info(f"Chart not suitable: {suitability_result['reason']}")
            return {
                **state,
                "chart_suitable": False,
                "chart_error": suitability_result["reason"],
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "chart_process": {
                        "status": "skipped",
                        "reason": suitability_result["reason"],
                        "timestamp": time.time()
                    }
                }
            }
        
        logger.info("Chart suitable - Proceeding with chart generation")
        
        # Step 2: Generate chart configuration
        chart_config = generate_chart_config(structured_data, user_input)
        if not chart_config:
            logger.warning("Chart config generation failed")
            return {
                **state,
                "chart_suitable": True,
                "chart_config": None,
                "chart_data": None,
                "chart_error": "Chart config generation failed",
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "chart_process": {
                        "status": "failed",
                        "reason": "Chart config generation failed",
                        "timestamp": time.time()
                    }
                }
            }
        # Success - Extract data for frontend
        chart_data = chart_config.get("data", {}).get("labels", [])
        chart_type = chart_config.get("type", "pie")
        
        logger.info("Chart Process completed successfully")
        return {
            **state,
            "chart_suitable": True,
            "chart_config": chart_config,
            "chart_data": chart_data,
            "chart_type": chart_type,
            "node_outputs": {
                **state.get("node_outputs", {}),
                "chart_process": {
                    "status": "completed",
                    "chart_type": chart_type,
                    "timestamp": time.time()
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Chart Process Node failed: {e}", exc_info=True)
        return {
            **state, 
            "chart_suitable": False,
            "chart_error": str(e),
            "node_outputs": {
                **state.get("node_outputs", {}),
                "chart_process": {
                    "status": "error",
                    "error": str(e),
                    "timestamp": time.time()
                }
            }
        }

    # Use the new workflow structure
    return create_workflow()
async def resume_workflow_from_paused_state(
    execution_id: str,
    paused_state: Dict[str, Any],
    paused_node: str
) -> Dict[str, Any]:
    """
    Resume workflow execution from a paused state at a specific node.
    """
    from ..websocket.websocket_manager import websocket_manager
    
    try:
        logger.info(f"Resuming workflow execution {execution_id} from paused node {paused_node}")
        
        # Use the paused state as initial state
        initial_state = paused_state.copy()
        initial_state["execution_id"] = execution_id
        
        # Clear pause flags but keep paused node info for logging
        initial_state["hitl_status"] = "running"
        # Keep hitl_paused for debugging - don't remove it yet
        # initial_state.pop("hitl_paused", None)
        initial_state.pop("hitl_reason", None)
        
        # Strictly continue from the paused node without re-running upstream nodes
        logger.info(f"Resuming execution from node {paused_node} with state keys: {list(initial_state.keys())}")

        state: Dict[str, Any] = initial_state

        # Helper to broadcast snapshot
        async def _emit(snapshot: Dict[str, Any]):
            await websocket_manager.broadcast_execution_update(execution_id, snapshot)

        try:
            # Get the query path to determine continuation logic
            query_path = state.get("query_path", "rag_only")
            
            if paused_node == "chart_process_node":
                # Continue from chart processing to LLM processing
                state = await llm_processing_node(state)
                await _emit(state)

            elif paused_node == "sql_agent_node":
                # Continue from SQL agent to chart process or LLM processing
                chart_suitable = state.get("chart_suitable", False)
                if chart_suitable:
                    state = chart_process_node(state)
                    await _emit(state)

                state = await llm_processing_node(state)
                await _emit(state)

            elif paused_node == "rag_answer_node":
                # Continue from RAG answer to router
                state = router_node(state)
                await _emit(state)
                    
                # Then continue based on router decision
                need_sql_agent = state.get("need_sql_agent", False)
                if need_sql_agent:
                    state = await sql_agent_node(state)
                    await _emit(state)
                    
                    chart_suitable = state.get("chart_suitable", False)
                    if chart_suitable:
                        state = chart_process_node(state)
                        await _emit(state)
                    
                    state = await llm_processing_node(state)
                    await _emit(state)

            else:
                # Fallback: continue to LLM processing
                logger.warning(f"Unknown paused node {paused_node}, continuing to LLM processing")
                state = await llm_processing_node(state)
                await _emit(state)

            set_execution_final_state(execution_id, state)
            logger.info(f"Workflow execution {execution_id} resumed and completed successfully")
            return state
        except Exception:
            # Re-raise to outer handler
            raise
        
    except Exception as e:
        logger.error(f"Error resuming workflow execution {execution_id}: {e}")
        return {
            "success": False,
            "error": f"Error resuming workflow: {str(e)}",
            "execution_id": execution_id
        }


async def process_intelligent_query(
    user_input: str, 
    datasource: Dict[str, Any], 
    execution_id: str = None,
    restored_state: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Process intelligent analysis query using LangGraph, with WebSocket support.
    """
    
    # Import WebSocket manager
    from ..websocket.websocket_manager import websocket_manager
    
    if not datasource:
        return {
            "success": False,
            "error": "No active data source found. Please select or create a data source first.",
            "user_input": user_input
        }
    
    # Build compiled app
    app = get_compiled_app()
    
    # Initial state - use restored state if available
    if restored_state:
        initial_state = restored_state.copy()
        # Ensure execution_id is set
        initial_state["execution_id"] = execution_id
        # Ensure critical fields are present
        if "user_input" not in initial_state:
            initial_state["user_input"] = user_input
        if "datasource" not in initial_state:
            initial_state["datasource"] = datasource
        logger.info(f"Using restored state for execution {execution_id}")
        logger.info(f"Restored state keys: {list(initial_state.keys())}")
        logger.info(f"Restored query_type: {initial_state.get('query_type', 'NOT_SET')}")
        logger.info(f"Restored sql_task_type: {initial_state.get('sql_task_type', 'NOT_SET')}")
    else:
        initial_state = {
        "user_input": user_input,
        "datasource": datasource,
            "execution_id": execution_id,
            "need_chart": False,
            "analysis_reasoning": "",
            "detected_keywords": [],
            "query_type": None,
            # RAG related fields
            "retrieved_documents": [],
            "reranked_documents": [],
            "rag_answer": "",
            # Router related fields
            "need_sql_agent": False,
            "router_reasoning": "",
            # SQL Agent related fields
            "sql_agent_answer": "",
            "executed_sqls": [],
            "agent_intermediate_steps": [],
        "structured_data": None,
            # Chart related fields
            "chart_suitable": False,
            "chart_error": None,
        "chart_config": None,
            "chart_data": None,
            "chart_type": None,
        "chart_image": None,
            # Final result
            "final_answer": "",
        "answer": "",
            "final_result": "",
            "quality_score": 0.0,
        "retry_count": 0,
            "error": None,
            "hitl_status": "none",
            "hitl_node": None,
            "hitl_reason": None,
            "hitl_parameters": None,
            "hitl_timestamp": None,
            "node_outputs": {},
            "input": user_input,
            "output": ""
    }
    
    config = {"recursion_limit": 50, "configurable": {"execution_id": execution_id}}
    
    # Helper to emit events
    async def emit_event(event_type: WorkflowEventType, node_id: str = None, **kwargs):
        if execution_id:
            event = WorkflowEvent(
                type=event_type,
                timestamp=time.time(),  # Add current timestamp
                execution_id=execution_id, 
                node_id=node_id, 
                **kwargs
            )
            await websocket_manager.broadcast_to_execution(execution_id, event)
    
    await emit_event("execution_started", data={"query": user_input})
    
    final_state = None
    
    try:
        # Check if execution is interrupted BEFORE starting the workflow
        if execution_id in websocket_manager.execution_cancelled or execution_id in websocket_manager.hitl_interrupted_executions:
            logger.info(f"🎯 Execution {execution_id} was interrupted before workflow start, raising exception")
            from .exceptions import HITLInterruptedException
            raise HITLInterruptedException(execution_id, "preworkflow", "preworkflow_interrupted", {"user_input": user_input})

        # Single-run: stream events and accumulate final state simultaneously to avoid duplicate execution
        accumulated_state = initial_state.copy()
        
        # Define main workflow nodes to track (exclude internal LangChain sub-components)
        main_workflow_nodes = {
            'start_node', 'rag_query_node', 'router_node', 'sql_agent_node', 
            'chart_process_node', 'llm_processing_node', 'end_node'
        }
        
        try:
            async for event in app.astream_events(initial_state, config, version="v1"):
                kind = event.get("event")
                node_name = event.get("name", "")

                if kind == "on_chain_start":
                    # Only log and emit events for main workflow nodes, not internal LangChain components
                    if node_name in main_workflow_nodes:
                        logger.info(f"Node started: {node_name}")
                        await emit_event("node_started", node_id=node_name)
                    else:
                        logger.debug(f"Internal component started: {node_name}")

                elif kind == "on_chain_end":
                    # Only log and emit events for main workflow nodes, not internal LangChain components
                    if node_name in main_workflow_nodes:
                        logger.info(f"Node completed: {node_name}")
                        data = event.get("data")
                        # Accumulate any state-like data emitted by nodes
                        if isinstance(data, dict):
                            for key, value in data.items():
                                accumulated_state[key] = value
                        await emit_event("node_completed", node_id=node_name, data=data)
                    else:
                        logger.debug(f"Internal component completed: {node_name}")

                elif kind == "on_chain_error":
                    # Log errors for all nodes, but only emit events for main workflow nodes
                    if node_name in main_workflow_nodes:
                        logger.error(f"Node error: {node_name} - {event.get('data')}")
                        await emit_event("node_error", node_id=node_name, error=str(event.get("data", "")))
                    else:
                        logger.error(f"Internal component error: {node_name} - {event.get('data')}")

            # After events stream finishes, treat accumulated_state as final_state
            final_state = accumulated_state

            # Save execution state for HITL operations
            set_execution_final_state(execution_id, final_state)

            # Check if final state indicates interrupted status
            if final_state.get("hitl_status") == "interrupted":
                logger.info(f"🎯 Workflow detected interrupted state in final state for execution {execution_id}")
                await websocket_manager.send_to_client(
                    websocket_manager.execution_to_client.get(execution_id, ""),
                    {
                        "type": "hitl_interrupted",
                        "execution_id": execution_id,
                        "node_name": final_state.get("hitl_interrupted", "unknown"),
                        "reason": final_state.get("hitl_reason", "paused"),
                        "current_state": final_state,
                        "timestamp": time.time()
                    }
                )
                return {
                    "success": True,
                    "user_input": user_input,
                    "hitl_status": "paused",
                    "hitl_node": final_state.get("hitl_paused"),
                    "hitl_reason": final_state.get("hitl_reason"),
                    **final_state
                }

            # Check if execution is currently paused (even if not in final state)
            if execution_id in websocket_manager.execution_paused or execution_id in websocket_manager.hitl_interrupted_executions:
                logger.info(f"🎯 Execution {execution_id} is currently paused, sending pause notification")
                await websocket_manager.send_to_client(
                    websocket_manager.execution_to_client.get(execution_id, ""),
                    {
                        "type": "hitl_paused",
                        "execution_id": execution_id,
                        "node_name": "workflow_completion",
                        "reason": "paused_during_execution",
                        "current_state": final_state,
                        "timestamp": time.time()
                    }
                )
                return {
                    "success": True,
                    "user_input": user_input,
                    "hitl_status": "paused",
                    "hitl_node": "workflow_completion",
                    "hitl_reason": "paused_during_execution",
                    **final_state
                }

        except Exception as e:
            # Check if it's a HITL exception
            if "HITLPausedException" in str(type(e)) or "HITLInterruptedException" in str(type(e)):
                logger.info(f"HITL execution interrupted during state accumulation: {e}")
                final_state = accumulated_state.copy()
                # Add HITL info to final state
                final_state["hitl_status"] = "interrupted" if "HITLInterruptedException" in str(type(e)) else "paused"
                final_state["hitl_node"] = getattr(e, 'node_name', 'unknown')
                final_state["hitl_reason"] = getattr(e, 'reason', 'unknown')
            else:
                # Re-raise non-HITL exceptions
                raise
        
        # final_state should now be the complete final state
        if not isinstance(final_state, dict):
            final_state = {}
        
        logger.info(f"Final state structure: {type(final_state)}")
        logger.info(f"Sending execution_completed event for {execution_id} with final_state keys: {list(final_state.keys()) if isinstance(final_state, dict) else 'not_dict'}")
        
        # Make sure we're sending a dict for the WorkflowEvent
        final_state_for_event = final_state if isinstance(final_state, dict) else {}
        await emit_event("execution_completed", data=final_state_for_event)
        logger.info(f"Execution completed event sent for {execution_id}")
        
        # Check if this is a HITL execution (paused or interrupted)
        if "hitl_status" in final_state:
            hitl_status = final_state["hitl_status"]
            if hitl_status == "paused" or hitl_status == "interrupted":
                # Send appropriate HITL notification
                client_id = websocket_manager.execution_to_client.get(execution_id) or websocket_manager.client_to_execution.get(execution_id)
                hitl_message_type = f"hitl_{hitl_status}"
                
                await websocket_manager.send_to_client(client_id, {
                    "type": hitl_message_type,
                    "execution_id": execution_id,
                    "node_name": final_state["hitl_node"],
                    "reason": final_state["hitl_reason"],
                    "current_state": final_state,
                    "timestamp": time.time()
                })
                
                return {
                    "success": True,  # HITL actions are successful operations
                    "hitl_status": hitl_status,
                    "hitl_node": final_state["hitl_node"],
                    "hitl_reason": final_state["hitl_reason"],
                    "user_input": user_input,
                    **final_state
                }
        
        # Regular successful completion
        return {
            "success": not final_state.get("error"),
            **final_state
        }
    
    except Exception as e:
        # Check if it's a HITL exception
        if "HITLPausedException" in str(type(e)):
            logger.info(f"HITL Execution paused: {e}")
            # Send pause notification to client via WebSocket manager
            await websocket_manager.send_to_client(
                websocket_manager.execution_to_client.get(execution_id, ""), 
                {
                    "type": "hitl_paused",
                    "execution_id": execution_id,
                    "node_name": getattr(e, 'node_name', 'unknown'),
                    "reason": getattr(e, 'reason', 'paused'),
                    "current_state": getattr(e, 'state', {}),
                    "timestamp": time.time()
                }
            )
            return {
                "success": True,
                "user_input": user_input,
                "hitl_status": "paused",
                "hitl_node": getattr(e, 'node_name', 'unknown'),
                "hitl_reason": getattr(e, 'reason', 'paused'),
                **getattr(e, 'state', {})
            }
        elif "HITLInterruptedException" in str(type(e)):
            logger.info(f"HITL Execution interrupted: {e}")
            # Notify WebSocket manager about interrupt
            client_id = websocket_manager.execution_to_client.get(execution_id, "")
            if client_id:
                await websocket_manager.send_to_client(client_id, {
                    "type": "hitl_interrupted",
                    "execution_id": execution_id,
                    "node_name": getattr(e, 'node_name', 'unknown'),
                    "reason": getattr(e, 'reason', 'interrupted'),
                    "current_state": getattr(e, 'state', {}),
                    "timestamp": time.time()
                })
            return {
                "success": True,
                "user_input": user_input,
                "hitl_status": "interrupted",
                "hitl_node": getattr(e, 'node_name', 'unknown'),
                "hitl_reason": getattr(e, 'reason', 'interrupted'),
                **getattr(e, 'state', {})
            }
        else:
            # Re-raise non-HITL exceptions
            raise
    
    except Exception as e:
        logger.error(f"Error during graph execution for {execution_id}: {e}")
        await emit_event("execution_error", error=str(e))
        return {
            "success": False,
            "user_input": user_input,
            "error": str(e)
        }
    finally:
        # Final cleanup - let routes.py handle this after sending completion event
        logger.info(f"Execution {execution_id} finished or was terminated.")

def _fallback_data_analysis(sample_row: Dict[str, Any], user_input: str, total_rows: int) -> Dict[str, Any]:
    """Fallback data analysis when LLM is not available or fails"""
    try:
        sample_category = str(sample_row.get("category", ""))
        user_lower = user_input.lower()
        
        # Detect if it's time series data
        is_date_format = bool(re.match(r'^\d{4}(-\d{2})?(-\d{2})?$', sample_category))
        has_time_keywords = any(keyword in user_lower for keyword in [
            'trend', 'monthly', 'weekly', 'yearly', 'over time', 'time series', 'quarterly'
        ])
        
        is_time_series = is_date_format and has_time_keywords
        
        # Determine year filter - only apply to time series data, not category-value data
        year_filter = None
        if is_time_series:  # Only apply year filter to actual time series data
            if '2025' in user_input and '2024' not in user_input:
                year_filter = "2025"
            elif '2024' in user_input and '2025' not in user_input:
                year_filter = "2024"
        
        # Determine sort strategy
        if is_time_series:
            sort_strategy = "chronological"
        elif any(keyword in user_lower for keyword in ['top', 'highest', 'best', 'largest']):
            sort_strategy = "value_desc"
        elif any(keyword in user_lower for keyword in ['lowest', 'smallest', 'worst']):
            sort_strategy = "value_asc"
        else:
            sort_strategy = "value_desc"  # Default
        
        # Determine data limit
        if is_time_series:
            data_limit = None  # No limit for time series
        else:
            data_limit = 10  # Limit for category data
        
        # Determine chart type
        chart_type = "line" if is_time_series else "bar"
        
        return {
            "is_time_series": is_time_series,
            "data_type": "time_series" if is_time_series else "category_ranking",
            "time_period_format": "YYYY-MM" if is_date_format else None,
            "filter_criteria": {
                "year_filter": year_filter,
                "time_range": None
            },
            "sort_strategy": sort_strategy,
            "data_limit": data_limit,
            "chart_type_suggestion": chart_type
        }
    except Exception as e:
        logger.error(f"Fallback analysis failed: {e}")
        # Ultimate fallback
        return {
            "is_time_series": False,
            "data_type": "general",
            "time_period_format": None,
            "filter_criteria": {"year_filter": None, "time_range": None},
            "sort_strategy": "value_desc",
            "data_limit": 10,
            "chart_type_suggestion": "bar"
        }

def _apply_dynamic_analysis_strategy(rows: List[Dict], analysis: Dict[str, Any], user_input: str) -> List[Dict]:
    """Apply LLM's custom analysis strategy with complete flexibility"""
    try:
        processed_rows = rows.copy()
        logger.info(f"Applying dynamic strategy with analysis: {analysis}")
        
        # Let LLM's analysis guide the processing - be completely flexible
        # The analysis can contain any structure the LLM designed
        
        # Generic filtering logic that adapts to any filter structure
        if "filter" in analysis or "filtering" in analysis or "filters" in analysis:
            filter_config = analysis.get("filter") or analysis.get("filtering") or analysis.get("filters")
            processed_rows = _apply_flexible_filters(processed_rows, filter_config, user_input)
        
        # Generic sorting logic that adapts to any sort instruction
        if "sort" in analysis or "sorting" in analysis or "order" in analysis:
            sort_config = analysis.get("sort") or analysis.get("sorting") or analysis.get("order")
            processed_rows = _apply_flexible_sorting(processed_rows, sort_config, user_input)
        
        # Generic limiting logic that adapts to any limit instruction
        if "limit" in analysis or "top" in analysis or "max" in analysis or "count" in analysis:
            limit_config = analysis.get("limit") or analysis.get("top") or analysis.get("max") or analysis.get("count")
            processed_rows = _apply_flexible_limiting(processed_rows, limit_config, user_input)
        
        # Generic transformation logic for any custom processing
        if "transform" in analysis or "processing" in analysis or "format" in analysis:
            transform_config = analysis.get("transform") or analysis.get("processing") or analysis.get("format")
            processed_rows = _apply_flexible_transformations(processed_rows, transform_config, user_input)
        
        logger.info(f"Dynamic strategy applied, {len(processed_rows)} rows after processing")
        return processed_rows
        
    except Exception as e:
        logger.error(f"Error applying dynamic strategy: {e}")
        return rows  # Return original rows if processing fails


def _apply_standard_analysis_strategy(rows: List[Dict], analysis: Dict[str, Any]) -> List[Dict]:
    """Apply standard analysis strategy based on fallback detection"""
    processed_rows = rows.copy()
    
    # Apply filtering based on analysis
    filter_criteria = analysis.get("filter_criteria", {})
    year_filter = filter_criteria.get("year_filter")
    time_range = filter_criteria.get("time_range")
    
    if year_filter:
        processed_rows = [row for row in processed_rows 
                        if str(row.get("category", "")).startswith(year_filter)]
        logger.info(f"Applied year filter '{year_filter}': {len(processed_rows)} rows remaining")
    
    if time_range and analysis.get("is_time_series"):
        start_period = time_range.get("start")
        end_period = time_range.get("end")
        if start_period and end_period:
            processed_rows = [row for row in processed_rows 
                            if start_period <= str(row.get("category", "")) <= end_period]
            logger.info(f"Applied time range filter {start_period} to {end_period}: {len(processed_rows)} rows remaining")
    
    # Apply sorting based on analysis
    sort_strategy = analysis.get("sort_strategy", "value_desc")
    
    if sort_strategy == "chronological":
        def sort_time_key(row):
            category = str(row.get("category", ""))
            try:
                if re.match(r'^\d{4}-\d{2}$', category):  # YYYY-MM
                    year, month = category.split('-')
                    return int(year) * 100 + int(month)
                elif re.match(r'^\d{4}-\d{2}-\d{2}$', category):  # YYYY-MM-DD
                    return category  # String comparison works for ISO dates
                elif re.match(r'^\d{4}$', category):  # YYYY
                    return int(category)
                else:
                    return category
            except:
                return category
                
        processed_rows = sorted(processed_rows, key=sort_time_key)
        logger.info("Applied chronological sorting")
        
    elif sort_strategy == "value_desc":
        processed_rows = sorted(processed_rows, key=lambda x: x.get('value', 0), reverse=True)
        logger.info("Applied value descending sorting")
        
    elif sort_strategy == "value_asc":
        processed_rows = sorted(processed_rows, key=lambda x: x.get('value', 0))
        logger.info("Applied value ascending sorting")
        
    elif sort_strategy == "alphabetical":
        processed_rows = sorted(processed_rows, key=lambda x: str(x.get('category', '')))
        logger.info("Applied alphabetical sorting")
    
    # Apply data limiting based on analysis
    data_limit = analysis.get("data_limit")
    if data_limit and len(processed_rows) > data_limit:
        processed_rows = processed_rows[:data_limit]
        logger.info(f"Limited data to {data_limit} points")
    
    return processed_rows


def _apply_flexible_filters(rows: List[Dict], filter_config: Any, user_input: str) -> List[Dict]:
    """Apply flexible filtering based on LLM's filter configuration"""
    if not filter_config:
        return rows
    
    try:
        # Handle different filter config structures
        if isinstance(filter_config, dict):
            for filter_key, filter_value in filter_config.items():
                if filter_key.lower() in ['year', 'year_filter']:
                    # For category-value data, year filters don't apply to categories
                    # Skip year filtering for category-value data structure
                    logger.info(f"Skipping year filter '{filter_value}' for category-value data structure")
                elif filter_key.lower() in ['range', 'time_range']:
                    if isinstance(filter_value, dict) and 'start' in filter_value and 'end' in filter_value:
                        start, end = filter_value['start'], filter_value['end']
                        rows = [row for row in rows if start <= str(row.get("category", "")) <= end]
                        logger.info(f"Applied flexible range filter {start}-{end}: {len(rows)} rows remaining")
        elif isinstance(filter_config, str):
            # Handle string-based filter instructions
            if any(year in filter_config for year in ['2025', '2024', '2023']):
                # Skip year filtering for category-value data structure
                logger.info(f"Skipping year filter in string config for category-value data structure")
        
        return rows
        
    except Exception as e:
        logger.warning(f"Error applying flexible filters: {e}")
        return rows


def _apply_flexible_sorting(rows: List[Dict], sort_config: Any, user_input: str) -> List[Dict]:
    """Apply flexible sorting based on LLM's sort configuration"""
    if not sort_config:
        return rows
    
    try:
        if isinstance(sort_config, str):
            sort_config = sort_config.lower()
            if 'time' in sort_config or 'chronolog' in sort_config or 'date' in sort_config:
                # Apply chronological sorting
                def sort_time_key(row):
                    category = str(row.get("category", ""))
                    try:
                        import re  # Import re inside the function to avoid scope issues
                        if re.match(r'^\d{4}-\d{2}$', category):
                            year, month = category.split('-')
                            return int(year) * 100 + int(month)
                        elif re.match(r'^\d{4}$', category):
                            return int(category)
                        else:
                            return category
                    except:
                        return category
                rows = sorted(rows, key=sort_time_key)
                logger.info("Applied flexible chronological sorting")
            elif 'desc' in sort_config or 'high' in sort_config or 'large' in sort_config:
                rows = sorted(rows, key=lambda x: x.get('value', 0), reverse=True)
                logger.info("Applied flexible descending value sorting")
            elif 'asc' in sort_config or 'low' in sort_config or 'small' in sort_config:
                rows = sorted(rows, key=lambda x: x.get('value', 0))
                logger.info("Applied flexible ascending value sorting")
            elif 'alpha' in sort_config or 'name' in sort_config:
                rows = sorted(rows, key=lambda x: str(x.get('category', '')))
                logger.info("Applied flexible alphabetical sorting")
        
        elif isinstance(sort_config, dict):
            # Handle dict-based sort config
            if sort_config.get('by') == 'value' and sort_config.get('order') == 'desc':
                rows = sorted(rows, key=lambda x: x.get('value', 0), reverse=True)
            elif sort_config.get('by') == 'value' and sort_config.get('order') == 'asc':
                rows = sorted(rows, key=lambda x: x.get('value', 0))
            elif sort_config.get('by') == 'time' or sort_config.get('by') == 'chronological':
                def sort_time_key(row):
                    category = str(row.get("category", ""))
                    try:
                        import re  # Import re inside the function to avoid scope issues
                        if re.match(r'^\d{4}-\d{2}$', category):
                            year, month = category.split('-')
                            return int(year) * 100 + int(month)
                        elif re.match(r'^\d{4}$', category):
                            return int(category)
                        else:
                            return category
                    except:
                        return category
                rows = sorted(rows, key=sort_time_key)
        
        return rows
        
    except Exception as e:
        logger.warning(f"Error applying flexible sorting: {e}")
        return rows


def _apply_flexible_limiting(rows: List[Dict], limit_config: Any, user_input: str) -> List[Dict]:
    """Apply flexible limiting based on LLM's limit configuration"""
    if not limit_config:
        return rows
    
    try:
        if isinstance(limit_config, int):
            return rows[:limit_config]
        elif isinstance(limit_config, str):
            # Extract number from string
            numbers = re.findall(r'\d+', limit_config)
            if numbers:
                limit = int(numbers[0])
                logger.info(f"Applied flexible limit: {limit}")
                return rows[:limit]
        elif isinstance(limit_config, dict):
            if 'count' in limit_config:
                limit = int(limit_config['count'])
                return rows[:limit]
        
        return rows
        
    except Exception as e:
        logger.warning(f"Error applying flexible limiting: {e}")
        return rows


def _apply_flexible_transformations(rows: List[Dict], transform_config: Any, user_input: str) -> List[Dict]:
    """Apply flexible transformations based on LLM's transformation configuration"""
    if not transform_config:
        return rows
    
    try:
        # This can be extended to handle any custom transformations the LLM suggests
        # For now, just log and return as-is
        logger.info(f"Transformation config received: {transform_config}")
        return rows
        
    except Exception as e:
        logger.warning(f"Error applying flexible transformations: {e}")
        return rows 


# Global state storage for execution states
_execution_states: Dict[str, Dict[str, Any]] = {}

def get_execution_final_state(execution_id: str) -> Dict[str, Any]:
    """Get the final state of an execution for HITL operations"""
    logger.info(f"🔄 [BACKEND-LG] get_execution_final_state called")
    logger.info(f"📥 [BACKEND-LG] get_execution_final_state input params: execution_id={execution_id}")
    
    state = _execution_states.get(execution_id, {})
    logger.info(f"📊 [BACKEND-LG] get_execution_final_state found state for execution {execution_id}")
    logger.info(f"📊 [BACKEND-LG] get_execution_final_state state keys: {list(state.keys())}")
    logger.info(f"📊 [BACKEND-LG] get_execution_final_state query_type: {state.get('query_type', 'NOT_SET')}")
    logger.info(f"📊 [BACKEND-LG] get_execution_final_state sql_task_type: {state.get('sql_task_type', 'NOT_SET')}")
    
    logger.info(f"�?[BACKEND-LG] get_execution_final_state completed successfully")
    return state

def set_execution_final_state(execution_id: str, state: Dict[str, Any]):
    """Set the final state of an execution for HITL operations"""
    logger.info(f"🔄 [BACKEND-LG] set_execution_final_state called")
    logger.info(f"📥 [BACKEND-LG] set_execution_final_state input params: execution_id={execution_id}")
    logger.info(f"📥 [BACKEND-LG] set_execution_final_state state keys: {list(state.keys())}")
    
    _execution_states[execution_id] = state
    logger.info(f"📊 [BACKEND-LG] set_execution_final_state stored state for execution {execution_id}")
    logger.info(f"📊 [BACKEND-LG] set_execution_final_state stored query_type: {state.get('query_type', 'NOT_SET')}")
    logger.info(f"📊 [BACKEND-LG] set_execution_final_state stored sql_task_type: {state.get('sql_task_type', 'NOT_SET')}")
    
    logger.info(f"✅ [BACKEND-LG] set_execution_final_state completed successfully")
