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

# Import databricks-sqlalchemy to register SQLAlchemy dialect for Databricks
# This must be imported before sqlalchemy.create_engine is called
try:
    from databricks.sqlalchemy import base  # noqa: F401
except ImportError:
    pass  # databricks-sqlalchemy is optional if not using Databricks

# Also import databricks.sql for fallback direct connection
try:
    import databricks.sql  # noqa: F401
except ImportError:
    pass  # databricks-sql-connector is optional if not using Databricks

# Import smart SQLDatabase factory that uses SQLAlchemy dialect for Databricks
from ..utils.databricks_adapter import create_sql_database
from ..agents.intelligent_agent import llm, perform_rag_query, get_answer_from_sqltable_datasource, get_query_from_sqltable_datasource
# re is already imported at line 8, no need to import again
import difflib
from ..models.data_models import WorkflowEvent, WorkflowEventType, NodeStatus, DataSourceType
from ..database.db_operations import get_active_datasource
from ..config.config import Config
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.outputs import LLMResult
# Removed unused import

logger = logging.getLogger(__name__)

# ==================== ReAct Callback Handler ====================

class ReActStepCallback(BaseCallbackHandler):
    """Callback handler for collecting ReAct steps (steps will be streamed via astream_events)"""
    
    def __init__(self, execution_id: str, websocket_manager=None):
        super().__init__()
        self.execution_id = execution_id
        self.websocket_manager = websocket_manager
        self.step_index = 0
        self.current_thought = ""
        self.current_action = None
        self.steps_queue = []  # Queue for steps to be streamed
        
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> None:
        """Called when LLM starts generating (thinking step)"""
        self.current_thought = ""
        self.step_index += 1
    
    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Called when LLM finishes generating"""
        if self.current_thought:
            self.steps_queue.append({
                "type": "thought",
                "index": self.step_index,
                "content": self.current_thought
            })
    
    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Called when LLM generates a new token (for thought streaming)"""
        self.current_thought += token
    
    def on_agent_action(self, action: AgentAction, **kwargs: Any) -> None:
        """Called when agent takes an action (tool call)"""
        self.step_index += 1
        tool_name = action.tool
        tool_input = action.tool_input
        
        # Format tool input for display
        tool_input_str = json.dumps(tool_input, ensure_ascii=False, indent=2) if isinstance(tool_input, dict) else str(tool_input)
        content = f"Calling tool: {tool_name}\nInput: {tool_input_str}"
        
        self.steps_queue.append({
            "type": "action",
            "index": self.step_index,
            "content": content,
            "tool_name": tool_name,
            "tool_input": tool_input
        })
        
        self.current_action = action
    
    def on_agent_finish(self, finish: AgentFinish, **kwargs: Any) -> None:
        """Called when agent finishes"""
        self.steps_queue.append({
            "type": "thought",
            "index": self.step_index + 1,
            "content": f"Agent finished. Final answer: {finish.return_values.get('output', 'N/A')[:100]}..."
        })
    
    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """Called when tool execution ends (observation step)"""
        self.step_index += 1
        # Truncate long outputs for display
        display_output = output[:100] + "..." if len(output) > 100 else output
        
        self.steps_queue.append({
            "type": "observation",
            "index": self.step_index,
            "content": f"Tool result: {display_output}",
            "tool_name": self.current_action.tool if self.current_action else None
        })

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
    
    # === Legacy fields (removed - not used in current workflow) ===
    # query_type and sql_task_type are no longer needed as routing is based on need_sql_agent and chart_suitable

# LangGraph native interrupt implementation
def router_decision_node(state: GraphState) -> GraphState:
    """Router decision node - just passes through the state"""
    return state

def sql_agent_decision_node(state: GraphState) -> GraphState:
    """SQL agent decision node - just passes through the state"""
    return state

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
        "router_reasoning": f"Fallback rule-based decision: {'SQL needed' if need_sql else 'LLM-only'}",
        "node_outputs": {
            **state.get("node_outputs", {}),
            "router": {
                "status": "completed",
                "decision": "sql_agent" if need_sql else "llm_only",
                "reasoning": f"Fallback: {'SQL signals detected' if need_sql else 'Conceptual/document Q&A'}",
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
    
    # Get WebSocket manager for streaming ReAct steps
    from ..websocket.websocket_manager import websocket_manager
    
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
        
        # Determine database URL based on datasource type
        # For Databricks datasources, always use Databricks connection
        # For DEFAULT type, use Config.DATABASE_URL (may be SQLite or Databricks)
        if datasource['type'] != DataSourceType.DEFAULT.value:
            # For non-DEFAULT datasources (like Databricks), use Databricks connection
            # Check if Config.DATABASE_URL is already a Databricks URL
            # If not, try to build one from environment variables
            if Config.DATABASE_URL.startswith("databricks://") or Config.DATABASE_URL.startswith("databricks+connector://"):
                database_url = Config.DATABASE_URL
                logger.info("Using Databricks connection from Config.DATABASE_URL for non-DEFAULT datasource")
            else:
                # Try to build Databricks URL from environment variables
                databricks_url = Config._build_databricks_url()
                if databricks_url:
                    database_url = databricks_url
                    logger.info("Using Databricks connection built from environment variables for non-DEFAULT datasource")
                else:
                    # For non-DEFAULT datasources, Databricks connection is required
                    error_msg = "Databricks connection is required for this datasource but not configured. Please set DATABASE_URL environment variable with databricks:// format, or set Databricks environment variables (DATABRICKS_SERVER_HOSTNAME, DATABRICKS_HTTP_PATH, DATABRICKS_TOKEN)."
                    logger.error(error_msg)
                    state["error"] = error_msg
                    state["sql_agent_answer"] = error_msg
                    return state
        else:
            # For DEFAULT type, use Config.DATABASE_URL
            database_url = Config.DATABASE_URL
            logger.info(f"Using Config.DATABASE_URL for DEFAULT datasource: {database_url[:50]}...")
        
        # Use smart factory that prioritizes SQLAlchemy dialect for Databricks
        # This ensures ReAct mode works correctly with SQLDatabaseToolkit
        db = create_sql_database(
            database_url,
            include_tables=include_tables,
            sample_rows_in_table_info=0  # Set to 0 to avoid Decimal type conversion errors
        )
        
        # Detect database type for SQL generation
        # Note: databricks-sqlalchemy only supports databricks:// format (not databricks+connector://)
        is_databricks = database_url.startswith("databricks://") or database_url.startswith("databricks+connector://")
        
        # 2.5. For Databricks, discover tables from specified schema only (default: public)
        # Schema can be overridden via DATABRICKS_SCHEMA environment variable
        all_discovered_tables = []
        marts_tables_detected = []
        all_tables_by_schema = {}
        target_schema = "public"  # Default schema, can be overridden by env var
        
        if is_databricks:
            # Get schema from environment variable, default to 'public'
            target_schema = os.getenv("DATABRICKS_SCHEMA", "public")
            logger.info(f"Discovering tables from schema: {target_schema} (default: public, override via DATABRICKS_SCHEMA env var)")
            try:
                # Create a temporary toolkit to get sql_db_query tool
                from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
                temp_toolkit = SQLDatabaseToolkit(db=db, llm=llm)
                temp_tools = temp_toolkit.get_tools()
                
                sql_query_tool = None
                for tool in temp_tools:
                    if tool.name == 'sql_db_query':
                        sql_query_tool = tool
                        break
                
                if sql_query_tool:
                    import re as re_module
                    import ast
                    catalog = os.getenv("DATABRICKS_DATABASE") or os.getenv("DATABRICKS_CATALOG", "workspace")
                    
                    # Only query tables from the specified schema (default: public)
                    try:
                        tables_query = f"SHOW TABLES IN {catalog}.{target_schema}"
                        logger.info(f"Querying tables in schema {target_schema}: {tables_query}")
                        
                        schema_tables_result = sql_query_tool.invoke({"query": tables_query})
                        
                        if schema_tables_result:
                            schema_tables = []
                            schema_tables_raw = str(schema_tables_result)
                            
                            try:
                                parsed_tables = ast.literal_eval(schema_tables_raw)
                                if isinstance(parsed_tables, list):
                                    for item in parsed_tables:
                                        if isinstance(item, (tuple, list)) and len(item) >= 2:
                                            table_name = item[1] if len(item) > 1 else item[0]
                                            if table_name and table_name not in ['databaseName', 'tableName', 'namespace', 'isTemporary']:
                                                full_table_name = f"{target_schema}.{table_name}"
                                                schema_tables.append(full_table_name)
                                                all_discovered_tables.append(full_table_name)
                            except:
                                pattern = rf"{re_module.escape(target_schema)}\.(\w+)"
                                matches = re_module.findall(pattern, schema_tables_raw)
                                for match in matches:
                                    if match not in ['tableName', 'table', 'database']:
                                        full_table_name = f"{target_schema}.{match}"
                                        schema_tables.append(full_table_name)
                                        all_discovered_tables.append(full_table_name)
                            
                            if schema_tables:
                                all_tables_by_schema[target_schema] = schema_tables
                                logger.info(f"  ✅ Schema '{target_schema}': {len(schema_tables)} tables discovered")
                        else:
                            logger.warning(f"  ⚠️  No tables found in schema '{target_schema}'")
                    except Exception as schema_error:
                        logger.warning(f"  ⚠️  Error querying tables in schema '{target_schema}': {schema_error}")
                    
                    # Identify marts layer tables (now in public schema with mart_ prefix)
                    if all_discovered_tables:
                        marts_tables_detected = [
                            t for t in all_discovered_tables 
                            if 'mart_' in t.lower() or 
                            (t.startswith(f'{target_schema}.') and any(keyword in t.lower() for keyword in ['summary', 'daily', 'flow', 'usage', 'topup', 'active', 'aggregat']))
                        ]
                        
                        logger.info(f"✅ Pre-discovered {len(all_discovered_tables)} tables from schema '{target_schema}'")
                        if marts_tables_detected:
                            logger.info(f"✅ Detected {len(marts_tables_detected)} marts layer tables: {marts_tables_detected}")
                        else:
                            logger.warning("⚠️  No marts layer tables detected in discovered schema")
                else:
                    logger.warning("sql_db_query tool not available for pre-discovery")
            except Exception as e:
                logger.warning(f"Error in pre-discovery of tables: {e}")
        
        # 3. Try to use ReAct mode with create_sql_agent
        use_react_mode = False
        react_fallback_reason = None
        
        if llm:
            try:
                from langchain_community.agent_toolkits import create_sql_agent
                from langchain.agents import AgentType
                
                # Create callback for streaming ReAct steps
                react_callback = ReActStepCallback(execution_id=execution_id, websocket_manager=websocket_manager)
                
                # Try to create SQL agent with ReAct mode
                logger.info("Attempting to create SQL agent with ReAct mode...")
                agent = create_sql_agent(
                    llm=llm,
                    db=db,
                    agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                    verbose=True,
                    callbacks=[react_callback]
                )
                
                # Check if agent was created successfully
                # We'll test during actual execution instead of here to avoid double execution
                use_react_mode = True
                logger.info("ReAct agent created successfully, will attempt execution")
                    
            except Exception as e:
                react_fallback_reason = f"Failed to create ReAct agent: {str(e)}"
                logger.warning(f"ReAct mode not available, will fallback: {react_fallback_reason}")
                use_react_mode = False
        
        # 4. Execute using ReAct mode or fallback to manual mode
        if use_react_mode:
            logger.info("Executing SQL Agent in ReAct mode...")
            try:
                # Build input with context and guidance
                # Add guidance about using marts layer for statistics and RAG for metadata
                guidance = ""
                available_tables_info = ""
                if is_databricks:
                    # Build available tables information from pre-discovered tables
                    if all_discovered_tables:
                        available_tables_info = f"\n\nAVAILABLE TABLES (discovered from schema '{target_schema}'):\n"
                        # Group by schema for better readability
                        for schema, tables in all_tables_by_schema.items():
                            available_tables_info += f"  {schema} schema: {', '.join([t.split('.')[-1] for t in tables])}\n"
                        available_tables_info += f"\nTotal: {len(all_discovered_tables)} tables from schema '{target_schema}'\n"
                        
                        if marts_tables_detected:
                            available_tables_info += f"\n⚠️  IMPORTANT - MARTS LAYER TABLES (preferred for statistics):\n"
                            for marts_table in marts_tables_detected:
                                available_tables_info += f"  - {marts_table}\n"
                    
                    guidance = f"""
IMPORTANT GUIDANCE FOR SQL QUERY GENERATION:

📊 DATA WAREHOUSE ARCHITECTURE (Kimball/Medallion Design):
This database follows a layered data warehouse architecture with table name prefixes indicating data layers:

LAYER 1 - src_* (Source Layer):
   - Raw data from source systems (Airbyte ETL)
   - Use: Rarely in analytics, mainly for data quality checks
   - Examples: src_users, src_transactions, src_stations

LAYER 2 - stg_* (Staging Layer):
   - Cleaned and validated data
   - Use: For custom joins when mart_* doesn't exist, building custom aggregations
   - Examples: stg_users, stg_transactions, stg_stations

LAYER 3 - dim_* (Dimension Layer):
   - Master reference data with surrogate keys
   - Use: When need dimension attributes (user info, station details, route info, time attributes)
   - Examples: dim_user, dim_station, dim_route, dim_time
   - Key: Contains *_key (surrogate key) and descriptive attributes

LAYER 4 - fact_* (Fact Layer):
   - Transactional fact tables with measures
   - Use: Only when mart_* tables don't provide required detail or granularity
   - Examples: fact_transactions, fact_topups
   - Key: Contains dimension keys and measures (amount, count, etc.)

LAYER 5 - mart_* (Marts Layer) - ⭐ STRONGLY PREFERRED:
   - Pre-aggregated analytical tables optimized for reporting
   - Use: MANDATORY for ALL statistical, metric, trend, and aggregation queries
   - Examples: mart_daily_active_users, mart_daily_topup_summary, mart_station_flow_daily
   - Benefits: Pre-computed, faster, optimized for analytics

QUERY TYPE TO TABLE SELECTION GUIDE:
- Statistical queries (counts, sums, averages) → mart_* (MANDATORY)
- Time series trends (daily, monthly, yearly) → mart_* (MANDATORY)
- Category/group comparisons → mart_* (MANDATORY)
- Station/route rankings → mart_station_flow_daily, mart_route_usage_summary (MANDATORY)
- User distributions → mart_user_card_type_summary (MANDATORY)
- Detailed transaction records → fact_* (only if mart_* insufficient)
- Dimension attributes → dim_* (for descriptive data)
- Raw source data → src_* (rarely needed)
- Cleaned data for custom logic → stg_* (use sparingly)

1. STATISTICAL/METRIC/TREND QUERIES - ALWAYS use mart_* tables (MANDATORY for data warehouse design):
   - For ANY aggregated statistics, metrics, summaries, trends, or pre-calculated data, MANDATORY to use mart_* tables in public schema
   - The mart_* tables follow Kimball/Medallion Architecture data warehouse design patterns and contain pre-aggregated metrics optimized for analytical queries
   - Design principle: mart_* tables are specifically designed for reporting and analytics, containing daily/weekly/monthly summaries, aggregations, and business metrics
   - When querying for statistics (counts, sums, averages, trends, comparisons), ALWAYS look for mart_* tables first (e.g., public.mart_daily_active_users, public.mart_daily_topup_summary)
   - NEVER aggregate from fact_*/dim_* tables when equivalent mart_* tables exist - mart_* tables are pre-computed, more efficient, and follow best practices
   - Only use fact_*/dim_* tables when mart_* tables don't provide the required granularity or specific metrics
   {"   - Available mart_* tables: " + ", ".join(marts_tables_detected) + " - Use these for ALL statistical queries!" if marts_tables_detected else ""}

2. METADATA INFORMATION - Use RAG knowledge base first:
   - For table structures, column definitions, business rules, and data relationships, FIRST check the background knowledge from RAG
   - The RAG knowledge base contains metadata documentation about tables, schemas, and business logic
   - Only if RAG doesn't provide sufficient information, use SQL-Agent's ReAct tools to explore the database schema
   - Use tools like sql_db_list_tables and sql_db_schema to discover table structures when RAG metadata is insufficient
   - NOTE: The sql_db_list_tables tool may only show tables from the default schema. Use the AVAILABLE TABLES list below to see all tables from the specified schema (default: public).

3. DATA EXPLORATION PRIORITY:
   - Step 1: Check RAG background knowledge for metadata and table information
   - Step 2: Check the AVAILABLE TABLES list below to see all available tables (all tables are in public schema)
   - Step 3: For statistical/metric/trend queries, MANDATORY to use mart_* tables (e.g., public.mart_daily_active_users) over aggregating from fact_*/dim_* tables
   - Step 4: Only use fact_*/dim_* tables when mart_* tables don't have the required metrics or granularity

4. TABLE NAMING:
   - All tables are in public schema. Always use public.table_name format when referencing tables (e.g., public.mart_daily_active_users, public.mart_station_flow_daily, public.fact_transactions)
   - Use table name prefixes to identify layers: src_*, stg_*, dim_*, fact_*, mart_*
   - For statistical queries, ALWAYS prefer mart_* tables (e.g., public.mart_daily_active_users for daily metrics, public.mart_daily_topup_summary for top-up trends)
{available_tables_info}
"""
                agent_input = f"{user_input}\n\n{guidance}\nBackground knowledge from knowledge base: {rag_answer if rag_answer else '(No RAG metadata available - use ReAct tools to explore database schema)'}"
                
                # Stream agent execution
                intermediate_steps = []
                final_answer = ""
                executed_sqls = []
                structured_data = None
                
                # Use astream_events to capture intermediate steps and stream them
                step_counter = 0
                logger.info(f"Starting astream_events iteration for ReAct agent...")
                
                # Try to capture all events, including internal ones
                event_count = 0
                async for event in agent.astream_events(
                    {"input": agent_input},
                    version="v2"
                ):
                    event_count += 1
                    # Stream ReAct steps in real-time
                    event_name = event.get("event")
                    event_name_str = event.get("name", "")
                    
                    # Only log important events to reduce noise
                    if event_name in ["on_agent_action", "on_tool_start", "on_tool_end", "on_chain_stream", "on_chain_end"]:
                        logger.info(f"ReAct event #{event_count}: {event_name}, name: {event_name_str}, event_keys: {list(event.keys())}")
                    
                    # Handle on_chain_stream events which contain action information for SQL Agent
                    # The chunk contains structured action objects, not text
                    if event_name == "on_chain_stream" and event_name_str == "SQL Agent Executor":
                        stream_data = event.get("data", {})
                        chunk = stream_data.get("chunk", {})
                        
                        # Check if chunk contains steps (AgentStep objects with action and observation)
                        if isinstance(chunk, dict) and "steps" in chunk:
                            steps = chunk["steps"]
                            if isinstance(steps, list) and len(steps) > 0:
                                # Process each step
                                for step_obj in steps:
                                    # Extract action and observation from AgentStep
                                    action_obj = getattr(step_obj, "action", None) if hasattr(step_obj, "action") else None
                                    observation = getattr(step_obj, "observation", None) if hasattr(step_obj, "observation") else None
                                    
                                    if action_obj:
                                        tool_name = getattr(action_obj, "tool", None) if hasattr(action_obj, "tool") else None
                                        tool_input_raw = getattr(action_obj, "tool_input", None) if hasattr(action_obj, "tool_input") else None
                                        
                                        if tool_name:
                                            # Format tool_input as dict
                                            if isinstance(tool_input_raw, dict):
                                                tool_input_dict = tool_input_raw
                                            elif isinstance(tool_input_raw, str):
                                                tool_input_dict = {"query": tool_input_raw} if tool_name == "sql_db_query" else {"input": tool_input_raw}
                                            else:
                                                tool_input_dict = {"input": str(tool_input_raw) if tool_input_raw else ""}
                                            
                                            # Check if we already have this action step
                                            existing_step_idx = None
                                            for idx, step in enumerate(intermediate_steps):
                                                if step.get("tool") == tool_name:
                                                    existing_step_idx = idx
                                                    break
                                            
                                            if existing_step_idx is None:
                                                # New action step
                                                step_counter += 1
                                                logger.info(f"Captured action from on_chain_stream steps: tool={tool_name}, input_type={type(tool_input_raw).__name__}")
                                                
                                                tool_input_str = json.dumps(tool_input_dict, ensure_ascii=False, indent=2) if isinstance(tool_input_dict, dict) else str(tool_input_dict)
                                                content = f"Calling tool: {tool_name}\nInput: {tool_input_str[:100]}{'...' if len(tool_input_str) > 100 else ''}"
                                                
                                                await websocket_manager.stream_react_step(
                                                    execution_id=execution_id,
                                                    step_type="action",
                                                    step_index=step_counter,
                                                    content=content,
                                                    node_id="sql_agent_node",
                                                    tool_name=tool_name,
                                                    tool_input=tool_input_dict
                                                )
                                                
                                                intermediate_steps.append({
                                                    "step": "action",
                                                    "tool": tool_name,
                                                    "input": tool_input_dict,
                                                    "observation": str(observation) if observation else ""
                                                })
                                            else:
                                                # Update existing step with observation
                                                if observation:
                                                    # CRITICAL: Truncate large observations to prevent context length exceeded errors
                                                    observation_str = str(observation)
                                                    MAX_OBSERVATION_LENGTH = 1048576  # 1MB limit
                                                    if len(observation_str) > MAX_OBSERVATION_LENGTH:
                                                        logger.warning(f"⚠️  Observation too large ({len(observation_str)} chars), truncating to {MAX_OBSERVATION_LENGTH} chars")
                                                        if tool_name == "sql_db_query":
                                                            # Try to parse and summarize SQL results
                                                            try:
                                                                parsed = _parse_agent_query_result(observation_str)
                                                                if parsed and parsed.get("rows"):
                                                                    rows = parsed.get("rows", [])
                                                                    truncated_rows = rows[:100]
                                                                    observation_str = f"Query returned {len(rows)} rows. Showing first 100 rows:\n{str(truncated_rows)}"
                                                                    if len(observation_str) > MAX_OBSERVATION_LENGTH:
                                                                        observation_str = observation_str[:MAX_OBSERVATION_LENGTH] + f"\n... (truncated)"
                                                            except:
                                                                observation_str = observation_str[:MAX_OBSERVATION_LENGTH] + f"\n... (truncated, original length: {len(observation_str)} chars)"
                                                        else:
                                                            observation_str = observation_str[:MAX_OBSERVATION_LENGTH] + f"\n... (truncated, original length: {len(observation_str)} chars)"
                                                    
                                                    intermediate_steps[existing_step_idx]["observation"] = observation_str
                                                    logger.info(f"Updated step {existing_step_idx} with observation: tool={tool_name}, observation_length={len(observation_str)}")
                                                    
                                                    # Try to parse structured_data from observation if it's a SQL query
                                                    if tool_name == "sql_db_query" and observation:
                                                        parsed = _parse_agent_query_result(str(observation))
                                                        if parsed:
                                                            structured_data = parsed
                                                            logger.info(f"Parsed structured_data from steps observation: {len(parsed.get('rows', []))} rows")
                        
                        # Check if chunk contains actions (structured format) - fallback
                        elif isinstance(chunk, dict) and "actions" in chunk:
                            actions = chunk["actions"]
                            if isinstance(actions, list) and len(actions) > 0:
                                # Get the first action (AgentAction object)
                                action_obj = actions[0]
                                
                                # Extract tool name and input from AgentAction object
                                tool_name = getattr(action_obj, "tool", None) if hasattr(action_obj, "tool") else None
                                tool_input_raw = getattr(action_obj, "tool_input", None) if hasattr(action_obj, "tool_input") else None
                                
                                if tool_name:
                                    # Format tool_input as dict for WebSocket
                                    if isinstance(tool_input_raw, dict):
                                        tool_input_dict = tool_input_raw
                                    elif isinstance(tool_input_raw, str):
                                        # If tool_input is a string (like SQL query), wrap it in dict
                                        tool_input_dict = {"query": tool_input_raw} if tool_name == "sql_db_query" else {"input": tool_input_raw}
                                    else:
                                        tool_input_dict = {"input": str(tool_input_raw) if tool_input_raw else ""}
                                    
                                    # Check if we already have this action step
                                    if not intermediate_steps or intermediate_steps[-1].get("tool") != tool_name:
                                        step_counter += 1
                                        logger.info(f"Captured action from on_chain_stream: tool={tool_name}, input_type={type(tool_input_raw).__name__}")
                                        
                                        # Format content for display
                                        tool_input_str = json.dumps(tool_input_dict, ensure_ascii=False, indent=2) if isinstance(tool_input_dict, dict) else str(tool_input_dict)
                                        content = f"Calling tool: {tool_name}\nInput: {tool_input_str[:200]}{'...' if len(tool_input_str) > 200 else ''}"
                                        
                                        await websocket_manager.stream_react_step(
                                            execution_id=execution_id,
                                            step_type="action",
                                            step_index=step_counter,
                                            content=content,
                                            node_id="sql_agent_node",
                                            tool_name=tool_name,
                                            tool_input=tool_input_dict  # Always pass as dict
                                        )
                                        
                                        intermediate_steps.append({
                                            "step": "action",
                                            "tool": tool_name,
                                            "input": tool_input_dict
                                        })
                        else:
                            # Fallback: Try to parse from text if chunk is text-based
                            chunk_text = ""
                            if isinstance(chunk, dict):
                                chunk_text = chunk.get("content", chunk.get("text", chunk.get("output", str(chunk))))
                            elif isinstance(chunk, str):
                                chunk_text = chunk
                            else:
                                chunk_text = str(chunk)
                            
                            # Check if this chunk contains action information as text
                            if chunk_text and ("Action:" in chunk_text or "Action Input:" in chunk_text):
                                logger.info(f"Found action text in on_chain_stream: {chunk_text[:100]}")
                                
                                # Parse action from text
                                import re
                                action_match = re.search(r"Action:\s*(\w+)", chunk_text)
                                action_input_match = re.search(r"Action Input:\s*(.+?)(?:\n|$)", chunk_text, re.DOTALL)
                                
                                if action_match:
                                    tool_name = action_match.group(1)
                                    tool_input_str = action_input_match.group(1).strip() if action_input_match else ""
                                    
                                    # Format as dict
                                    tool_input_dict = {"query": tool_input_str} if tool_name == "sql_db_query" else {"input": tool_input_str}
                                    
                                    # Check if we already have this action step
                                    if not intermediate_steps or intermediate_steps[-1].get("tool") != tool_name:
                                        step_counter += 1
                                        logger.info(f"Captured action from on_chain_stream text: tool={tool_name}, input_length={len(tool_input_str)}")
                                        
                                        content = f"Calling tool: {tool_name}\nInput: {tool_input_str[:200]}{'...' if len(tool_input_str) > 200 else ''}"
                                        
                                        await websocket_manager.stream_react_step(
                                            execution_id=execution_id,
                                            step_type="action",
                                            step_index=step_counter,
                                            content=content,
                                            node_id="sql_agent_node",
                                            tool_name=tool_name,
                                            tool_input=tool_input_dict  # Always pass as dict
                                        )
                                        
                                        intermediate_steps.append({
                                            "step": "action",
                                            "tool": tool_name,
                                            "input": tool_input_dict
                                        })
                    
                    if event_name == "on_llm_start":
                        step_counter += 1
                        await websocket_manager.stream_react_step(
                            execution_id=execution_id,
                            step_type="thought",
                            step_index=step_counter,
                            content="Thinking about the query...",
                            node_id="sql_agent_node"
                        )
                    elif event_name == "on_agent_action":
                        step_counter += 1
                        # Fix: event structure for on_agent_action
                        action_data = event.get("data", {})
                        logger.info(f"on_agent_action event - full event keys: {list(event.keys())}, data keys: {list(action_data.keys())}")
                        
                        # Try different possible structures - check the actual event structure
                        action = None
                        if "output" in action_data:
                            action = action_data["output"]
                        elif "action" in action_data:
                            action = action_data["action"]
                        else:
                            action = action_data
                        
                        # Log the full action structure for debugging
                        logger.info(f"Action structure: {type(action).__name__}, content: {str(action)[:100]}")
                        
                        if isinstance(action, dict):
                            tool_name = action.get("tool", action.get("name", event.get("name", "unknown")))
                            tool_input = action.get("tool_input", action.get("input", action.get("tool_input_str", "")))
                        else:
                            # Fallback: try to extract from event directly
                            tool_name = event.get("name", "unknown")
                            tool_input = action_data.get("input", action_data.get("tool_input", ""))
                        
                        logger.info(f"Captured action step {step_counter}: tool={tool_name}, input_type={type(tool_input).__name__}, input_preview={str(tool_input)[:100]}")
                        
                        tool_input_str = json.dumps(tool_input, ensure_ascii=False, indent=2) if isinstance(tool_input, dict) else str(tool_input)
                        content = f"Calling tool: {tool_name}\nInput: {tool_input_str}"
                        
                        await websocket_manager.stream_react_step(
                            execution_id=execution_id,
                            step_type="action",
                            step_index=step_counter,
                            content=content,
                            node_id="sql_agent_node",
                            tool_name=tool_name,
                            tool_input=tool_input
                        )
                        
                        intermediate_steps.append({
                            "step": "action",
                            "tool": tool_name,
                            "input": tool_input
                        })
                    elif event_name == "on_tool_end":
                        step_counter += 1
                        # Fix: event structure for on_tool_end
                        tool_data = event.get("data", {})
                        tool_name_from_event = event_name_str  # The tool name is in the event name
                        logger.info(f"on_tool_end event - tool: {tool_name_from_event}, data keys: {list(tool_data.keys())}")
                        
                        # Try different possible structures
                        observation = ""
                        if "output" in tool_data:
                            observation = tool_data["output"]
                        elif "result" in tool_data:
                            observation = str(tool_data["result"])
                        else:
                            observation = str(tool_data) if tool_data else ""
                        
                        # CRITICAL: Truncate large observations to prevent context length exceeded errors
                        # OpenAI API has a 10MB limit (10485760 characters) for message content
                        # We'll limit observation to 1MB (1048576 characters) to leave room for other content
                        MAX_OBSERVATION_LENGTH = 1048576  # 1MB limit
                        observation_original_length = len(observation)
                        if observation_original_length > MAX_OBSERVATION_LENGTH:
                            logger.warning(f"⚠️  Observation too large ({observation_original_length} chars), truncating to {MAX_OBSERVATION_LENGTH} chars to prevent context length exceeded error")
                            # For SQL query results, try to extract summary information
                            if tool_name_from_event == "sql_db_query":
                                # Try to parse and summarize the result
                                try:
                                    parsed = _parse_agent_query_result(observation)
                                    if parsed and parsed.get("rows"):
                                        rows = parsed.get("rows", [])
                                        # Keep first 100 rows and summary
                                        truncated_rows = rows[:100]
                                        summary = f"Query returned {len(rows)} rows. Showing first 100 rows:\n"
                                        observation = summary + str(truncated_rows)
                                        if len(observation) > MAX_OBSERVATION_LENGTH:
                                            observation = observation[:MAX_OBSERVATION_LENGTH] + f"\n... (truncated, original length: {observation_original_length} chars)"
                                except:
                                    # If parsing fails, just truncate the string
                                    observation = observation[:MAX_OBSERVATION_LENGTH] + f"\n... (truncated, original length: {observation_original_length} chars)"
                            else:
                                # For other tools, just truncate
                                observation = observation[:MAX_OBSERVATION_LENGTH] + f"\n... (truncated, original length: {observation_original_length} chars)"
                        
                        logger.info(f"Tool observation length: {len(observation)}, preview: {str(observation)[:100]}")
                        display_output = observation[:100] + "..." if len(observation) > 100 else observation
                        
                        await websocket_manager.stream_react_step(
                            execution_id=execution_id,
                            step_type="observation",
                            step_index=step_counter,
                            content=f"Tool result: {display_output}",
                            node_id="sql_agent_node"
                        )
                        
                        # If no matching action step found, create one from tool_end event
                        if not intermediate_steps or intermediate_steps[-1].get("tool") != tool_name_from_event:
                            logger.warning(f"No matching action step found for tool {tool_name_from_event}, creating one from tool_end event")
                            # Try to extract input from tool_data
                            tool_input = tool_data.get("input", "")
                            # If tool_input is a dict and contains "query", extract it
                            if isinstance(tool_input, dict):
                                if "query" in tool_input:
                                    tool_input = tool_input["query"]
                                elif "tool_input" in tool_input:
                                    tool_input = tool_input["tool_input"]
                                elif len(tool_input) == 1:
                                    # If dict has only one key-value pair, use the value
                                    tool_input = list(tool_input.values())[0]
                            
                            # Format input for sql_db_query
                            formatted_input = {"query": tool_input} if tool_name_from_event == "sql_db_query" and isinstance(tool_input, str) else tool_input
                            
                            intermediate_steps.append({
                                "step": "action",
                                "tool": tool_name_from_event,
                                "input": formatted_input,
                                "observation": observation
                            })
                            logger.info(f"Created action step from tool_end: tool={tool_name_from_event}, input_type={type(tool_input).__name__}, input_preview={str(tool_input)[:100]}")
                            
                            # Try to parse structured_data from observation immediately
                            if tool_name_from_event == "sql_db_query" and observation:
                                parsed = _parse_agent_query_result(observation)
                                if parsed:
                                    structured_data = parsed
                                    logger.info(f"Parsed structured_data from tool_end observation: {len(parsed.get('rows', []))} rows")
                        else:
                            # Update the last step with observation
                            intermediate_steps[-1]["observation"] = observation
                            logger.info(f"Updated existing action step with observation: tool={intermediate_steps[-1].get('tool')}")
                            
                            # Try to parse structured_data from observation if it's a SQL query
                            if intermediate_steps[-1].get("tool") == "sql_db_query" and observation:
                                parsed = _parse_agent_query_result(observation)
                                if parsed:
                                    structured_data = parsed
                                    logger.info(f"Parsed structured_data from updated observation: {len(parsed.get('rows', []))} rows")
                    elif event_name == "on_chain_end":
                        # Check if this is the AgentExecutor chain end
                        # SQL Agent uses "SQL Agent Executor" as the chain name
                        chain_name = event.get("name", "")
                        if chain_name == "AgentExecutor" or "AgentExecutor" in str(chain_name) or "SQL Agent Executor" in str(chain_name):
                            chain_data = event.get("data", {})
                            output = chain_data.get("output", {})
                            if isinstance(output, dict):
                                final_answer = output.get("output", str(output))
                                logger.info(f"Extracted final_answer from on_chain_end: {final_answer[:100] if final_answer else 'None'}")
                            else:
                                final_answer = str(output) if output else ""
                                logger.info(f"Extracted final_answer from on_chain_end (non-dict): {final_answer[:200] if final_answer else 'None'}")
                        
                        # Also check for "Final Answer" in the output text for SQL Agent
                        if not final_answer and chain_name and ("SQL Agent" in str(chain_name) or "Agent" in str(chain_name)):
                            chain_data = event.get("data", {})
                            output = chain_data.get("output", "")
                            if output and isinstance(output, str) and ("Final Answer" in output or "final answer" in output.lower()):
                                # Try to extract the final answer text
                                import re
                                match = re.search(r"Final Answer:\s*(.+?)(?:\n|$)", output, re.IGNORECASE | re.DOTALL)
                                if match:
                                    final_answer = match.group(1).strip()
                                    logger.info(f"Extracted final_answer from output text: {final_answer[:100]}")
                
                logger.info(f"astream_events completed - total events: {event_count}, intermediate_steps: {len(intermediate_steps)}")
                
                # Extract SQL queries from intermediate steps
                logger.info(f"Processing {len(intermediate_steps)} intermediate steps to extract SQL queries...")
                for idx, step in enumerate(intermediate_steps):
                    tool_name = step.get("tool", "")
                    tool_input = step.get("input", {})
                    logger.info(f"Step {idx}: tool={tool_name}, input_type={type(tool_input).__name__}")
                    
                    # Handle different input formats
                    if isinstance(tool_input, str):
                        # If input is a string, try to extract query
                        if "sql_db_query" in tool_name or "query" in tool_name.lower() or "sql" in tool_name.lower():
                            executed_sqls.append(tool_input)
                            logger.info(f"Added SQL query from string input: {tool_input[:100]}")
                    elif isinstance(tool_input, dict):
                        query = tool_input.get("query", tool_input.get("tool_input", ""))
                        if query and ("sql_db_query" in tool_name or "query" in tool_name.lower() or "sql" in tool_name.lower()):
                            executed_sqls.append(query)
                            logger.info(f"Added SQL query from dict input: {query[:100]}")
                        # Parse result if available
                        if step.get("observation"):
                            parsed = _parse_agent_query_result(step["observation"])
                            if parsed:
                                structured_data = parsed
                                logger.info(f"Parsed structured_data from observation: {len(parsed.get('rows', []))} rows")
                
                # If no intermediate steps captured, try to use ainvoke and parse the result
                if len(intermediate_steps) == 0:
                    logger.warning("No intermediate steps captured from astream_events, falling back to ainvoke...")
                    result = await agent.ainvoke({"input": agent_input})
                    logger.info(f"ainvoke result type: {type(result).__name__}, keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
                    
                    if isinstance(result, dict):
                        final_answer = result.get("output", str(result))
                        # Try to extract intermediate steps from result
                        if "intermediate_steps" in result:
                            intermediate_steps = result["intermediate_steps"]
                            logger.info(f"Found intermediate_steps in result: {len(intermediate_steps)} steps")
                    else:
                        final_answer = str(result)
                
                # If no final answer, try invoke (but only if we didn't capture intermediate steps)
                # If we have intermediate steps, we can construct the answer from them
                if not final_answer:
                    if len(intermediate_steps) > 0:
                        # We have steps but no final answer - construct a summary from the steps
                        logger.info("No final answer from astream_events, but we have intermediate steps. Constructing answer from steps...")
                        # Try to get the last observation which might contain the answer
                        last_step = intermediate_steps[-1]
                        if last_step.get("observation"):
                            # If the last step is a query, use its result as the answer
                            if last_step.get("tool") == "sql_db_query":
                                final_answer = f"Query executed successfully. Results: {last_step.get('observation', '')[:100]}"
                            else:
                                final_answer = f"Agent completed {len(intermediate_steps)} steps. Last step: {last_step.get('tool', 'unknown')}"
                        else:
                            final_answer = f"Agent completed {len(intermediate_steps)} steps successfully."
                        logger.info(f"Constructed final_answer from steps: {final_answer[:100]}")
                    else:
                        # No steps captured, need to fallback to ainvoke
                        logger.warning("No final answer and no intermediate steps from astream_events, trying ainvoke...")
                        result = await agent.ainvoke({"input": agent_input})
                        if isinstance(result, dict):
                            final_answer = result.get("output", str(result))
                        else:
                            final_answer = str(result)
                
                logger.info(f"ReAct mode completed - {len(intermediate_steps)} steps, {len(executed_sqls)} SQL queries")
                logger.info(f"Intermediate steps details: {[step.get('tool', 'N/A') for step in intermediate_steps]}")
                logger.info(f"Executed SQLs: {executed_sqls}")
                logger.info(f"Structured data available: {structured_data is not None}, type: {type(structured_data).__name__}")
                
                # If no structured_data extracted from steps, try to parse from final_answer
                if not structured_data and executed_sqls:
                    # Try to extract data from the last SQL query result
                    for step in reversed(intermediate_steps):
                        if step.get("observation"):
                            parsed = _parse_agent_query_result(step["observation"])
                            if parsed:
                                structured_data = parsed
                                logger.info(f"Parsed structured_data from reversed step observation: {len(parsed.get('rows', []))} rows")
                                break
                    
                    # If still no structured_data, try to parse from final_answer text
                    if not structured_data and final_answer:
                        logger.info("Attempting to parse structured_data from final_answer text...")
                        # Try to extract SQL result from final_answer
                        import re
                        # Look for patterns like [('Office Supplies', 71), ('Audio', 69), ...]
                        pattern = r"\[\([^)]+\)(?:,\s*\([^)]+\))*\]"
                        matches = re.findall(pattern, final_answer)
                        if matches:
                            logger.info(f"Found potential data pattern in final_answer: {matches[0][:100]}")
                            # Try to parse it
                            try:
                                import ast
                                parsed_data = ast.literal_eval(matches[0])
                                if isinstance(parsed_data, list) and len(parsed_data) > 0:
                                    # Convert to structured format
                                    if isinstance(parsed_data[0], tuple):
                                        # Convert tuples to dicts
                                        keys = ["category", "sales"] if len(parsed_data[0]) == 2 else [f"col{i}" for i in range(len(parsed_data[0]))]
                                        rows = [dict(zip(keys, row)) for row in parsed_data]
                                        structured_data = {"rows": rows, "columns": keys}
                                        logger.info(f"Successfully parsed structured_data from final_answer: {len(rows)} rows")
                            except Exception as e:
                                logger.warning(f"Failed to parse data from final_answer: {e}")
                
                # Determine chart suitability
                chart_suitable = False
                if user_input:
                    chart_keywords = ["chart", "pie", "bar", "line", "graph", "visualization", "proportion", "distribution", "trend"]
                    has_chart_intent = any(keyword.lower() in user_input.lower() for keyword in chart_keywords)
                    # Check structured_data in different formats
                    data_rows = None
                    if structured_data:
                        if isinstance(structured_data, dict):
                            data_rows = structured_data.get("rows") or structured_data.get("data", [])
                        elif isinstance(structured_data, list):
                            data_rows = structured_data
                    if has_chart_intent and data_rows and len(data_rows) >= 2:
                        chart_suitable = True
                        logger.info(f"Chart suitable: intent={has_chart_intent}, rows={len(data_rows)}")
                    else:
                        logger.info(f"Chart not suitable: intent={has_chart_intent}, rows={len(data_rows) if data_rows else 0}")
                
                return {
                    **state,
                    "sql_agent_answer": final_answer,
                    "executed_sqls": executed_sqls,
                    "structured_data": structured_data,
                    "chart_suitable": chart_suitable,
                    "agent_intermediate_steps": intermediate_steps,
                    "sql_execution_success": True,
                    "react_mode_used": True,
                    "node_outputs": {
                        **state.get("node_outputs", {}),
                        "sql_agent": {
                            "status": "completed",
                            "queries_count": len(executed_sqls),
                            "steps_count": len(intermediate_steps),
                            "chart_suitable": chart_suitable,
                            "react_mode": True,
                            "timestamp": time.time()
                        }
                    }
                }
                
            except Exception as react_error:
                logger.error(f"ReAct mode execution failed: {react_error}", exc_info=True)
                react_fallback_reason = f"ReAct execution error: {str(react_error)}"
                logger.info(f"Falling back to manual mode due to: {react_fallback_reason}")
                # Continue to fallback mode
        
        # 5. Fallback to manual ReAct Loop Implementation
        logger.info("Using manual ReAct SQL exploration (fallback mode)...")
        if react_fallback_reason:
            await websocket_manager.stream_react_step(
                execution_id=execution_id,
                step_type="thought",
                step_index=0,
                content=f"Note: ReAct mode not available ({react_fallback_reason}), using manual mode",
                node_id="sql_agent_node"
            )
        
        # Create SQL Toolkit
        from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
        
        toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        tools = toolkit.get_tools()
        
        # Step 1: List all tables
        list_tables_tool = None
        for tool in tools:
            if tool.name == 'sql_db_list_tables':
                list_tables_tool = tool
                break
        
        tables_result = ""
        marts_tables_detected = []
        all_tables_by_schema = {}  # Store tables organized by schema
        
        if list_tables_tool:
            try:
                # Step 1: Get initial table list (from current/default schema)
                tables_result = list_tables_tool.invoke({})
                logger.info(f"Found tables from default schema: {tables_result}")
                
                # Step 2: For Databricks, discover tables from specified schema only (default: public)
                if is_databricks:
                    # Ensure re is available
                    import re as re_module
                    import ast
                    
                    # Get schema from environment variable, default to 'public'
                    target_schema = os.getenv("DATABRICKS_SCHEMA", "public")
                    
                    # Get sql_db_query tool to query tables
                    sql_query_tool = None
                    for tool in tools:
                        if tool.name == 'sql_db_query':
                            sql_query_tool = tool
                            break
                    
                    if sql_query_tool:
                        try:
                            catalog = os.getenv("DATABRICKS_DATABASE") or os.getenv("DATABRICKS_CATALOG", "workspace")
                            
                            # Only query tables from the specified schema (default: public)
                            logger.info(f"Discovering tables from schema: {target_schema} (default: public, override via DATABRICKS_SCHEMA env var)")
                            tables_query = f"SHOW TABLES IN {catalog}.{target_schema}"
                            
                            try:
                                schema_tables_result = sql_query_tool.invoke({"query": tables_query})
                                logger.info(f"Querying tables in schema {target_schema}: {tables_query}")
                                
                                all_tables = []
                                if schema_tables_result:
                                    schema_tables = []
                                    schema_tables_raw = str(schema_tables_result)
                                    
                                    try:
                                        # Try to parse as Python list of tuples
                                        parsed_tables = ast.literal_eval(schema_tables_raw)
                                        if isinstance(parsed_tables, list):
                                            for item in parsed_tables:
                                                if isinstance(item, (tuple, list)) and len(item) >= 2:
                                                    # Format: (database, table, isTemporary) or (namespace, table, ...)
                                                    table_name = item[1] if len(item) > 1 else item[0]
                                                    if table_name and table_name not in ['databaseName', 'tableName', 'namespace', 'isTemporary']:
                                                        full_table_name = f"{target_schema}.{table_name}"
                                                        schema_tables.append(full_table_name)
                                                        all_tables.append(full_table_name)
                                    except:
                                        # Fallback: regex extraction
                                        # Look for patterns like schema.table_name
                                        pattern = rf"{re_module.escape(target_schema)}\.(\w+)"
                                        matches = re_module.findall(pattern, schema_tables_raw)
                                        for match in matches:
                                            if match not in ['tableName', 'table', 'database']:
                                                full_table_name = f"{target_schema}.{match}"
                                                schema_tables.append(full_table_name)
                                                all_tables.append(full_table_name)
                                    
                                    if schema_tables:
                                        all_tables_by_schema[target_schema] = schema_tables
                                        logger.info(f"  ✅ Schema '{target_schema}': {len(schema_tables)} tables")
                                    else:
                                        logger.warning(f"  ⚠️  Schema '{target_schema}': No tables found or could not parse")
                                
                                # Step 2.3: Merge discovered tables into tables_result
                                if all_tables:
                                    # Combine with initial tables_result
                                    initial_tables = [t.strip() for t in re_module.split(r"[,\s]+", str(tables_result)) if t.strip()]
                                    
                                    # Add schema prefix to initial tables if they don't have one
                                    initial_tables_with_schema = []
                                    for table in initial_tables:
                                        if '.' not in table:
                                            # Assume they're from target schema (default: public)
                                            initial_tables_with_schema.append(f"{target_schema}.{table}")
                                        else:
                                            initial_tables_with_schema.append(table)
                                    
                                    # Merge all tables
                                    all_tables_combined = initial_tables_with_schema + all_tables
                                    
                                    # Deduplicate tables
                                    all_tables_merged = list(set(all_tables_combined))
                                    
                                    tables_result = ', '.join(all_tables_merged)
                                    
                                    logger.info(f"✅ Total tables discovered: {len(all_tables_merged)} tables from schema '{target_schema}'")
                                    
                                    # Identify marts layer tables (now in target schema with mart_ prefix)
                                    marts_tables_detected = [
                                        t for t in all_tables_merged 
                                        if 'mart_' in t.lower() or 
                                        (t.startswith(f'{target_schema}.') and any(keyword in t.lower() for keyword in ['summary', 'daily', 'flow', 'usage', 'topup', 'active', 'aggregat']))
                                    ]
                                    
                                    if marts_tables_detected:
                                        logger.info(f"✅ Detected {len(marts_tables_detected)} marts layer tables: {marts_tables_detected}")
                                    else:
                                        logger.warning("⚠️  No marts layer tables detected in discovered schema")
                                else:
                                    logger.warning(f"⚠️  No tables discovered from schema '{target_schema}', using default schema tables only")
                                    
                            except Exception as schema_error:
                                logger.warning(f"Could not query tables in schema '{target_schema}': {schema_error}")
                                logger.warning("Falling back to default schema tables only")
                                
                        except Exception as e:
                            logger.warning(f"Error discovering schemas and tables: {e}")
                            logger.warning("Falling back to default schema tables only")
                    else:
                        logger.warning("sql_db_query tool not available, cannot discover schemas")
                else:
                    # For non-Databricks databases, use default behavior
                    import re as re_module
                    tables_list = [t.strip() for t in re_module.split(r"[,\s]+", str(tables_result)) if t.strip()]
                    logger.info(f"Non-Databricks database: {len(tables_list)} tables found")
                    
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
            # For Databricks, tables may be in different schemas, so we need to handle schema.table format
            sales_tables = ['sales', 'dws_sales_cube', 'dwd_sales_detail']
            for table in sales_tables:
                # Check if table exists in tables_result (may be with or without schema prefix)
                table_found = table in tables_result or any(table in t for t in tables_result.split(',') if t.strip())
                if table_found:
                    try:
                        # Try to get schema info with the table name as-is
                        # If it's Databricks and table doesn't have schema prefix, try common schemas
                        table_to_query = table
                        if is_databricks and '.' not in table:
                            # Try public schema first (all tables are now in public schema)
                            # Old schemas (dimensions, facts, marts, staging) are deprecated
                            schemas_to_try = ['public']  # Only try public schema
                            schema_found = False
                            for schema in schemas_to_try:
                                try:
                                    full_table_name = f"{schema}.{table}"
                                    table_schema = db.get_table_info([full_table_name])
                                    schema_info += f"\n{full_table_name} table structure:\n{table_schema}\n"
                                    schema_found = True
                                    break
                                except:
                                    continue
                            if not schema_found:
                                # Fallback: try without schema prefix (assumes public)
                                try:
                                    table_schema = db.get_table_info([table])
                                    schema_info += f"\npublic.{table} table structure:\n{table_schema}\n"
                                except:
                                    schema_info += f"\n{table} table structure: (not found in public schema)\n"
                        else:
                            table_schema = db.get_table_info([table_to_query])
                            schema_info += f"\n{table_to_query} table structure:\n{table_schema}\n"
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
        
        {"Example RAG metadata for mart tables (if available in knowledge base):" if is_databricks else ""}
        {"Table: public.mart_daily_active_users" if is_databricks else ""}
        {"Description: Daily active users metrics and trends. Pre-aggregated table optimized for analytical queries." if is_databricks else ""}
        {"Columns: date (date, unique), active_users (integer), total_transactions (integer), total_amount (numeric), avg_transactions_per_user (numeric), avg_amount_per_transaction (numeric), entry_transactions (integer), exit_transactions (integer), is_weekend (boolean)" if is_databricks else ""}
        {"Use case: Daily/monthly/yearly user activity trends, transaction volume analysis, weekend vs weekday comparisons" if is_databricks else ""}
        {"" if is_databricks else ""}
        {"Table: public.mart_daily_topup_summary" if is_databricks else ""}
        {"Description: Daily top-up summary metrics. Pre-aggregated table for top-up analysis." if is_databricks else ""}
        {"Columns: date (date, unique), total_topups (integer), unique_users (integer), total_amount (numeric), avg_amount_per_topup (numeric), avg_amount_per_user (numeric), cash_topups (integer), card_topups (integer), mobile_topups (integer), online_topups (integer), is_weekend (boolean)" if is_databricks else ""}
        {"Use case: Top-up trends, payment method analysis, top-up amount statistics" if is_databricks else ""}
        {"" if is_databricks else ""}
        {"Table: public.mart_station_flow_daily" if is_databricks else ""}
        {"Description: Daily station flow metrics. Pre-aggregated table for station-level analysis." if is_databricks else ""}
        {"Columns: date (date), station_id (integer), station_name (string), station_type (string), total_transactions (integer), unique_users (integer), entry_count (integer), exit_count (integer), total_amount (numeric), is_weekend (boolean)" if is_databricks else ""}
        {"Use case: Station rankings, station flow analysis, entry/exit patterns, station performance comparison" if is_databricks else ""}
        {"" if is_databricks else ""}
        {"Table: public.mart_user_card_type_summary" if is_databricks else ""}
        {"Description: User summary by card type. Pre-aggregated table for card type distribution analysis." if is_databricks else ""}
        {"Columns: card_type (string, unique), total_users (integer), verified_users (integer), total_transactions (integer), total_transaction_amount (numeric), avg_transactions_per_user (numeric), total_topups (integer), total_topup_amount (numeric), avg_topup_per_user (numeric)" if is_databricks else ""}
        {"Use case: Card type distribution, user segmentation, card type performance comparison" if is_databricks else ""}
        {"" if is_databricks else ""}
        {"Table: public.mart_route_usage_summary" if is_databricks else ""}
        {"Description: Route usage summary metrics. Pre-aggregated table for route-level analysis." if is_databricks else ""}
        {"Columns: route_id (integer, unique), route_name (string), route_type (string), total_transactions (integer), unique_users (integer), total_amount (numeric), avg_transactions_per_day (numeric), first_transaction_date (date), last_transaction_date (date)" if is_databricks else ""}
        {"Use case: Route rankings, route usage analysis, route performance comparison" if is_databricks else ""}
        {"" if is_databricks else ""}
        
        Available tables in database: {tables_result}
        
        Table structure information: {schema_info}
        
        {"This is a Databricks SQL database (Unity Catalog)." if is_databricks else "This is a SQLite database."} Please generate a SQL query based on the user question and available tables.
        
        {"📊 DATA WAREHOUSE DESIGN PRINCIPLES (Kimball/Medallion Architecture):" if is_databricks else ""}
        {"This database follows a layered data warehouse architecture. All tables are in public schema, identified by prefixes:" if is_databricks else ""}
        {"1. src_* (Source Layer - Raw Data):" if is_databricks else ""}
        {"   - Purpose: Raw data directly from source systems (Airbyte ETL)" if is_databricks else ""}
        {"   - Use when: Need to access original, unprocessed data; Data quality checks; ETL debugging" if is_databricks else ""}
        {"   - Examples: src_users, src_transactions, src_stations, src_routes, src_topups" if is_databricks else ""}
        {"   - Query pattern: SELECT * FROM public.src_users WHERE ... (rarely used in analytics)" if is_databricks else ""}
        {"" if is_databricks else ""}
        {"2. stg_* (Staging Layer - Cleaned Data):" if is_databricks else ""}
        {"   - Purpose: Cleaned, validated, and standardized data ready for transformation" if is_databricks else ""}
        {"   - Use when: Need cleaned data for joins with dimensions; Building custom aggregations not in mart_*" if is_databricks else ""}
        {"   - Examples: stg_users, stg_transactions, stg_stations, stg_routes, stg_topups" if is_databricks else ""}
        {"   - Query pattern: SELECT * FROM public.stg_transactions WHERE ... (use sparingly, prefer mart_* for analytics)" if is_databricks else ""}
        {"" if is_databricks else ""}
        {"3. dim_* (Dimension Layer - Master Data):" if is_databricks else ""}
        {"   - Purpose: Master reference data with surrogate keys for dimensional modeling" if is_databricks else ""}
        {"   - Use when: Need dimension attributes (user info, station details, route info, time attributes); Joining with fact tables" if is_databricks else ""}
        {"   - Examples: dim_user, dim_station, dim_route, dim_time" if is_databricks else ""}
        {"   - Query pattern: SELECT * FROM public.dim_user WHERE ... or JOIN with fact_* tables" if is_databricks else ""}
        {"   - Key columns: *_key (surrogate key), *_id (business key), descriptive attributes" if is_databricks else ""}
        {"" if is_databricks else ""}
        {"4. fact_* (Fact Layer - Transactional Data):" if is_databricks else ""}
        {"   - Purpose: Transactional fact tables with foreign keys to dimensions and measures" if is_databricks else ""}
        {"   - Use when: Need detailed transaction-level data; Custom aggregations not available in mart_*; Specific granularity requirements" if is_databricks else ""}
        {"   - Examples: fact_transactions, fact_topups" if is_databricks else ""}
        {"   - Query pattern: SELECT * FROM public.fact_transactions WHERE ... (use only when mart_* doesn't have required metrics)" if is_databricks else ""}
        {"   - Key columns: *_key (surrogate key), *_id (business key), dimension keys, measures (amount, count, etc.)" if is_databricks else ""}
        {"" if is_databricks else ""}
        {"5. mart_* (Marts Layer - Pre-aggregated Analytics) - ⭐ STRONGLY PREFERRED:" if is_databricks else ""}
        {"   - Purpose: Pre-computed, optimized analytical tables for reporting and business intelligence" if is_databricks else ""}
        {"   - Use when: ANY statistical query, trend analysis, metrics, summaries, comparisons, aggregations" if is_databricks else ""}
        {"   - Design: Follows Kimball/Medallion Architecture - optimized for analytical queries" if is_databricks else ""}
        {"   - Examples: mart_daily_active_users, mart_daily_topup_summary, mart_station_flow_daily, mart_user_card_type_summary, mart_route_usage_summary" if is_databricks else ""}
        {"   - Query pattern: SELECT * FROM public.mart_daily_active_users WHERE ... (MANDATORY for analytics)" if is_databricks else ""}
        {"   - Benefits: Pre-aggregated, faster queries, optimized for reporting, follows data warehouse best practices" if is_databricks else ""}
        {"" if is_databricks else ""}
        {"🎯 QUERY TYPE TO TABLE PREFIX MAPPING:" if is_databricks else ""}
        {"- Statistical queries (counts, sums, averages, trends): → mart_* tables (MANDATORY)" if is_databricks else ""}
        {"- Time series analysis (daily, monthly, yearly trends): → mart_* tables (MANDATORY)" if is_databricks else ""}
        {"- Category/group comparisons: → mart_* tables (MANDATORY)" if is_databricks else ""}
        {"- Station/route rankings: → mart_station_flow_daily or mart_route_usage_summary (MANDATORY)" if is_databricks else ""}
        {"- User distribution by card type: → mart_user_card_type_summary (MANDATORY)" if is_databricks else ""}
        {"- Detailed transaction records: → fact_* tables (only if mart_* doesn't provide required detail)" if is_databricks else ""}
        {"- Dimension attributes (user info, station details): → dim_* tables" if is_databricks else ""}
        {"- Raw source data access: → src_* tables (rarely needed in analytics)" if is_databricks else ""}
        {"- Cleaned data for custom joins: → stg_* tables (use sparingly, prefer mart_*)" if is_databricks else ""}
        {"" if is_databricks else ""}
        {"⚠️  CRITICAL: All tables are now in public schema. Use table name prefixes to identify layers:" if is_databricks else ""}
        {"   - src_* : Source tables (raw data from Airbyte)" if is_databricks else ""}
        {"   - stg_* : Staging tables (cleaned and validated data)" if is_databricks else ""}
        {"   - dim_* : Dimension tables (dim_user, dim_station, dim_route, dim_time)" if is_databricks else ""}
        {"   - fact_* : Fact tables (fact_transactions, fact_topups)" if is_databricks else ""}
        {"   - mart_* : Marts tables (pre-aggregated metrics, STRONGLY PREFERRED for all statistics and analytics queries)" if is_databricks else ""}
        {"⚠️  STRONGLY RECOMMENDED: Use mart_* tables for ALL statistical, metric, trend, and aggregation queries:" if is_databricks and marts_tables_detected else ""}
        {"   Available mart_* tables: " + ", ".join(marts_tables_detected) + "." if is_databricks and marts_tables_detected else ""}
        {"   - mart_daily_active_users: Daily user activity metrics" if is_databricks and marts_tables_detected else ""}
        {"     Columns: date, active_users, total_transactions, total_amount, avg_transactions_per_user, avg_amount_per_transaction, entry_transactions, exit_transactions, is_weekend" if is_databricks and marts_tables_detected else ""}
        {"     Sample query: SELECT date, active_users, total_transactions FROM public.mart_daily_active_users WHERE date >= '2025-11-01' ORDER BY date" if is_databricks and marts_tables_detected else ""}
        {"   - mart_daily_topup_summary: Daily top-up metrics" if is_databricks and marts_tables_detected else ""}
        {"     Columns: date, total_topups, unique_users, total_amount, avg_amount_per_topup, avg_amount_per_user, cash_topups, card_topups, mobile_topups, online_topups, is_weekend" if is_databricks and marts_tables_detected else ""}
        {"     Sample query: SELECT DATE_FORMAT(date, 'yyyy-MM') as Month, SUM(total_amount) as Total_Topup FROM public.mart_daily_topup_summary WHERE EXTRACT(YEAR FROM date) = 2025 GROUP BY Month" if is_databricks and marts_tables_detected else ""}
        {"   - mart_station_flow_daily: Daily station flow metrics" if is_databricks and marts_tables_detected else ""}
        {"     Columns: date, station_id, station_name, station_type, total_transactions, unique_users, entry_count, exit_count, total_amount, is_weekend" if is_databricks and marts_tables_detected else ""}
        {"     Sample query: SELECT station_name, SUM(total_transactions) as Total FROM public.mart_station_flow_daily WHERE date >= '2025-11-01' GROUP BY station_name ORDER BY Total DESC LIMIT 10" if is_databricks and marts_tables_detected else ""}
        {"   - mart_user_card_type_summary: User metrics by card type" if is_databricks and marts_tables_detected else ""}
        {"     Columns: card_type, total_users, verified_users, total_transactions, total_transaction_amount, avg_transactions_per_user, total_topups, total_topup_amount, avg_topup_per_user" if is_databricks and marts_tables_detected else ""}
        {"     Sample query: SELECT card_type, total_users, total_transaction_amount FROM public.mart_user_card_type_summary ORDER BY total_users DESC" if is_databricks and marts_tables_detected else ""}
        {"   - mart_route_usage_summary: Route usage metrics" if is_databricks and marts_tables_detected else ""}
        {"     Columns: route_id, route_name, route_type, total_transactions, unique_users, total_amount, avg_transactions_per_day, first_transaction_date, last_transaction_date" if is_databricks and marts_tables_detected else ""}
        {"     Sample query: SELECT route_name, total_transactions, unique_users FROM public.mart_route_usage_summary ORDER BY total_transactions DESC LIMIT 10" if is_databricks and marts_tables_detected else ""}
        {"   DO NOT aggregate from fact_*/dim_* tables when equivalent mart_* tables exist!" if is_databricks and marts_tables_detected else ""}
        
        CRITICAL RULES - MUST FOLLOW:
        1. ONLY use column names that exist in the table structure information above
        {"2. DATA WAREHOUSE LAYER SELECTION - Choose the right table prefix based on query type:" if is_databricks else "2. NEVER use 'customer_type' - it does NOT exist in dws_sales_cube table"}
        {"   Query Type → Table Prefix Mapping:" if is_databricks else ""}
        {"   - Statistical queries (counts, sums, averages, trends) → mart_* (MANDATORY)" if is_databricks else ""}
        {"   - Time series analysis (daily/monthly/yearly trends) → mart_* (MANDATORY)" if is_databricks else ""}
        {"   - Category/group comparisons → mart_* (MANDATORY)" if is_databricks else ""}
        {"   - Station/route rankings → mart_station_flow_daily, mart_route_usage_summary (MANDATORY)" if is_databricks else ""}
        {"   - User distribution by card type → mart_user_card_type_summary (MANDATORY)" if is_databricks else ""}
        {"   - Detailed transaction records → fact_* (only if mart_* insufficient)" if is_databricks else ""}
        {"   - Dimension attributes (user info, station details) → dim_*" if is_databricks else ""}
        {"   - Raw source data access → src_* (rarely needed)" if is_databricks else ""}
        {"   - Cleaned data for custom logic → stg_* (use sparingly)" if is_databricks else ""}
        {"" if is_databricks else ""}
        {"   Table Prefix Meanings:" if is_databricks else ""}
        {"   - src_* : Source layer - Raw data from Airbyte (rarely used in analytics)" if is_databricks else ""}
        {"   - stg_* : Staging layer - Cleaned and validated data (use sparingly, prefer mart_*)" if is_databricks else ""}
        {"   - dim_* : Dimension layer - Master reference data (for descriptive attributes)" if is_databricks else ""}
        {"   - fact_* : Fact layer - Transactional data (only when mart_* insufficient)" if is_databricks else ""}
        {"   - mart_* : Marts layer - Pre-aggregated analytics (MANDATORY for statistics)" if is_databricks else ""}
        {"   - Always use public.table_name format (e.g., public.mart_daily_active_users, public.fact_transactions)" if is_databricks else ""}
        {"3. STATISTICAL/METRIC/TREND QUERIES - ALWAYS use mart_* tables (MANDATORY for data warehouse design):" if is_databricks else ""}
        {"   - For ANY aggregated statistics, metrics, summaries, trends, or pre-calculated data, MANDATORY to use mart_* tables" if is_databricks else ""}
        {"   - Design principle: mart_* tables follow Kimball/Medallion Architecture and contain pre-aggregated metrics optimized for analytical queries" if is_databricks else ""}
        {"   - mart_* tables are specifically designed for reporting and analytics, containing daily/weekly/monthly summaries, aggregations, and business metrics" if is_databricks else ""}
        {"   - When querying for statistics (counts, sums, averages, trends, comparisons), ALWAYS look for mart_* tables first" if is_databricks else ""}
        {"   - NEVER aggregate from fact_*/dim_* tables when equivalent mart_* tables exist - mart_* tables are pre-computed, more efficient, and follow best practices" if is_databricks else ""}
        {"   - Only use fact_*/dim_* tables when mart_* tables don't provide the required granularity or specific metrics" if is_databricks else ""}
        {"   - For monthly/yearly trends: Use mart_daily_active_users or mart_daily_topup_summary aggregated by month/year" if is_databricks else ""}
        {"   - For daily trends: Use mart_daily_active_users or mart_daily_topup_summary directly" if is_databricks else ""}
        {"   - For station/route comparisons: Use mart_station_flow_daily or mart_route_usage_summary" if is_databricks else ""}
        {"   - For category distributions: Use mart_user_card_type_summary" if is_databricks else ""}
        {"4. METADATA INFORMATION - Use RAG knowledge base first:" if is_databricks else "3. Use 'category' instead of 'customer_type' for product categorization"}
        {"   - The background knowledge above contains metadata about table structures, column definitions, and business rules" if is_databricks else "4. Verify every column name against the table structure before using it"}
        {"   - Use this RAG metadata to understand table relationships and data semantics" if is_databricks else "5. dws_sales_cube CAN be joined with dim_customer using customer_id field"}
        {"   - If RAG metadata is insufficient, you can explore the database schema using available tools" if is_databricks else "6. Use appropriate JOIN conditions based on available fields"}
        {"6. All tables are in public schema, so joins use public.table_name format" if is_databricks else "3. Use 'category' instead of 'customer_type' for product categorization"}
        {"7. Example table references: public.src_users, public.stg_stations, public.dim_user, public.fact_transactions, public.mart_daily_active_users" if is_databricks else "4. Verify every column name against the table structure before using it"}
        {"8. Example joins: SELECT * FROM public.stg_stations s JOIN public.dim_station d ON s.station_id = d.station_id" if is_databricks else "5. dws_sales_cube CAN be joined with dim_customer using customer_id field"}
        {"9. Verify every column name against the table structure before using it" if is_databricks else "6. Use appropriate JOIN conditions based on available fields"}
        {"10. Use appropriate JOIN conditions based on available fields" if is_databricks else "7. Check table relationships before creating JOIN conditions"}
        {"11. Check table relationships before creating JOIN conditions" if is_databricks else "8. IMPORTANT: For sales amount queries, use 'total_amount' in dws_sales_cube"}
        {"12. NEVER use 'customer_type' - it does NOT exist in dws_sales_cube table (if applicable)" if is_databricks else "9. IMPORTANT: For quantity queries, use 'total_quantity_sold' NOT 'quantity_sold' in dws_sales_cube"}
        {"13. IMPORTANT: For date filtering, use appropriate date functions" if is_databricks else "10. IMPORTANT: For date filtering, use 'sale_date' column with strftime() function"}
        
        Technical Instructions:
        {"- Use Databricks SQL syntax (Spark SQL compatible)" if is_databricks else "- Use SQLite syntax"}
        {"- All tables are in public schema. Use public.table_name format (e.g., public.src_users, public.stg_stations, public.dim_user, public.fact_transactions, public.mart_daily_active_users)" if is_databricks else ""}
        {"- Example joins: SELECT * FROM public.stg_stations s JOIN public.dim_station d ON s.station_id = d.station_id" if is_databricks else ""}
        {"- DATA WAREHOUSE DESIGN: Follow layer selection rules - statistical queries MUST use mart_* tables, not fact_*/dim_*" if is_databricks else ""}
        {"- PRIORITY: For statistical/metric/trend queries, MANDATORY to use mart_* tables (e.g., public.mart_daily_active_users) over aggregating from fact_*/dim_* tables" if is_databricks else ""}
        {"- Table prefix selection: mart_* for analytics, fact_* for details, dim_* for attributes, stg_* for cleaned data, src_* for raw data" if is_databricks else ""}
        {"- Use RAG background knowledge for metadata (table structures, relationships, business rules) before exploring database schema" if is_databricks else ""}
        - Return ONLY ONE SQL query statement, no other explanations or multiple statements
        - CRITICAL: Generate exactly ONE SELECT statement, not multiple statements
        {"- Databricks supports standard SQL functions: EXTRACT(), YEAR(), MONTH(), DATE_FORMAT(), etc." if is_databricks else "- SQLite doesn't support EXTRACT() function, use strftime() instead"}
        {"- For date extraction in Databricks, use: EXTRACT(YEAR FROM date_column), EXTRACT(MONTH FROM date_column), DATE_FORMAT(date_column, 'yyyy-MM')" if is_databricks else "- SQLite doesn't support YEAR() function, use strftime('%Y', date_column) instead"}
        {"- SQLite doesn't support MONTH() function, use strftime('%m', date_column) instead" if not is_databricks else ""}
        {"- If user asks for table list, use: SHOW TABLES IN catalog.schema; or SHOW TABLES;" if is_databricks else "- If user asks for table list, use: SELECT name FROM sqlite_master WHERE type='table';"}
        {"- For date-related queries in Databricks, use: DATE_FORMAT(date_column, 'yyyy-MM'), EXTRACT(YEAR FROM date_column), etc." if is_databricks else "- For date-related queries, use strftime() function with proper syntax: strftime('%Y-%m', date_column)"}
        - SQL clause order: SELECT ... FROM ... WHERE ... GROUP BY ... ORDER BY ...
        {"- Example 1 (Monthly transaction trend - mart_daily_active_users): SELECT DATE_FORMAT(date, 'yyyy-MM') as Month, SUM(total_amount) as Total_Transaction_Amount, SUM(active_users) as Total_Active_Users, SUM(total_transactions) as Total_Transactions FROM public.mart_daily_active_users WHERE EXTRACT(YEAR FROM date) = 2025 GROUP BY Month ORDER BY Month;" if is_databricks else "- Example: SELECT strftime('%Y-%m', sale_date) as Month, SUM(total_amount) as Sales FROM dws_sales_cube WHERE strftime('%Y', sale_date) = '2025' GROUP BY Month ORDER BY Month;"}
        {"- Example 2 (Daily active users trend - mart_daily_active_users): SELECT date, active_users, total_transactions, total_amount, avg_transactions_per_user, avg_amount_per_transaction FROM public.mart_daily_active_users WHERE date >= '2025-11-01' AND date <= '2025-12-31' ORDER BY date;" if is_databricks else "- Example for pie chart by category: SELECT category, SUM(total_amount) as sales FROM dws_sales_cube WHERE strftime('%Y-%m', sale_date) BETWEEN '2025-07' AND '2025-09' GROUP BY category ORDER BY sales DESC;"}
        {"- Example 3 (Monthly top-up summary - mart_daily_topup_summary): SELECT DATE_FORMAT(date, 'yyyy-MM') as Month, SUM(total_amount) as Total_Topup_Amount, SUM(total_topups) as Total_Topups, SUM(unique_users) as Total_Users, AVG(avg_amount_per_topup) as Avg_Topup_Amount FROM public.mart_daily_topup_summary WHERE EXTRACT(YEAR FROM date) = 2025 GROUP BY Month ORDER BY Month;" if is_databricks else ""}
        {"- Example 4 (Top stations by flow - mart_station_flow_daily): SELECT station_name, SUM(total_transactions) as Total_Transactions, SUM(unique_users) as Total_Users, SUM(entry_count) as Total_Entries, SUM(exit_count) as Total_Exits, SUM(total_amount) as Total_Amount FROM public.mart_station_flow_daily WHERE date >= '2025-11-01' GROUP BY station_name ORDER BY Total_Transactions DESC LIMIT 10;" if is_databricks else ""}
        {"- Example 5 (Card type distribution - mart_user_card_type_summary): SELECT card_type, total_users, total_transactions, total_transaction_amount, total_topups, total_topup_amount FROM public.mart_user_card_type_summary ORDER BY total_users DESC;" if is_databricks else ""}
        {"- Example 6 (Route usage ranking - mart_route_usage_summary): SELECT route_name, route_type, total_transactions, unique_users, total_amount, avg_transactions_per_day FROM public.mart_route_usage_summary ORDER BY total_transactions DESC LIMIT 10;" if is_databricks else ""}
        {"- Example 7 (Payment method breakdown - mart_daily_topup_summary): SELECT DATE_FORMAT(date, 'yyyy-MM') as Month, SUM(cash_topups) as Cash_Topups, SUM(card_topups) as Card_Topups, SUM(mobile_topups) as Mobile_Topups, SUM(online_topups) as Online_Topups FROM public.mart_daily_topup_summary WHERE EXTRACT(YEAR FROM date) = 2025 GROUP BY Month ORDER BY Month;" if is_databricks else ""}
        {"- Example 8 (Weekend vs weekday comparison - mart_daily_active_users): SELECT is_weekend, AVG(active_users) as Avg_Active_Users, AVG(total_transactions) as Avg_Transactions, AVG(total_amount) as Avg_Amount FROM public.mart_daily_active_users WHERE date >= '2025-11-01' GROUP BY is_weekend;" if is_databricks else ""}
        {"- IMPORTANT: All tables are in public schema. Use public.table_name format (e.g., public.src_users, public.stg_stations, public.dim_user, public.fact_transactions, public.mart_daily_active_users)" if is_databricks else "- IMPORTANT: strftime() function requires two parameters: format string and date column"}
        - IMPORTANT: Do not use backslashes in table or column names, use underscores directly
        - IMPORTANT: For SELECT * queries, use: SELECT * FROM table_name (not table_name.*)
        - IMPORTANT: Do NOT include comments, explanations, or multiple SQL statements
        
        VALIDATION CHECKLIST:
        - [ ] All column names exist in the table structure
        {"- [ ] Table names use schema.table format (e.g., public.src_stations, staging.stg_stations)" if is_databricks else "- [ ] No 'customer_type' column used in dws_sales_cube (use 'category' instead)"}
        {"- [ ] Cross-schema joins use full path: schema1.table1 JOIN schema2.table2" if is_databricks else "- [ ] For sales amount: use 'total_amount' in dws_sales_cube"}
        {"- [ ] JOIN conditions use existing fields from both tables" if is_databricks else "- [ ] For quantity: use 'total_quantity_sold' NOT 'quantity_sold' in dws_sales_cube"}
        {"- [ ] Databricks SQL syntax used correctly (schema.table format)" if is_databricks else "- [ ] JOIN conditions use existing fields from both tables"}
        {"- [ ] No 'customer_type' column used in dws_sales_cube (if applicable, use 'category' instead)" if is_databricks else "- [ ] dws_sales_cube JOIN with dim_customer uses customer_id field"}
        {"- [ ] SQLite syntax used correctly" if not is_databricks else ""}
        - [ ] Query follows proper SQL clause order
        {"- [ ] Date filtering uses DATE_FORMAT() or EXTRACT() functions (Databricks)" if is_databricks else "- [ ] Date filtering uses strftime() function correctly"}
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
                # Ensure re is available (it's imported at module level, but ensure it's accessible here)
                import re as re_module
                # Extract table names referenced in the SQL (simple regex over FROM/JOIN)
                referenced = set()
                referenced_with_schema = {}  # Store full table references with schema
                for m in re_module.finditer(r"\b(?:FROM|JOIN)\s+([\w\.]+)", sql_query, re_module.IGNORECASE):
                    # Get full table reference (may include schema)
                    token = m.group(1)
                    base = token.split('.')[-1]
                    referenced.add(base)
                    referenced_with_schema[base] = token  # Store original reference

                # Build whitelist from actual tables_result string (comma/space separated)
                whitelist = set()
                marts_tables_in_whitelist = set()
                src_staging_tables_in_whitelist = set()
                if isinstance(tables_result, str):
                    # tables_result like: "dim_product, dwd_sales_detail, dws_sales_cube, ..." or "src_transactions, marts.daily_topup_summary, ..."
                    for t in re_module.split(r"[,\s]+", tables_result):
                        t_clean = t.strip()
                        if t_clean:
                            whitelist.add(t_clean)
                            # Categorize tables by layer
                            t_lower = t_clean.lower()
                            if 'marts' in t_lower or any(kw in t_lower for kw in ['summary', 'daily', 'flow', 'usage', 'topup', 'active', 'aggregat']):
                                marts_tables_in_whitelist.add(t_clean)
                            elif t_lower.startswith('src_') or t_lower.startswith('stg_') or 'staging' in t_lower or ('public' in t_lower and 'src' in t_lower):
                                src_staging_tables_in_whitelist.add(t_clean)

                # Known preferred names mapping to avoid layer mix-up
                canonical = {
                    'dwd_sales_cube': 'dws_sales_cube',
                }

                # Detect if this is a statistical/aggregation query
                is_statistical_query = bool(re_module.search(r'\b(SUM|COUNT|AVG|MAX|MIN|GROUP BY|aggregat|statistic|metric|trend|summary)\b', sql_query, re_module.IGNORECASE))
                
                corrected = sql_query
                for name in referenced:
                    target = name
                    original_ref = referenced_with_schema.get(name, name)
                    
                    # Check if table is from src/staging layer and query is statistical
                    if is_databricks and is_statistical_query:
                        # Check if table reference is from src/staging layer
                        is_src_staging = False
                        name_lower = name.lower()
                        ref_lower = original_ref.lower()
                        
                        # Check if it's a src/staging table
                        if name_lower.startswith('src_') or name_lower.startswith('stg_'):
                            is_src_staging = True
                        elif '.' in original_ref:
                            schema = original_ref.split('.')[0].lower()
                            if schema in ['src', 'staging', 'public'] and 'marts' not in ref_lower:
                                is_src_staging = True
                        elif name in src_staging_tables_in_whitelist:
                            is_src_staging = True
                        
                        if is_src_staging and marts_tables_in_whitelist:
                            # Try to find equivalent marts table based on context
                            # Look for marts tables that might match the query intent
                            marts_candidates = list(marts_tables_in_whitelist)
                            
                            if marts_candidates:
                                # Use fuzzy matching to find best marts table
                                # Try to match based on table name similarity
                                best_match = difflib.get_close_matches(name, marts_candidates, n=1, cutoff=0.2)
                                if not best_match:
                                    # If no close match, try to find by keywords (e.g., transaction -> daily, flow, summary)
                                    if 'transaction' in name_lower or 'trans' in name_lower:
                                        best_match = [t for t in marts_candidates if any(kw in t.lower() for kw in ['flow', 'daily', 'summary', 'transaction'])]
                                    elif 'topup' in name_lower or 'top' in name_lower:
                                        best_match = [t for t in marts_candidates if 'topup' in t.lower() or 'top' in t.lower()]
                                
                                if best_match:
                                    target = best_match[0]
                                    # Ensure public schema prefix and mart_ prefix if not already present
                                    if not target.startswith('public.') and not target.startswith('mart_'):
                                        # Check if it's already a full qualified name
                                        if '.' not in target:
                                            # Add mart_ prefix if not present
                                            if not target.startswith('mart_'):
                                                target = f"mart_{target}" if not target.startswith('mart_') else target
                                            target = f"public.{target}"
                                        else:
                                            # Has schema prefix, ensure it's public and has mart_ prefix
                                            schema, table = target.split('.', 1)
                                            if not table.startswith('mart_'):
                                                table = f"mart_{table}"
                                            target = f"public.{table}"
                                    elif target.startswith('mart_') and not target.startswith('public.'):
                                        target = f"public.{target}"
                                    logger.warning(f"⚠️  Statistical query detected using src/staging table '{original_ref}'. Auto-suggesting mart_* table: {target}")
                                    logger.warning(f"   Design principle: Use mart_* tables for aggregated statistics instead of raw source tables")
                    
                    if name in canonical:
                        target = canonical[name]
                    elif whitelist and name not in whitelist:
                        # fuzzy match to closest table in whitelist
                        candidates = difflib.get_close_matches(name, list(whitelist), n=1, cutoff=0.8)
                        if candidates:
                            target = candidates[0]
                    
                    # Apply replacement only if changed
                    if target != name and target != original_ref:
                        logger.warning(f"Auto-correcting table name in SQL: {original_ref} -> {target}")
                        # re_module is available in this scope
                        # Replace both with and without schema prefix
                        # Use word boundaries to avoid partial matches
                        corrected = re_module.sub(rf"\b{re_module.escape(original_ref)}\b", target, corrected, flags=re_module.IGNORECASE)
                        if original_ref != name:
                            corrected = re_module.sub(rf"\b{re_module.escape(name)}\b", target.split('.')[-1] if '.' in target else target, corrected, flags=re_module.IGNORECASE)

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
                        logger.info(f"Query result preview: {str(query_result)[:100]}...")
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
            "react_mode_used": False,
            "react_fallback_reason": react_fallback_reason,
            "node_outputs": {
                **state.get("node_outputs", {}),
                "sql_agent": {
                    "status": "completed",
                    "queries_count": len(executed_sqls),
                    "steps_count": 1,
                    "chart_suitable": chart_suitable,
                    "react_mode": False,
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
                import re
                from datetime import date, datetime
                from decimal import Decimal
                
                # Try ast.literal_eval first for simple types
                try:
                    data = ast.literal_eval(observation)
                    if isinstance(data, list) and len(data) > 0:
                        sample_row = data[0]
                        if isinstance(sample_row, tuple):
                            # Simple tuples parsed successfully
                            columns = []
                            for i in range(len(sample_row)):
                                if i == 0:
                                    columns.append("category")
                                elif i == 1:
                                    columns.append("sales_revenue")
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
                except (ValueError, SyntaxError):
                    # ast.literal_eval failed, likely due to datetime/Decimal objects
                    logger.info("ast.literal_eval failed, using eval with safe namespace for datetime/Decimal objects")
                    
                    # Use eval with a controlled namespace that includes datetime and Decimal
                    safe_namespace = {
                        'datetime': datetime,
                        'date': date,
                        'Decimal': Decimal,
                        '__builtins__': {}
                    }
                    
                    data = eval(observation, safe_namespace)
                    if isinstance(data, list) and len(data) > 0:
                        sample_row = data[0]
                        if isinstance(sample_row, tuple):
                            # Infer column names from data types
                            columns = []
                            for i, val in enumerate(sample_row):
                                if isinstance(val, (date, datetime)):
                                    columns.append("date" if i == 0 else f"date_{i}")
                                elif isinstance(val, (int, Decimal, float)):
                                    if i == 1:
                                        columns.append("count")
                                    elif i == 2:
                                        columns.append("amount")
                                    else:
                                        columns.append(f"value_{i}")
                                elif isinstance(val, str):
                                    columns.append("category" if i == 0 else f"category_{i}")
                                else:
                                    columns.append(f"col_{i}")
                            
                            rows = []
                            for row in data:
                                if isinstance(row, tuple):
                                    row_dict = {}
                                    for i, val in enumerate(row):
                                        # Convert datetime.date to string for JSON serialization
                                        if isinstance(val, date):
                                            row_dict[columns[i]] = val.isoformat()
                                        elif isinstance(val, Decimal):
                                            row_dict[columns[i]] = float(val)
                                        else:
                                            row_dict[columns[i]] = val
                                    rows.append(row_dict)
                            
                            logger.info(f"Parsed datetime/Decimal tuple result with {len(rows)} rows, {len(columns)} columns")
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
        
        retrieval_result = await perform_rag_retrieval(user_input, datasource, k=10)
        
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
                logger.info(f"Category-value response generated: {result[:100]}...")
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
            logger.info(f"Generic detailed response: {result[:100]}...")
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
        
        You MUST return a complete JSON configuration for the chart. Analyze the user's requirements and provide ALL required fields.
        
        CHART TYPE SELECTION RULES (CRITICAL):
        1. Use "line" chart for:
           - Time series data (trends over time)
           - Queries containing: "trend", "monthly", "yearly", "daily", "weekly", "over time", "时间", "趋势", "月度", "年度"
           - Data showing changes over time periods (months, years, days, etc.)
           - Sequential time-based comparisons
           - When categories represent time periods (e.g., months: "01", "02", ..., "12")
        
        2. Use "pie" chart for:
           - Proportions and distributions
           - Queries explicitly asking for "proportion", "distribution", "percentage", "share"
           - Comparing parts of a whole
           - Category-based data WITHOUT time dimension
        
        3. Use "bar" chart for:
           - Comparing categories (non-time-based)
           - Ranking and comparisons
           - When neither trend nor proportion is the focus
        
        TIME SERIES DETECTION:
        - If query contains "trend", "monthly", "yearly", "daily", "weekly", "over time", "时间", "趋势", "月度", "年度"
        - OR if data has time-based categories (months: "01"-"12", years: "2025", dates: "2025-01-15", etc.)
        - THEN set is_time_series: true, time_grouping: "month"/"year"/"day" as appropriate, chart_type: "line"
        
        Example 1 - TIME SERIES (Monthly transaction trend from mart_daily_active_users):
        Query: "Show monthly transaction amount trend for 2025"
        SQL: SELECT DATE_FORMAT(date, 'yyyy-MM') as Month, SUM(total_amount) as Total_Amount FROM public.mart_daily_active_users WHERE EXTRACT(YEAR FROM date) = 2025 GROUP BY Month ORDER BY Month
        Data columns: Month (string), Total_Amount (numeric)
        Chart config:
        {{
            "chart_type": "line",
            "title": "Monthly Transaction Amount Trend (2025)",
            "x_axis_label": "Month",
            "y_axis_label": "Total Transaction Amount (¥)",
            "data_field_for_labels": "Month",
            "data_field_for_values": "Total_Amount",
            "aggregation_method": "none",
            "time_grouping": "month",
            "is_time_series": true
        }}
        
        Example 2 - TIME SERIES (Daily active users from mart_daily_active_users):
        Query: "Show daily active users for November 2025"
        SQL: SELECT date, active_users, total_transactions, total_amount FROM public.mart_daily_active_users WHERE date >= '2025-11-01' AND date <= '2025-11-30' ORDER BY date
        Data columns: date (date), active_users (integer), total_transactions (integer), total_amount (numeric)
        Chart config:
        {{
            "chart_type": "line",
            "title": "Daily Active Users Trend (November 2025)",
            "x_axis_label": "Date",
            "y_axis_label": "Active Users",
            "data_field_for_labels": "date",
            "data_field_for_values": "active_users",
            "aggregation_method": "none",
            "time_grouping": "day",
            "is_time_series": true
        }}
        
        Example 3 - PROPORTION (Card type distribution from mart_user_card_type_summary):
        Query: "Show user distribution by card type"
        SQL: SELECT card_type, total_users, total_transaction_amount FROM public.mart_user_card_type_summary ORDER BY total_users DESC
        Data columns: card_type (string), total_users (integer), total_transaction_amount (numeric)
        Chart config:
        {{
            "chart_type": "pie",
            "title": "User Distribution by Card Type",
            "x_axis_label": "Card Type",
            "y_axis_label": "Total Users",
            "data_field_for_labels": "card_type",
            "data_field_for_values": "total_users",
            "aggregation_method": "none",
            "time_grouping": "none",
            "is_time_series": false
        }}
        
        Example 4 - BAR CHART (Top stations from mart_station_flow_daily):
        Query: "Show top 10 stations by transaction volume"
        SQL: SELECT station_name, SUM(total_transactions) as Total_Transactions FROM public.mart_station_flow_daily WHERE date >= '2025-11-01' GROUP BY station_name ORDER BY Total_Transactions DESC LIMIT 10
        Data columns: station_name (string), Total_Transactions (integer)
        Chart config:
        {{
            "chart_type": "bar",
            "title": "Top 10 Stations by Transaction Volume",
            "x_axis_label": "Station Name",
            "y_axis_label": "Total Transactions",
            "data_field_for_labels": "station_name",
            "data_field_for_values": "Total_Transactions",
            "aggregation_method": "none",
            "time_grouping": "none",
            "is_time_series": false
        }}
        
        Example 5 - TIME SERIES (Monthly top-up trend from mart_daily_topup_summary):
        Query: "Show monthly top-up amount trend"
        SQL: SELECT DATE_FORMAT(date, 'yyyy-MM') as Month, SUM(total_amount) as Total_Topup_Amount, SUM(total_topups) as Total_Topups FROM public.mart_daily_topup_summary WHERE EXTRACT(YEAR FROM date) = 2025 GROUP BY Month ORDER BY Month
        Data columns: Month (string), Total_Topup_Amount (numeric), Total_Topups (integer)
        Chart config:
        {{
            "chart_type": "line",
            "title": "Monthly Top-up Amount Trend (2025)",
            "x_axis_label": "Month",
            "y_axis_label": "Total Top-up Amount (¥)",
            "data_field_for_labels": "Month",
            "data_field_for_values": "Total_Topup_Amount",
            "aggregation_method": "none",
            "time_grouping": "month",
            "is_time_series": true
        }}
        
        Example 6 - BAR CHART (Route usage from mart_route_usage_summary):
        Query: "Show top routes by usage"
        SQL: SELECT route_name, total_transactions, unique_users, total_amount FROM public.mart_route_usage_summary ORDER BY total_transactions DESC LIMIT 10
        Data columns: route_name (string), total_transactions (integer), unique_users (integer), total_amount (numeric)
        Chart config:
        {{
            "chart_type": "bar",
            "title": "Top 10 Routes by Transaction Volume",
            "x_axis_label": "Route Name",
            "y_axis_label": "Total Transactions",
            "data_field_for_labels": "route_name",
            "data_field_for_values": "total_transactions",
            "aggregation_method": "none",
            "time_grouping": "none",
            "is_time_series": false
        }}
        
        IMPORTANT: 
        1. Always provide a meaningful title based on the query - NEVER leave title empty
        2. Title should be descriptive and include relevant time periods if mentioned
        3. For time series queries, use chart_type: "line" and set is_time_series: true
        4. For sales data, use y_axis_label: "Sales Revenue ($)" or "Sales Amount ($)"
        5. For time series, use x_axis_label: "Month", "Year", "Date", etc.
        6. Return ONLY valid JSON, no additional text
        
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
        
        # Check if this is a time series query (trend, monthly, yearly, etc.)
        is_time_series_query = any(kw in user_input_lower for kw in [
            'trend', 'monthly', 'yearly', 'daily', 'weekly', 'over time', 
            '时间', '趋势', '月度', '年度', '日期', '天', '周'
        ])
        
        # Check if data indicates time series (categories are months, years, dates)
        data_summary_lower = (data_summary or "").lower()
        has_time_categories = any(indicator in data_summary_lower for indicator in [
            'month', 'year', 'date', '01', '02', '03', '12', '2025', '2024'
        ])
        
        # Priority-based chart type detection
        if "pie chart" in user_input_lower or "pie" in user_input_lower:
            # Only use pie if explicitly requested AND not a time series query
            if not is_time_series_query and not has_time_categories:
                detected_type = "pie"
            else:
                detected_type = "line"  # Override to line for time series
                logger.info("Overriding pie chart to line chart for time series query")
        elif "line chart" in user_input_lower or "line" in user_input_lower:
            detected_type = "line"
        elif "bar chart" in user_input_lower or "bar" in user_input_lower:
            detected_type = "bar"
        elif is_time_series_query or has_time_categories:
            # Force line chart for time series queries
            detected_type = "line"
            # Update chart_analysis to reflect time series detection
            chart_analysis["is_time_series"] = True
            if chart_analysis.get("time_grouping", "none") == "none":
                # Detect time grouping from query
                if "monthly" in user_input_lower or "month" in user_input_lower:
                    chart_analysis["time_grouping"] = "month"
                elif "yearly" in user_input_lower or "year" in user_input_lower:
                    chart_analysis["time_grouping"] = "year"
                elif "daily" in user_input_lower or "day" in user_input_lower:
                    chart_analysis["time_grouping"] = "day"
                elif "weekly" in user_input_lower or "week" in user_input_lower:
                    chart_analysis["time_grouping"] = "week"
                else:
                    chart_analysis["time_grouping"] = "month"  # Default for trend queries
            logger.info(f"Detected time series query/data, forcing chart_type to 'line', time_grouping: {chart_analysis.get('time_grouping')}")
        
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
    import re
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
        # Support various value field names: "value", "sales_revenue", etc.
        value_field_names = ["value", "sales_revenue", "revenue", "amount", "total", "sum"]
        value_field = None
        if isinstance(sample_row, dict) and "category" in sample_row:
            # Find the value field
            for field_name in value_field_names:
                if field_name in sample_row:
                    value_field = field_name
                    break
            # If no standard field found, try to find the second numeric field
            if not value_field:
                for key, val in sample_row.items():
                    if key != "category" and isinstance(val, (int, float)):
                        value_field = key
                        break
        
        if isinstance(sample_row, dict) and "category" in sample_row and value_field:
            logger.info(f"Processing {len(rows)} rows of category-value data (value field: {value_field})")
            
            # Detect if this is time series data
            # First check chart_analysis and user_input (most reliable)
            user_input_lower = (user_input or "").lower()
            is_time_series_from_analysis = (
                chart_analysis.get("is_time_series", False) or 
                chart_analysis.get("time_grouping", "none") != "none" or
                any(kw in user_input_lower for kw in ['trend', 'monthly', 'yearly', 'daily', 'weekly', 'over time', '时间', '趋势', '月度', '年度', '日期', '天', '周'])
            )
            
            # Check sample categories to detect time format (even if analysis doesn't suggest it)
            is_time_series = is_time_series_from_analysis
            time_sort_keys = {}
            sample_categories = [str(row.get("category", "")) for row in rows[:min(5, len(rows))]]
            
            # Always check category format to detect time series, regardless of analysis
            for cat in sample_categories:
                ts_detected, sort_key = _detect_time_series_category(cat, chart_analysis, user_input)
                if ts_detected and sort_key is not None:
                    is_time_series = True
                    # Update chart_analysis if it wasn't set correctly
                    if not chart_analysis.get("is_time_series", False):
                        chart_analysis["is_time_series"] = True
                    if chart_analysis.get("time_grouping", "none") == "none":
                        # Detect time grouping from category format
                        if re.match(r'^(0?[1-9]|1[0-2])$', str(cat)):
                            chart_analysis["time_grouping"] = "month"
                        elif re.match(r'^\d{4}$', str(cat)):
                            chart_analysis["time_grouping"] = "year"
                    break
            
            # Build sort keys for all rows
            for row in rows:
                category = str(row.get("category", ""))
                ts_detected, sort_key = _detect_time_series_category(category, chart_analysis, user_input)
                logger.info(f"Category '{category}': ts_detected={ts_detected}, sort_key={sort_key}, chart_analysis.is_time_series={chart_analysis.get('is_time_series')}, time_grouping={chart_analysis.get('time_grouping')}")
                if ts_detected and sort_key is not None:
                    time_sort_keys[category] = sort_key
                    if not is_time_series:
                        is_time_series = True
                        # Update chart_analysis
                        chart_analysis["is_time_series"] = True
                        if chart_analysis.get("time_grouping", "none") == "none":
                            if re.match(r'^(0?[1-9]|1[0-2])$', category):
                                chart_analysis["time_grouping"] = "month"
                            elif re.match(r'^\d{4}$', category):
                                chart_analysis["time_grouping"] = "year"
                else:
                    # Log when detection fails for debugging
                    logger.warning(f"Time series detection failed for category '{category}': ts_detected={ts_detected}, sort_key={sort_key}, chart_analysis={chart_analysis.get('is_time_series')}, time_grouping={chart_analysis.get('time_grouping')}")
            
            logger.info(f"Time series detection result: is_time_series={is_time_series}, time_sort_keys={len(time_sort_keys)} keys, sample_keys={list(time_sort_keys.items())[:5] if time_sort_keys else []}")
            
            # Sort rows based on data type
            if is_time_series and time_sort_keys:
                # Sort by time order (ascending for chronological order)
                def time_sort_key(row):
                    category = str(row.get("category", ""))
                    return time_sort_keys.get(category, float('inf'))
                sorted_rows = sorted(rows, key=time_sort_key)
                logger.info(f"Is time series: True, Time grouping: {chart_analysis.get('time_grouping', 'none')}, time_sort_keys count: {len(time_sort_keys)}")
                logger.info("Sorted by time (chronological order)")
            else:
                # Sort by value descending for non-time series data
                sorted_rows = sorted(rows, key=lambda x: float(x.get(value_field, 0)), reverse=True)
                logger.info(f"Sorted by value (descending), value_field: {value_field}")
            
            processed_rows = sorted_rows  # Use all data points
            
            # Extract final labels and values
            for row in processed_rows:
                try:
                    category = str(row["category"]) if row["category"] else f"Item{len(labels)+1}"
                    value = float(row[value_field]) if isinstance(row.get(value_field), (int, float)) else 0
                    
                    # Format label based on context (especially for time series)
                    if is_time_series:
                        # Format time labels appropriately
                        time_grouping = chart_analysis.get("time_grouping", "none")
                        if time_grouping == "month" and category.isdigit() and 1 <= int(category) <= 12:
                            # Format month number as month name (English)
                            month_names = ["January", "February", "March", "April", "May", "June",
                                          "July", "August", "September", "October", "November", "December"]
                            month_num = int(category)
                            label = month_names[month_num - 1]
                        elif time_grouping == "day" or time_grouping == "daily":
                            # Format as date
                            label = _format_date_label(category)
                        elif time_grouping != "none":
                            # Use time formatting function if available
                            label = _format_time_label(category, time_grouping) if time_grouping != "none" else category
                        else:
                            # Try to detect date format even if time_grouping is not set
                            import re
                            if re.match(r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$', category) or \
                               re.match(r'^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$', category) or \
                               re.match(r'^(\d{8})$', category):
                                label = _format_date_label(category)
                            else:
                                label = category
                    else:
                        label = category
                    
                    labels.append(label)
                    values.append(value)
                    logger.info(f"Added data point: {label} -> {value}")
                    
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Error processing row: {e}")
                    continue
            
            logger.info(f"Successfully extracted {len(labels)} data points using {'time-series' if is_time_series else 'value-based'} analysis")
            logger.info(f"Final chart data: labels={labels}, values={values}")
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

def _detect_time_series_category(category: str, chart_analysis: Dict[str, Any], user_input: str = "") -> tuple:
    """
    Detect if a category value represents time series data and return sorting key
    
    Returns:
        (is_time_series, sort_key) tuple
        - is_time_series: bool indicating if this is time series data
        - sort_key: value to use for sorting (time-based or None)
    """
    if not category:
        return False, None
    
    category_str = str(category).strip()
    import re
    
    # First, try to detect time format directly from category (most reliable)
    # This doesn't depend on chart_analysis state
    
    # Month format: '01', '02', ..., '12' (1-12) - check this first as it's common
    if re.match(r'^(0?[1-9]|1[0-2])$', category_str):
        month_num = int(category_str)
        return True, month_num
    
    # Check chart_analysis and user input for additional context
    is_time_series = chart_analysis.get("is_time_series", False)
    time_grouping = chart_analysis.get("time_grouping", "none")
    
    # Check user input for time-related keywords
    user_input_lower = (user_input or "").lower()
    has_time_keywords = any(kw in user_input_lower for kw in [
        'trend', 'monthly', 'yearly', 'daily', 'weekly', 'over time', 
        'date', 'day', '时间', '趋势', '月度', '年度', '日期', '天', '周'
    ])
    
    # If explicitly marked as time series or has time grouping, treat as time series
    if is_time_series or time_grouping != "none" or has_time_keywords:
        # Detect other time formats and create sort key
        
        # Date format: '2025-01-15', '2025/01/15' (YYYY-MM-DD or YYYY/MM/DD)
        date_match_iso = re.match(r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$', category_str)
        if date_match_iso:
            year = int(date_match_iso.group(1))
            month = int(date_match_iso.group(2))
            day = int(date_match_iso.group(3))
            if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                # Return YYYYMMDD as integer for sorting
                return True, year * 10000 + month * 100 + day
        
        # Date format: '01-15-2025', '01/15/2025' (MM-DD-YYYY or MM/DD/YYYY) - US format
        date_match_us = re.match(r'^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$', category_str)
        if date_match_us:
            month = int(date_match_us.group(1))
            day = int(date_match_us.group(2))
            year = int(date_match_us.group(3))
            if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                return True, year * 10000 + month * 100 + day
        
        # Date format: '15-01-2025', '15/01/2025' (DD-MM-YYYY or DD/MM/YYYY) - EU format
        date_match_eu = re.match(r'^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$', category_str)
        if date_match_eu:
            # Try to distinguish: if first part > 12, it's likely DD-MM-YYYY
            first_part = int(date_match_eu.group(1))
            second_part = int(date_match_eu.group(2))
            year = int(date_match_eu.group(3))
            if first_part > 12 and 1 <= second_part <= 12:
                # DD-MM-YYYY format
                day = first_part
                month = second_part
                if 1900 <= year <= 2100 and 1 <= day <= 31:
                    return True, year * 10000 + month * 100 + day
        
        # Date format: '20250115' (YYYYMMDD) - compact format
        date_match_compact = re.match(r'^(\d{8})$', category_str)
        if date_match_compact:
            year = int(category_str[:4])
            month = int(category_str[4:6])
            day = int(category_str[6:8])
            if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                return True, year * 10000 + month * 100 + day
        
        # Month format: '01', '02', ..., '12' (1-12)
        if re.match(r'^(0?[1-9]|1[0-2])$', category_str):
            month_num = int(category_str)
            return True, month_num
        
        # Year-month format: '2025-01', '2025-1', etc.
        year_month_match = re.match(r'^(\d{4})[-/]?(\d{1,2})$', category_str)
        if year_month_match:
            year = int(year_month_match.group(1))
            month = int(year_month_match.group(2))
            if 1 <= month <= 12:
                return True, year * 100 + month
        
        # Year format: '2025', '2024', etc.
        if re.match(r'^\d{4}$', category_str):
            year = int(category_str)
            if 1900 <= year <= 2100:
                return True, year
        
        # Quarter format: '2025-Q1', 'Q1-2025', etc.
        quarter_match = re.match(r'(\d{4})[-/]?Q(\d)|Q(\d)[-/]?(\d{4})', category_str, re.IGNORECASE)
        if quarter_match:
            if quarter_match.group(1):  # Year-Q format
                year = int(quarter_match.group(1))
                quarter = int(quarter_match.group(2))
            else:  # Q-Year format
                quarter = int(quarter_match.group(3))
                year = int(quarter_match.group(4))
            if 1 <= quarter <= 4:
                return True, year * 10 + quarter
        
        # Week format: '2025-W01', '2025-W1', etc.
        week_match = re.match(r'(\d{4})[-/]?W(\d{1,2})', category_str, re.IGNORECASE)
        if week_match:
            year = int(week_match.group(1))
            week = int(week_match.group(2))
            if 1 <= week <= 53:
                return True, year * 100 + week
        
        # If time_grouping is set but format doesn't match, still treat as time series
        # and use string comparison as fallback
        if time_grouping != "none":
            return True, category_str
    
    return False, None

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

def _format_date_label(date_str: str) -> str:
    """Format date string for display"""
    import re
    try:
        # ISO format: '2025-01-15' or '2025/01/15'
        date_match_iso = re.match(r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$', date_str)
        if date_match_iso:
            year = int(date_match_iso.group(1))
            month = int(date_match_iso.group(2))
            day = int(date_match_iso.group(3))
            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            if 1 <= month <= 12:
                return f"{month_names[month - 1]} {day}, {year}"
        
        # US format: '01-15-2025' or '01/15/2025'
        date_match_us = re.match(r'^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$', date_str)
        if date_match_us:
            month = int(date_match_us.group(1))
            day = int(date_match_us.group(2))
            year = int(date_match_us.group(3))
            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            if 1 <= month <= 12:
                return f"{month_names[month - 1]} {day}, {year}"
        
        # EU format: '15-01-2025' or '15/01/2025' (if first part > 12)
        date_match_eu = re.match(r'^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$', date_str)
        if date_match_eu:
            first_part = int(date_match_eu.group(1))
            second_part = int(date_match_eu.group(2))
            year = int(date_match_eu.group(3))
            if first_part > 12 and 1 <= second_part <= 12:
                day = first_part
                month = second_part
                month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                return f"{month_names[month - 1]} {day}, {year}"
        
        # Compact format: '20250115'
        date_match_compact = re.match(r'^(\d{8})$', date_str)
        if date_match_compact:
            year = int(date_str[:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            if 1 <= month <= 12:
                return f"{month_names[month - 1]} {day}, {year}"
        
        # If no match, return original
        return date_str
    except:
        return date_str

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
        elif time_grouping == "day" or time_grouping == "daily":
            # Try to format as date
            return _format_date_label(time_key)
        else:
            # Try to detect if it's a date format
            import re
            if re.match(r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$', time_key) or \
               re.match(r'^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$', time_key) or \
               re.match(r'^(\d{8})$', time_key):
                return _format_date_label(time_key)
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
    
    # Add interrupt check after rag_query_node
    workflow.add_conditional_edges(
        "rag_query_node",
        check_interrupt_status,
        {
            "continue": "router_node",
            "interrupt": "interrupt_node"
        }
    )
    
    # Add interrupt check after router_node
    workflow.add_conditional_edges(
        "router_node",
        check_interrupt_status,
        {
            "continue": "router_decision_node",
            "interrupt": "interrupt_node"
        }
    )
    
    # Add router decision node
    workflow.add_node("router_decision_node", router_decision_node)
    
    # Router decision routes to either sql_agent or llm_processing
    workflow.add_conditional_edges(
        "router_decision_node",
        lambda state: "sql_agent_node" if state.get("need_sql_agent", False) else "llm_processing_node",
        {
            "sql_agent_node": "sql_agent_node",
            "llm_processing_node": "llm_processing_node"
        }
    )

    # Add interrupt check after sql_agent_node
    workflow.add_conditional_edges(
        "sql_agent_node",
        check_interrupt_status,
        {
            "continue": "sql_agent_decision_node",
            "interrupt": "interrupt_node"
        }
    )
    
    # Add sql agent decision node
    workflow.add_node("sql_agent_decision_node", sql_agent_decision_node)
    
    # SQL agent decision routes to either chart_process or llm_processing
    workflow.add_conditional_edges(
        "sql_agent_decision_node",
        lambda state: "chart_process_node" if state.get("chart_suitable", False) else "llm_processing_node",
        {
            "chart_process_node": "chart_process_node",
            "llm_processing_node": "llm_processing_node"
        }
    )
    
    # Add interrupt check after chart_process_node
    workflow.add_conditional_edges(
        "chart_process_node",
        check_interrupt_status,
        {
            "continue": "llm_processing_node",
            "interrupt": "interrupt_node"
        }
    )
    
    # Add interrupt check after llm_processing_node
    workflow.add_conditional_edges(
        "llm_processing_node",
        check_interrupt_status,
        {
            "continue": "end_node",
            "interrupt": "interrupt_node"
        }
    )
    
    # Interrupt node goes to end (workflow stops)
    workflow.add_edge("interrupt_node", "end_node")

    # Compile the workflow
    app = workflow.compile()
    
    logger.info("New workflow created with 6 nodes: start → rag_query → router → [sql_agent → chart?] → llm_processing → end")
    
    return app
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

            elif paused_node == "rag_query_node":
                # Continue from RAG query to router
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
                    # RAG only path - go directly to LLM processing
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
                    # RAG only path - go directly to LLM processing
                    state = await llm_processing_node(state)
                    await _emit(state)

            elif paused_node == "router_node":
                # Continue from router based on decision
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
                    # RAG only path - go directly to LLM processing
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
    
    logger.info(f"�?[BACKEND-LG] get_execution_final_state completed successfully")
    return state

def set_execution_final_state(execution_id: str, state: Dict[str, Any]):
    """Set the final state of an execution for HITL operations"""
    logger.info(f"🔄 [BACKEND-LG] set_execution_final_state called")
    logger.info(f"📥 [BACKEND-LG] set_execution_final_state input params: execution_id={execution_id}")
    logger.info(f"📥 [BACKEND-LG] set_execution_final_state state keys: {list(state.keys())}")
    
    _execution_states[execution_id] = state
    logger.info(f"📊 [BACKEND-LG] set_execution_final_state stored state for execution {execution_id}")
    
    logger.info(f"✅ [BACKEND-LG] set_execution_final_state completed successfully")
