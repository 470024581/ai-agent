"""
Intelligent Data Analysis Flow Based on LangGraph
"""
import json
import time
import uuid
import asyncio
import re
from typing import Dict, Any, List, Optional, TypedDict
import logging
import requests
from langgraph.graph import StateGraph
from ..agents.intelligent_agent import llm, perform_rag_query, get_answer_from_sqltable_datasource, get_query_from_sqltable_datasource
from ..models.data_models import WorkflowEvent, WorkflowEventType, NodeStatus
from ..database.db_operations import get_active_datasource  # Added to get active datasource

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
    """Define graph state for hybrid query workflow"""
    # === Basic fields ===
    user_input: str
    datasource: Dict[str, Any]
    execution_id: str  # For WebSocket routing and token streaming
    
    # === Intent analysis results ===
    query_path: str  # "rag_only" | "sql_only" | "rag_sql"
    need_chart: bool  # Whether chart visualization is needed
    analysis_reasoning: str  # LLM reasoning process
    detected_keywords: List[str]  # Detected keywords from query
    
    # === Legacy fields (for backward compatibility) ===
    query_type: Optional[str]  # "sql" or "rag" - deprecated but kept for compatibility
    sql_task_type: Optional[str]  # "query" or "chart" - deprecated
    
    # === RAG related ===
    rag_result: Optional[str]  # Retrieved document content
    rag_sources: Optional[List[str]]  # Source file list
    rag_confidence: Optional[float]  # Retrieval confidence score
    rag_executed: bool  # Flag to prevent duplicate RAG execution
    
    # === SQL related ===
    structured_data: Optional[Dict[str, Any]]  # Query result data
    sql_answer: Optional[str]  # Initial SQL result description
    executed_sql: Optional[str]  # Executed SQL statement
    
    # === Merged results (for rag_sql path) ===
    merged_context: Optional[str]  # Integrated context from RAG + SQL
    data_with_metadata: Optional[Dict[str, Any]]  # Data with metadata annotations
    
    # === Chart related ===
    chart_config: Optional[Dict[str, Any]]  # Chart configuration
    chart_data: Optional[List[Dict]]  # Chart data
    chart_type: Optional[str]  # Chart type
    chart_image: Optional[str]  # Legacy field - chart image path
    
    # === Final output ===
    answer: str  # Final natural language answer
    final_result: Optional[Dict[str, Any]]  # Complete result package
    
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

def intent_analysis_node(state: GraphState) -> GraphState:
    """Intent Analysis Node: Optimized single-call intent analysis"""
    user_input = state["user_input"]
    execution_id = state.get("execution_id", "unknown")
    
    logger.info(f"Intent Analysis Node - Analyzing query: {user_input}")
    
    if not llm:
        logger.warning("LLM not available, using fallback rule-based intent analysis")
        return _fallback_intent_analysis(state)
    
    try:
        # Optimized single-call analysis
        analysis_prompt = f"""
        Analyze this user query and determine the execution path: "{user_input}"
        
        Analysis steps:
        1. Identify if query asks about documents/concepts/designs/metadata
        2. Identify if query asks about database data/statistics/numbers  
        3. Check for chart/visualization keywords
        4. Determine if both knowledge and data are needed
        
        Keywords to check:
        - Chart: chart, graph, visualization, pie chart, bar chart, line chart, 图表, 可视化, 饼图, 柱状图, 折线图
        - Data: data, query, sales, order, product, 数据, 查询, 统计, 分析, 销售, 订单, 产品
        - Documents: meaning, definition, design, concept, explain, 含义, 定义, 设计, 方案, 原则, 概念, 解释
        
        Return ONLY a JSON response:
        {{
            "query_path": "rag_only|sql_only|rag_sql",
            "need_chart": true/false,
            "reasoning": "Brief explanation of your decision",
            "detected_keywords": ["keyword1", "keyword2"]
        }}
        """
        
        response = llm.invoke(analysis_prompt)
        response_text = _extract_content(response)
        logger.info(f"Intent Analysis - Response: {response_text[:200]}...")
        
        # Parse JSON response
        try:
            import json
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                decision_json = json.loads(response_text[json_start:json_end])
                
                query_path = decision_json.get("query_path", "rag_only")
                need_chart = decision_json.get("need_chart", False)
                reasoning = decision_json.get("reasoning", "No reasoning provided")
                detected_keywords = decision_json.get("detected_keywords", [])
                
                # Validate query_path
                if query_path not in ["rag_only", "sql_only", "rag_sql"]:
                    logger.warning(f"Invalid query_path: {query_path}, defaulting to rag_only")
                    query_path = "rag_only"
                
                logger.info(f"Intent Analysis Result - Path: {query_path}, Chart: {need_chart}")
                
                return {
                    **state,
                    "query_path": query_path,
                    "need_chart": need_chart,
                    "analysis_reasoning": reasoning,
                    "detected_keywords": detected_keywords,
                    # Legacy compatibility
                    "query_type": "sql" if query_path in ["sql_only", "rag_sql"] else "rag",
                    "sql_task_type": "chart" if need_chart else "query",
                    "node_outputs": {
                        **state.get("node_outputs", {}),
                        "intent_analysis": {
                            "status": "completed",
                            "timestamp": time.time(),
                            "query_path": query_path,
                            "need_chart": need_chart,
                            "reasoning": reasoning,
                            "keywords": detected_keywords
                        }
                    }
                }
            else:
                raise ValueError("No valid JSON found in response")
                
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse intent analysis JSON: {e}, using fallback")
            return _fallback_intent_analysis(state)
            
    except Exception as e:
        logger.error(f"Intent analysis failed: {e}, using fallback")
        return _fallback_intent_analysis(state)

def _fallback_intent_analysis(state: GraphState) -> GraphState:
    """Fallback rule-based intent analysis when LLM is not available"""
    user_input = state["user_input"]
    
    # Rule-based keyword detection
    chart_keywords = ["图表", "可视化", "饼图", "柱状图", "折线图", "chart", "graph", "visualization", "pie chart", "bar chart", "line chart"]
    db_keywords = ["数据", "查询", "统计", "分析", "销售", "订单", "产品", "data", "query", "sales", "order", "product"]
    doc_keywords = ["含义", "定义", "设计", "方案", "原则", "概念", "解释", "meaning", "definition", "design", "concept", "explain"]
    
    detected_keywords = []
    has_chart = False
    has_db = False
    has_doc = False
    
    user_lower = user_input.lower()
    
    for keyword in chart_keywords:
        if keyword in user_lower:
            detected_keywords.append(keyword)
            has_chart = True
    
    for keyword in db_keywords:
        if keyword in user_lower:
            detected_keywords.append(keyword)
            has_db = True
    
    for keyword in doc_keywords:
        if keyword in user_lower:
            detected_keywords.append(keyword)
            has_doc = True
    
    # Determine query path
    if has_doc and has_db:
        query_path = "rag_sql"
    elif has_db:
        query_path = "sql_only"
    else:
        query_path = "rag_only"
    
    need_chart = has_chart or (has_db and not has_doc)  # All SQL queries try charts unless pure RAG
    
    reasoning = f"Rule-based analysis: doc={has_doc}, db={has_db}, chart={has_chart}"
    
    logger.info(f"Fallback Intent Analysis - Path: {query_path}, Chart: {need_chart}")
    
    return {
        **state,
        "query_path": query_path,
        "need_chart": need_chart,
        "analysis_reasoning": reasoning,
        "detected_keywords": detected_keywords,
        # Legacy compatibility
        "query_type": "sql" if query_path in ["sql_only", "rag_sql"] else "rag",
        "sql_task_type": "chart" if need_chart else "query",
        "node_outputs": {
            **state.get("node_outputs", {}),
            "intent_analysis": {
                "status": "completed",
                "timestamp": time.time(),
                "query_path": query_path,
                "need_chart": need_chart,
                "reasoning": reasoning,
                "method": "fallback"
            }
        }
    }

def _extract_content(response) -> str:
    """Extract content from LLM response"""
    if hasattr(response, 'content'):
        return response.content.strip()
    elif isinstance(response, str):
        return response.strip()
    else:
        return str(response).strip()

# Legacy router_node for backward compatibility
def router_node(state: GraphState) -> GraphState:
    """Legacy router node - redirects to intent_analysis_node"""
    logger.info("Using legacy router_node - redirecting to intent_analysis_node")
    return intent_analysis_node(state)

# Remove hitl_checkpoint decorator completely and use LangGraph native interrupt
def sql_classifier_node(state: GraphState) -> GraphState:
    """SQL classification node: use LLM to determine if it's data query or chart building"""
    user_input = state["user_input"]
    
    if not llm:
        logger.warning("LLM not available, using fallback rule-based SQL classification")
        # Fallback to rule-based judgment
        chart_keywords = [
            "chart", "visualization", "trend", "distribution", "bar chart", 
            "line chart", "pie chart", "graph", "plot", "generate", "create", "build",
            "visualize", "show", "display", "draw"
        ]
        
        if any(keyword in user_input.lower() for keyword in chart_keywords):
            sql_task_type = "chart"
        else:
            sql_task_type = "query"
    else:
        # Use LLM for semantic classification (with strong rule overrides)
        try:
            prompt = f"""
            Analyze the following user query and determine what the user wants:
            1. query - Get data query results (text-based data analysis)
            2. chart - Generate charts or visualizations (charts, trend graphs, distribution graphs, etc.)
            
            User query: "{user_input}"
            
            Only answer "query" or "chart" (lowercase, no explanation needed).
            """
            
            response = llm.invoke(prompt)
            
            # Handle different response types (Ollama returns string, OpenAI returns object)
            if hasattr(response, 'content'):
                sql_task_type = response.content.strip().lower()
            elif isinstance(response, str):
                sql_task_type = response.strip().lower()
            else:
                sql_task_type = str(response).strip().lower()
            
            # Normalize punctuation and whitespace
            sql_task_type = sql_task_type.strip().strip(".!,; ")
            
            # Strong keyword override for chart intent
            chart_keywords = [
                "pie", "pie chart", "proportion", "percentage", "distribution", "breakdown",
                "饼图", "占比", "比例", "分布", "图表"
            ]
            if any(k in user_input.lower() for k in chart_keywords):
                sql_task_type = "chart"
            
            # Validate response
            if sql_task_type not in ["query", "chart"]:
                logger.warning(f"Invalid LLM SQL classification response: {sql_task_type}, defaulting to chart if keywords present else query")
                sql_task_type = "chart" if any(k in user_input.lower() for k in chart_keywords) else "query"
                
        except Exception as e:
            logger.error(f"Error in LLM SQL classification: {e}, falling back to rule-based")
            # Fallback to rule-based
            chart_keywords = [
                "chart", "visualization", "trend", "distribution", "bar chart", 
                "line chart", "pie chart", "graph", "plot", "generate", "create", "build",
                "visualize", "show", "display", "draw"
            ]
            if any(keyword in user_input.lower() for keyword in chart_keywords):
                sql_task_type = "chart"
            else:
                sql_task_type = "query"
    
    logger.info(f"SQL task type: {sql_task_type} for input: {user_input}")
    
    # Return updated state while preserving existing state
    return {**state, "sql_task_type": sql_task_type}

async def sql_query_node(state: GraphState) -> GraphState:
    """Enhanced SQL query node: supports both direct queries and RAG-guided queries, with integrated result merging and chart decision"""
    try:
        user_input = state["user_input"]
        datasource = state.get("datasource")
        rag_result = state.get("rag_result")  # Optional RAG metadata for guidance
        query_path = state.get("query_path", "sql_only")
        
        if not datasource:
            error_msg = "No data source found in state. Please select or create a data source first."
            logger.error(error_msg)
            return {
                **state,
                "error": error_msg,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "sql_query": {
                        "status": "error",
                        "timestamp": time.time(),
                        "error": "No datasource in state"
                    }
                }
            }
        
        # Force SQL branch to use built-in DEFAULT datasource (ID=1)
        if datasource.get("type") != "default":
            try:
                from ..database.db_operations import get_datasource
                builtin_ds = await get_datasource(1)
                if builtin_ds:
                    datasource = builtin_ds
                    logger.info("SQL branch: switched to built-in DEFAULT datasource (ID=1)")
            except Exception as _e:
                logger.warning(f"SQL branch: failed to switch to DEFAULT datasource: {_e}")

        logger.info(f"SQL Query Node - Path: {query_path}, Has RAG guidance: {bool(rag_result)}")
        
        # Enhanced query processing based on path
        if query_path == "rag_sql" and rag_result:
            # Use RAG metadata to guide SQL generation
            logger.info("SQL Query Node - Using RAG-guided SQL generation")
            result = await _perform_rag_guided_sql_query(user_input, datasource, rag_result)
        else:
            # Direct SQL query (existing logic)
            logger.info("SQL Query Node - Using direct SQL query")
            result = await get_query_from_sqltable_datasource(user_input, datasource)
        
        if result["success"]:
            structured_data = result.get("data", {})
            executed_sql = result.get("executed_sql", "")
            sql_answer = result.get("answer", "")
            
            # Validate the result structure
            if not structured_data:
                error_msg = "No structured data returned from query"
                logger.error(error_msg)
                return {
                    **state,
                    "error": error_msg,
                    "node_outputs": {
                        **state.get("node_outputs", {}),
                        "sql_query": {
                            "status": "error",
                            "timestamp": time.time(),
                            "error": "No data available"
                        }
                    }
                }
            
            logger.info(f"SQL query successful, data: {structured_data}")
            
            # === INTEGRATED RESULT MERGING AND CHART DECISION ===
            
            # 1. Result Merging Logic (from result_merge_node)
            merged_context = None
            data_with_metadata = None
            
            if rag_result and structured_data:
                # Normal case: both RAG and SQL available
                logger.info("SQL Query Node - Combining RAG metadata with SQL data")
                merged_context = f"""
                [Metadata Context]
                {rag_result}
                
                [Data Query Results]
                Query: {user_input}
                SQL: {executed_sql}
                Data: {structured_data.get('rows', [])}
                
                The metadata above explains the meaning and context of the data below.
                """
                
                data_with_metadata = {
                    "metadata_context": rag_result,
                    "query_context": user_input,
                    "sql_query": executed_sql,
                    "data_rows": structured_data.get('rows', []),
                    "data_columns": structured_data.get('columns', []),
                    "row_count": len(structured_data.get('rows', [])),
                    "merged_at": time.time()
                }
                logger.info(f"SQL Query Node - Result merge completed - Rows: {len(structured_data.get('rows', []))}")
                
            elif not rag_result and structured_data:
                # Handle case where RAG failed but SQL succeeded
                logger.warning("SQL Query Node - RAG result missing, proceeding with SQL data only")
                merged_context = f"""
                [Data Query Results]
                Query: {user_input}
                SQL: {executed_sql}
                Data: {structured_data.get('rows', [])}
                
                Note: No metadata context available, using direct data query results.
                """
                
                data_with_metadata = {
                    "metadata_context": "No metadata available",
                    "query_context": user_input,
                    "sql_query": executed_sql,
                    "data_rows": structured_data.get('rows', []),
                    "data_columns": structured_data.get('columns', []),
                    "row_count": len(structured_data.get('rows', [])),
                    "merged_at": time.time(),
                    "rag_failed": True
                }
            
            # 2. Chart Decision Logic (from chart_decision_node)
            chart_decision = "skip_chart"
            if query_path in ["sql_only", "rag_sql"] and structured_data:
                rows = structured_data.get("rows", [])
                if rows and len(rows) > 0:
                    chart_decision = "generate_chart"
                    logger.info(f"SQL Query Node - Chart decision: generate_chart for {query_path} path with {len(rows)} rows")
                else:
                    logger.info(f"SQL Query Node - Chart decision: skip_chart - no data rows")
            else:
                logger.info(f"SQL Query Node - Chart decision: skip_chart for {query_path} path")
            
            # Prepare return state with all integrated results
            return_state = {
                **state,
                "structured_data": structured_data,
                "sql_answer": sql_answer,
                "executed_sql": executed_sql,
                "merged_context": merged_context,
                "data_with_metadata": data_with_metadata,
                "chart_decision": chart_decision,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "sql_query": {
                        "status": "completed",
                        "timestamp": time.time(),
                        "query_path": query_path,
                        "rag_guided": bool(rag_result),
                        "data_summary": {
                            "row_count": len(structured_data.get("rows", [])),
                            "executed_sql": executed_sql,
                            "has_answer": bool(sql_answer)
                        },
                        "result_merge": {
                            "status": "completed",
                            "timestamp": time.time(),
                            "merged_context_length": len(merged_context) if merged_context else 0,
                            "data_rows": len(structured_data.get('rows', [])),
                            "metadata_used": bool(rag_result)
                        },
                        "chart_decision": {
                            "status": "completed",
                            "timestamp": time.time(),
                            "decision": chart_decision,
                            "reason": f"{query_path} path with {len(structured_data.get('rows', []))} rows"
                        }
                    }
                }
            }
            
            return return_state
        else:
            error_msg = result.get("error", "SQL query execution failed")
            logger.error(f"SQL query failed: {error_msg}")
            
            return {
                **state,
                "error": error_msg,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "sql_query": {
                        "status": "error",
                        "timestamp": time.time(),
                        "error": error_msg
                    }
                }
            }
    except Exception as e:
        error_msg = f"Unexpected error in SQL query node: {str(e)}"
        logger.exception(error_msg)
        return {
            **state,
            "error": error_msg,
            "node_outputs": {
                **state.get("node_outputs", {}),
                "sql_query": {
                    "status": "error",
                    "timestamp": time.time(),
                    "error": error_msg
                }
            }
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

async def sql_chart_node(state: GraphState) -> GraphState:
    """SQL chart node: execute SQL query for chart data"""
    try:
        user_input = state["user_input"]
        datasource = state["datasource"]
        
        # Force SQL chart branch to use built-in DEFAULT datasource (ID=1)
        if datasource.get("type") != "default":
            try:
                from ..database.db_operations import get_datasource
                builtin_ds = await get_datasource(1)
                if builtin_ds:
                    datasource = builtin_ds
                    logger.info("SQL chart branch: switched to built-in DEFAULT datasource (ID=1)")
            except Exception as _e:
                logger.warning(f"SQL chart branch: failed to switch to DEFAULT datasource: {_e}")

        # Call existing SQL query logic with chart context
        result = await get_answer_from_sqltable_datasource(user_input, datasource)
        
        if result["success"]:
            structured_data = result["data"]
            
            # Ensure we have the required data for charting
            if not structured_data.get("rows"):
                return {
                    **state,
                    "error": "No data returned for chart generation",
                    "node_outputs": {
                        **state.get("node_outputs", {}),
                        "sql_chart": {
                            "status": "error",
                            "timestamp": time.time(),
                            "error": "No data available for charting"
                        }
                    }
                }
            
            logger.info(f"SQL chart data query successful, data rows: {len(structured_data.get('rows', []))}")
            
            # Update state with chart data
            return {
                **state,
                "structured_data": structured_data,
                "answer": result["answer"],
                "query_type": state.get("query_type"),  # Preserve query_type
                "sql_task_type": state.get("sql_task_type"),  # Preserve sql_task_type
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "sql_chart": {
                        "status": "completed",
                        "timestamp": time.time(),
                        "data_summary": {
                            "row_count": len(structured_data.get("rows", [])),
                            "executed_sql": structured_data.get("executed_sql"),
                            "queried_table": structured_data.get("queried_table")
                        }
                    }
                }
            }
        else:
            error_msg = result.get("error", "SQL chart data query failed")
            logger.error(f"SQL chart query failed: {error_msg}")
            return {
                **state,
                "error": error_msg,
                "query_type": state.get("query_type"),  # Preserve query_type
                "sql_task_type": state.get("sql_task_type"),  # Preserve sql_task_type
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "sql_chart": {
                        "status": "error",
                        "timestamp": time.time(),
                        "error": error_msg
                    }
                }
            }
    except Exception as e:
        error_msg = f"SQL chart node error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            **state,
            "error": error_msg,
            "query_type": state.get("query_type"),  # Preserve query_type
            "sql_task_type": state.get("sql_task_type"),  # Preserve sql_task_type
            "node_outputs": {
                **state.get("node_outputs", {}),
                "sql_chart": {
                    "status": "error",
                    "timestamp": time.time(),
                    "error": error_msg
                }
            }
        }

def chart_config_node(state: GraphState) -> GraphState:
    """Chart configuration node: generate chart configuration"""
    try:
        structured_data = state.get("structured_data", {})
        user_input = state["user_input"]
        
        # Generate chart configuration based on data and user requirements
        chart_config = generate_chart_config(structured_data, user_input)
        
        # Pass structured_data to next node for chart rendering
        return {
            **state, 
            "chart_config": chart_config,
            "structured_data": structured_data,  # Ensure structured_data is passed through
            "query_type": state.get("query_type"),  # Preserve query_type
            "sql_task_type": state.get("sql_task_type")  # Preserve sql_task_type
        }
    except Exception as e:
        logger.error(f"Chart config node error: {e}")
        return {
            **state, 
            "error": str(e),
            "query_type": state.get("query_type"),  # Preserve query_type
            "sql_task_type": state.get("sql_task_type")  # Preserve sql_task_type
        }

async def rag_query_node(state: GraphState) -> GraphState:
    """Enhanced RAG query node: supports both full retrieval and metadata-focused retrieval"""
    try:
        user_input = state["user_input"]
        datasource = state["datasource"]
        query_path = state.get("query_path", "rag_only")
        
        # Guards: avoid duplicate RAG execution in the same run
        if state.get("rag_executed"):
            logger.info("RAG query skipped: rag_executed flag present (preventing duplicate execution)")
            return {**state}
        
        logger.info(f"RAG Query Node - Path: {query_path}, Query: {user_input}")
        
        # Determine retrieval strategy based on query path
        if query_path == "rag_sql":
            # Metadata-focused retrieval for hybrid path
            logger.info("RAG Query Node - Using metadata-focused retrieval for hybrid path")
            result = await _perform_metadata_rag_query(user_input, datasource)
        else:
            # Full retrieval for pure RAG path
            logger.info("RAG Query Node - Using full retrieval for pure RAG path")
            result = await perform_rag_query(user_input, datasource)
        
        if result["success"]:
            rag_result = result["answer"]
            rag_sources = result.get("sources", [])
            rag_confidence = result.get("confidence", 0.8)
            
            # For rag_only path, set answer directly
            if query_path == "rag_only":
                return {
                    **state,
                    "answer": rag_result,
                    "rag_result": rag_result,
                    "rag_sources": rag_sources,
                    "rag_confidence": rag_confidence,
                    "rag_executed": True,
                    "node_outputs": {
                        **state.get("node_outputs", {}),
                        "rag_query": {
                            "status": "completed",
                            "timestamp": time.time(),
                            "query_path": query_path,
                            "sources": rag_sources,
                            "confidence": rag_confidence,
                            "data": result.get("data", {})
                        }
                    }
                }
            else:
                # For rag_sql path, store result for later merging
                return {
                    **state,
                    "rag_result": rag_result,
                    "rag_sources": rag_sources,
                    "rag_confidence": rag_confidence,
                    "rag_executed": True,
                    "node_outputs": {
                        **state.get("node_outputs", {}),
                        "rag_query": {
                            "status": "completed",
                            "timestamp": time.time(),
                            "query_path": query_path,
                            "sources": rag_sources,
                            "confidence": rag_confidence,
                            "data": result.get("data", {})
                        }
                    }
                }
        else:
            error_msg = result.get("error", "RAG query failed")
            logger.error(f"RAG query failed: {error_msg}")
            return {
                **state, 
                "rag_executed": True, 
                "error": error_msg,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "rag_query": {
                        "status": "error",
                        "timestamp": time.time(),
                        "error": error_msg
                    }
                }
            }
    except Exception as e:
        logger.error(f"RAG query node error: {e}")
        return {
            **state, 
            "error": str(e),
            "node_outputs": {
                **state.get("node_outputs", {}),
                "rag_query": {
                    "status": "error",
                    "timestamp": time.time(),
                    "error": str(e)
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

# Result Merge Node for combining RAG + SQL results
def result_merge_node(state: GraphState) -> GraphState:
    """Result Merge Node: combine RAG metadata and SQL data results"""
    try:
        rag_result = state.get("rag_result")
        structured_data = state.get("structured_data")
        user_input = state["user_input"]
        
        # Handle case where RAG failed but SQL succeeded
        if not rag_result and structured_data:
            logger.warning("RAG result missing, proceeding with SQL data only")
            merged_context = f"""
            [Data Query Results]
            Query: {user_input}
            SQL: {structured_data.get('executed_sql', 'N/A')}
            Data: {structured_data.get('rows', [])}
            
            Note: No metadata context available, using direct data query results.
            """
            
            data_with_metadata = {
                "metadata_context": "No metadata available",
                "query_context": user_input,
                "sql_query": structured_data.get('executed_sql', ''),
                "data_rows": structured_data.get('rows', []),
                "data_columns": structured_data.get('columns', []),
                "row_count": len(structured_data.get('rows', [])),
                "merged_at": time.time(),
                "rag_failed": True
            }
            
            return {
                **state,
                "merged_context": merged_context,
                "data_with_metadata": data_with_metadata,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "result_merge": {
                        "status": "completed",
                        "timestamp": time.time(),
                        "rag_available": False,
                        "sql_available": True,
                        "merged_successfully": True
                    }
                }
            }
        
        # Handle case where both RAG and SQL are missing
        if not rag_result and not structured_data:
            error_msg = "Missing both RAG result and structured data for merging"
            logger.error(error_msg)
            return {
                **state,
                "error": error_msg,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "result_merge": {
                        "status": "error",
                        "timestamp": time.time(),
                        "error": error_msg
                    }
                }
            }
        
        # Normal case: both RAG and SQL available
        logger.info("Result Merge Node - Combining RAG metadata with SQL data")
        
        # Create merged context
        merged_context = f"""
        [Metadata Context]
        {rag_result}
        
        [Data Query Results]
        Query: {user_input}
        SQL: {structured_data.get('executed_sql', 'N/A') if structured_data else 'N/A'}
        Data: {structured_data.get('rows', []) if structured_data else []}
        
        The metadata above explains the meaning and context of the data below.
        """
        
        # Create data with metadata annotations
        data_with_metadata = {
            "metadata_context": rag_result,
            "query_context": user_input,
            "sql_query": structured_data.get('executed_sql', '') if structured_data else '',
            "data_rows": structured_data.get('rows', []) if structured_data else [],
            "data_columns": structured_data.get('columns', []) if structured_data else [],
            "row_count": len(structured_data.get('rows', [])) if structured_data else 0,
            "merged_at": time.time()
        }
        
        logger.info(f"Result Merge completed - Rows: {len(structured_data.get('rows', [])) if structured_data else 0}")
        
        return {
            **state,
            "merged_context": merged_context,
            "data_with_metadata": data_with_metadata,
            "node_outputs": {
                **state.get("node_outputs", {}),
                "result_merge": {
                    "status": "completed",
                    "timestamp": time.time(),
                    "merged_context_length": len(merged_context),
                    "data_rows": len(structured_data.get('rows', [])),
                    "metadata_used": True
                }
            }
        }
        
    except Exception as e:
        error_msg = f"Error in Result Merge Node: {str(e)}"
        logger.error(error_msg)
        return {
            **state,
            "error": error_msg,
            "node_outputs": {
                **state.get("node_outputs", {}),
                "result_merge": {
                    "status": "error",
                    "timestamp": time.time(),
                    "error": error_msg
                }
            }
        }

def chart_rendering_node(state: GraphState) -> GraphState:
    """Chart rendering node: render interactive chart configuration"""
    try:
        chart_config = state.get("chart_config")
        structured_data = state.get("structured_data")
        
        if not chart_config:
            return {**state, "error": "Missing chart configuration"}
        
        # Require structured data for chart generation
        if not structured_data:
            return {**state, "error": "Missing structured data for chart"}
        
        # Import AntV chart service
        from ..mcp.antv_chart_service import AntVChartService
        
        # Process structured data for chart generation
        chart_type = chart_config.get("type", "line")
        chart_title = chart_config.get("title", "Data Visualization")
        
        # Convert structured data to chart data format
        chart_data = []
        
        # Handle structured_data format: {'rows': [...], 'columns': [...], ...}
        if isinstance(structured_data, dict) and "rows" in structured_data:
            rows = structured_data.get("rows", [])
            if rows and len(rows) > 0:
                # Convert rows to chart data format
                for row in rows:
                    if isinstance(row, dict):
                        # Handle dict format like {'col_0': '2025-01', 'col_1': 42, 'col_2': 88293.43}
                        row_keys = list(row.keys())
                        if len(row_keys) >= 2:
                            # Use first column as x-axis (time/date), last column as y-axis (value)
                            x_value = row[row_keys[0]]  # e.g., '2025-01'
                            y_value = row[row_keys[-1]]  # e.g., 88293.43
                            chart_data.append({
                                "x": str(x_value),
                                "y": float(y_value) if isinstance(y_value, (int, float)) else 0
                            })
                    else:
                        # Handle list format
                        if len(row) >= 2:
                            chart_data.append({
                                "x": str(row[0]),
                                "y": float(row[-1]) if isinstance(row[-1], (int, float)) else 0
                            })
        elif isinstance(structured_data, list) and len(structured_data) > 0:
            # Handle direct list format
            if isinstance(structured_data[0], dict):
                chart_data = structured_data
            else:
                # Convert simple list to chart data
                for i, value in enumerate(structured_data):
                    chart_data.append({"x": i, "y": value})
        else:
            # No structured data available
            logger.warning("No structured data available for chart generation")
            return {**state, "error": "No structured data available for chart generation"}
        
        # Generate interactive chart configuration using PyEcharts
        chart_service = AntVChartService()
        interactive_chart_config = chart_service.render_chart(
            chart_type=chart_type,
            data=chart_data,
            config={
                "title": chart_title,
                "xField": chart_config.get("xField", "x"),
                "yField": chart_config.get("yField", "y"),
                "seriesField": chart_config.get("seriesField"),
                "categoryField": chart_config.get("categoryField", "category"),
                "valueField": chart_config.get("valueField", "value")
            }
        )
        
        logger.info(f"Generated interactive chart config for {chart_type} chart")
        
        return {
            **state, 
            "chart_config": interactive_chart_config,
            "chart_type": chart_type,
            "chart_data": chart_data
        }
    except Exception as e:
        logger.error(f"Chart rendering error: {e}")
        return {**state, "error": str(e)}

async def llm_processing_node(state: GraphState) -> GraphState:
    """Enhanced LLM Processing Node: handle outputs from 3 different query paths"""
    try:
        user_input = state["user_input"]
        query_path = state.get("query_path", "rag_only")
        execution_id = state.get("execution_id")
        
        logger.info(f"LLM Processing Node - Path: {query_path}")
        
        # Handle different paths
        if query_path == "rag_only":
            return await _process_rag_only_output(state, execution_id)
        elif query_path == "sql_only":
            return await _process_sql_only_output(state, execution_id)
        elif query_path == "rag_sql":
            return await _process_rag_sql_output(state, execution_id)
        else:
            logger.warning(f"Unknown query path: {query_path}, defaulting to rag_only")
            return await _process_rag_only_output(state, execution_id)
            
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

async def _process_rag_only_output(state: GraphState, execution_id: str) -> GraphState:
    """Process RAG-only path output"""
    rag_result = state.get("rag_result", "")
    
    if not rag_result:
        error_msg = "No RAG result available for processing"
        logger.error(error_msg)
        return {**state, "error": error_msg}
    
    logger.info("LLM Processing - Processing RAG-only output")
    
    # Stream the RAG result
    await _stream_text_as_tokens(rag_result, execution_id, "llm_processing_node")
    
    final_result = {
        "text": rag_result,
        "data": None,
        "chart": None,
        "path": "rag_only"
    }
    
    return {
        **state,
        "answer": rag_result,
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
    sql_answer = state.get("sql_answer", "")
    
    if not structured_data:
        error_msg = "No structured data available for processing"
        logger.error(error_msg)
        return {**state, "error": error_msg}
    
    logger.info("LLM Processing - Processing SQL-only output")
    
    # Generate intelligent response from SQL data
    rows = structured_data.get("rows", [])
    columns = structured_data.get("columns", [])
    executed_sql = structured_data.get("executed_sql", "")
    
    if rows:
        # Generate structured answer
        structured_answer = _generate_intelligent_sql_response(
            state["user_input"], rows, columns, executed_sql
        )
        
        # Add chart context if available
        if chart_config:
            structured_answer += f"\n\nI've also generated a visualization chart to help you better understand the data."
        
        # Stream the response
        await _stream_text_as_tokens(structured_answer, execution_id, "llm_processing_node")
        final_answer = structured_answer
    else:
        final_answer = f"No data was found matching your query '{state['user_input']}'. Please try a different question or check if the data exists."
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
    merged_context = state.get("merged_context")
    structured_data = state.get("structured_data")
    chart_config = state.get("chart_config")
    
    # Handle case where RAG failed but SQL succeeded
    if not merged_context and structured_data:
        logger.warning("RAG context missing, processing SQL-only output in hybrid path")
        return await _process_sql_only_output(state, execution_id)
    
    # Handle case where SQL failed but RAG succeeded
    if merged_context and not structured_data:
        logger.warning("SQL data missing, processing RAG-only output in hybrid path")
        return await _process_rag_only_output(state, execution_id)
    
    # Handle case where both are missing
    if not merged_context and not structured_data:
        error_msg = "Missing both merged context and structured data for hybrid processing"
        logger.error(error_msg)
        return {**state, "error": error_msg}
    
    logger.info("LLM Processing - Processing RAG+SQL hybrid output")
    
    # Generate comprehensive response combining metadata and data
    comprehensive_prompt = f"""
    User Query: "{state['user_input']}"
    
    Context: {merged_context}
    
    Please provide a comprehensive response that:
    1. Explains the metadata context and what the data means
    2. Analyzes the actual data results
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
        "metadata": merged_context,
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
                "has_metadata": True
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
        
        Please analyze the user's chart requirements and return chart configuration suggestions in JSON format:
        {{
            "chart_type": "line|bar|pie",
            "title": "Chart title",
            "x_axis_label": "X-axis label",
            "y_axis_label": "Y-axis label",
            "data_field_for_labels": "Data field name or index for labels",
            "data_field_for_values": "Data field name or index for values",
            "aggregation_method": "none|sum|average|count",
            "time_grouping": "none|week|month|quarter|year",
            "is_time_series": true|false
        }}
        
        Analysis requirements:
        1. Determine the most suitable chart type based on user query:
           - Use "pie" for: proportion, percentage, distribution, breakdown, "each product", "by category"
           - Use "line" for: trend, over time, monthly, weekly, yearly, quarterly
           - Use "bar" for: comparison, ranking, top/bottom items
        2. Generate meaningful titles and axis labels
        3. Identify which fields in the data should be used for labels and values
        4. **CRITICAL**: Analyze if this is a time series query by looking for keywords:
           - "trend", "over time", "monthly", "weekly", "yearly", "quarterly"
           - "sales trend", "time series", "by month", "by year", "by quarter"
           - "2025", specific years, date ranges
           - If ANY time-related keywords found, set "is_time_series": true and appropriate "time_grouping"
        5. Pay attention to time units mentioned in user query:
           - If user mentions "week" or "weekly": set time_grouping to "week"
           - If user mentions "month" or "monthly": set time_grouping to "month"  
           - If user mentions "year" or "yearly": set time_grouping to "year"
           - If user mentions "quarter" or "quarterly": set time_grouping to "quarter"
           - If user mentions "trend" without specific time unit, default to "month"
        6. Generate appropriate x_axis_label based on time grouping:
           - For week grouping: use "Week"
           - For month grouping: use "Month"
           - For year grouping: use "Year"
           - For quarter grouping: use "Quarter"
           - For non-time series: use appropriate category label
        7. For different chart types:
           - For pie charts: Set data_field_for_labels to "0" (category/product names), data_field_for_values to "1" (amounts/quantities)
           - For time series data: Always use "line" chart type for trends, set data_field_for_labels to "0" (time), data_field_for_values to "1" (values)
           - For bar charts: Set data_field_for_labels to "0" (categories), data_field_for_values to "1" (values)
        8. Only return JSON, no other explanation
        """
        
        # For chart推理使用 reasoning 模型
        try:
            from ..models.llm_factory import get_reasoning_llm
            reasoning_llm = get_reasoning_llm()
            response = reasoning_llm.invoke(chart_analysis_prompt)
        except Exception:
            # 兜底使用默认chat模型
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
            
            # Extract JSON part
            json_match = re.search(r'\{.*\}', analysis_text, re.DOTALL)
            if json_match:
                chart_analysis = json.loads(json_match.group())
            else:
                logger.warning("No JSON found in LLM response, using fallback")
                return generate_fallback_chart_config(data, user_input)
                
        except (json.JSONDecodeError, AttributeError) as e:
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
        
        # Intelligent Y-axis label detection
        y_axis_label = chart_analysis.get("y_axis_label", "Value")
        if not y_axis_label or y_axis_label == "Value":
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
                        "text": chart_analysis.get("title", "Data Chart"),
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
                        summary_parts.append("Contains fields: ID, Product ID, Product Name, Category, Sales Volume, Unit Price, Total Amount, Date")
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
            
            # Simple processing: sort by value descending and take top 10
            sorted_rows = sorted(rows, key=lambda x: float(x.get("value", 0)), reverse=True)
            processed_rows = sorted_rows[:10]  # Limit to top 10
            
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
        if is_time_series or time_grouping != "none" or any(keyword in user_input.lower() for keyword in ['trend', 'monthly', 'yearly', 'over time']):
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
            # Non-time series: use original logic
            label_field = chart_analysis.get("data_field_for_labels", "2")  # Default product name  
            value_field = chart_analysis.get("data_field_for_values", "6")  # Default total amount
            try:
                label_idx = int(label_field) if str(label_field).isdigit() else 2
                value_idx = int(value_field) if str(value_field).isdigit() else 6
                # Ensure indices are within bounds
                if num_cols > 0:
                    if label_idx >= num_cols: label_idx = min(2, num_cols - 1)
                    if value_idx >= num_cols: value_idx = min(num_cols - 1, max(1, num_cols - 1))
            except (ValueError, TypeError):
                label_idx, value_idx = min(2, num_cols - 1), min(num_cols - 1, max(1, num_cols - 1))
        
        logger.info(f"Using label_idx: {label_idx}, value_idx: {value_idx}")
        logger.info(f"Sample row: {sample_row}")
        logger.info(f"Is time series: {is_time_series}, Time grouping: {time_grouping}")
        
        if time_grouping != "none" and len(rows[0]) > 7:
            # Time series data processing
            time_data = {}
            
            for row in rows:
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
                        
                        if date_str and len(date_str) >= 7:
                            if time_grouping == "month":
                                # Extract year-month, support different date formats
                                if '-' in date_str:
                                    time_key = date_str[:7]  # YYYY-MM
                                else:
                                    # Handle other formats
                                    time_key = date_str[:7] if len(date_str) >= 7 else date_str
                            elif time_grouping == "week":
                                # Extract year-week, format as YYYY-WW
                                if '-' in date_str and len(date_str) >= 10:
                                    # Convert date to week format using strftime logic
                                    try:
                                        from datetime import datetime
                                        date_obj = datetime.strptime(date_str[:10], '%Y-%m-%d')
                                        year = date_obj.isocalendar()[0]
                                        week = date_obj.isocalendar()[1]
                                        time_key = f"{year}-W{week:02d}"
                                    except ValueError:
                                        # Fallback: use first 7 characters
                                        time_key = date_str[:7]
                                else:
                                    time_key = date_str[:7] if len(date_str) >= 7 else date_str
                            elif time_grouping == "quarter":
                                year = date_str[:4]
                                month_str = date_str[5:7] if len(date_str) > 6 else "01"
                                try:
                                    month = int(month_str)
                                    quarter = (month - 1) // 3 + 1
                                    time_key = f"{year}-Q{quarter}"
                                except ValueError:
                                    time_key = f"{year}-Q1"
                            elif time_grouping == "year":
                                time_key = date_str[:4]  # YYYY
                            else:
                                time_key = date_str[:7]
                            
                            if aggregation_method == "sum":
                                time_data[time_key] = time_data.get(time_key, 0) + value
                            elif aggregation_method == "average":
                                if time_key in time_data:
                                    time_data[time_key] = (time_data[time_key] + value) / 2
                                else:
                                    time_data[time_key] = value
                            elif aggregation_method == "count":
                                time_data[time_key] = time_data.get(time_key, 0) + 1
                            else:
                                time_data[time_key] = value
                                
                    except (ValueError, TypeError, IndexError) as e:
                        logger.warning(f"Error processing row data: {e}")
                        continue
            
            # Convert time data to chart format with proper time-based sorting
            def sort_time_key(key):
                """Custom time key sorting function"""
                try:
                    if time_grouping == "year":
                        return int(key)
                    elif time_grouping == "month":
                        year, month = key.split('-')
                        return int(year) * 100 + int(month)
                    elif time_grouping == "week":
                        year, week_str = key.split('-W')
                        return int(year) * 100 + int(week_str)
                    elif time_grouping == "quarter":
                        year, quarter = key.split('-Q')
                        return int(year) * 10 + int(quarter)
                    else:
                        return key
                except:
                    return key
            
            for time_key in sorted(time_data.keys(), key=sort_time_key):
                labels.append(format_time_label(time_key, time_grouping))
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
                        label = str(row[0]) if row[0] else f"Item{len(labels)+1}"
                        # Handle TEXT type numeric fields
                        value_str = str(row[1]) if row[1] else "0"
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
                        
                        if aggregation_method == "sum":
                            data_dict[label] = data_dict.get(label, 0) + value
                        elif aggregation_method == "average":
                            if label in data_dict:
                                data_dict[label] = (data_dict[label] + value) / 2
                            else:
                                data_dict[label] = value
                        elif aggregation_method == "count":
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
                    # Sort by value in descending order (original logic)
                    sorted_items = sorted(data_dict.items(), key=lambda x: x[1], reverse=True)[:10]
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
    """Create the new hybrid workflow with 3 query paths"""
    workflow = StateGraph(GraphState)
    
    # Add nodes to the graph
    workflow.add_node("start_node", lambda state: state)  # Start node just passes through
    workflow.add_node("intent_analysis_node", intent_analysis_node)  # New intent analysis node
    workflow.add_node("rag_query_node", rag_query_node)  # Enhanced RAG query node
    workflow.add_node("sql_query_node", sql_query_node)  # Enhanced SQL query node with integrated result merge and chart decision
    workflow.add_node("chart_process_node", chart_process_node)  # Enhanced chart process node
    workflow.add_node("llm_processing_node", llm_processing_node)  # Enhanced LLM processing node
    workflow.add_node("interrupt_node", interrupt_node)  # HITL interrupt node
    workflow.add_node("end_node", lambda state: {"success": True})

    # Set entry point
    workflow.set_entry_point("start_node")
    
    # Connect start to intent analysis
    workflow.add_edge("start_node", "intent_analysis_node")

    # Intent analysis routes to different paths
    workflow.add_conditional_edges(
        "intent_analysis_node",
        lambda state: state["query_path"],
        {
            "rag_only": "rag_query_node",
            "sql_only": "sql_query_node", 
            "rag_sql": "rag_query_node"  # Start with RAG for hybrid path
        }
    )

    # RAG query node routes based on path
    workflow.add_conditional_edges(
        "rag_query_node",
        lambda state: state["query_path"],
        {
            "rag_only": "llm_processing_node",  # Pure RAG goes directly to LLM
            "rag_sql": "sql_query_node"  # Hybrid continues to SQL
        }
    )

    # SQL query node routes based on chart decision (integrated)
    workflow.add_conditional_edges(
        "sql_query_node",
        lambda state: state.get("chart_decision", "skip_chart"),
        {
            "generate_chart": "chart_process_node",  # Generate chart if needed
            "skip_chart": "llm_processing_node"  # Skip chart, go to LLM processing
        }
    )

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
def chart_process_node(state: GraphState) -> GraphState:
    """Enhanced Chart Process Node: generate chart config then render chart"""
    try:
        structured_data = state.get("structured_data")
        user_input = state["user_input"]
        query_path = state.get("query_path", "sql_only")
        
        if not structured_data:
            logger.warning("Chart Process Node - No structured data available")
            return {**state, "error": "No structured data available for chart generation"}
        
        logger.info(f"Chart Process Node - Processing chart for {query_path} path")
        
        # Step 1: Generate chart configuration
        chart_config_result = chart_config_node(state)
        if chart_config_result.get("error"):
            logger.warning(f"Chart config failed: {chart_config_result.get('error')}")
            # Don't fail the entire process, just skip chart generation
            return {
                **state,
                "chart_config": None,
                "chart_data": None,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "chart_process": {
                        "status": "skipped",
                        "timestamp": time.time(),
                        "reason": "Chart config failed",
                        "error": chart_config_result.get("error")
                    }
                }
            }
        
        # Step 2: Render chart
        chart_render_result = chart_rendering_node(chart_config_result)
        if chart_render_result.get("error"):
            logger.warning(f"Chart rendering failed: {chart_render_result.get('error')}")
            # Don't fail the entire process, just skip chart generation
            return {
                **chart_config_result,
                "chart_config": None,
                "chart_data": None,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "chart_process": {
                        "status": "skipped",
                        "timestamp": time.time(),
                        "reason": "Chart rendering failed",
                        "error": chart_render_result.get("error")
                    }
                }
            }
        
        logger.info("Chart Process Node - Chart generation completed successfully")
        
        return {
            **chart_render_result,
            "node_outputs": {
                **state.get("node_outputs", {}),
                "chart_process": {
                    "status": "completed",
                    "timestamp": time.time(),
                    "chart_type": chart_render_result.get("chart_type"),
                    "data_rows": len(structured_data.get("rows", []))
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Chart process node error: {e}")
        return {
            **state, 
            "error": str(e),
            "node_outputs": {
                **state.get("node_outputs", {}),
                "chart_process": {
                    "status": "error",
                    "timestamp": time.time(),
                    "error": str(e)
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

            elif paused_node == "sql_query_node":
                # Continue based on query path
                if query_path == "sql_only":
                    # Pure SQL path: go to chart decision
                    state = chart_decision_node(state)
                    await _emit(state)
                    
                    # Check chart decision
                    chart_decision = state.get("node_outputs", {}).get("chart_decision", {}).get("decision", "skip_chart")
                    if chart_decision == "generate_chart":
                        state = chart_process_node(state)
                await _emit(state)

                state = await llm_processing_node(state)
                await _emit(state)
            elif query_path == "rag_sql":
                    # Hybrid path: go to result merge
                    state = result_merge_node(state)
                    await _emit(state)

                    # Then chart decision
                    state = chart_decision_node(state)
                    await _emit(state)
                    
                    # Check chart decision
                    chart_decision = state.get("node_outputs", {}).get("chart_decision", {}).get("decision", "skip_chart")
                    if chart_decision == "generate_chart":
                        state = chart_process_node(state)
                        await _emit(state)
                    
                    state = await llm_processing_node(state)
                    await _emit(state)

            elif paused_node == "rag_query_node":
                # Continue based on query path
                if query_path == "rag_only":
                    # Pure RAG path: go directly to LLM processing
                    state = await llm_processing_node(state)
                    await _emit(state)
                elif query_path == "rag_sql":
                    # Hybrid path: go to SQL query
                    state = await sql_query_node(state)
                    await _emit(state)
                    
                    # Then result merge
                    state = result_merge_node(state)
                    await _emit(state)
                    
                    # Then chart decision
                    state = chart_decision_node(state)
                    await _emit(state)
                    
                    # Check chart decision
                    chart_decision = state.get("node_outputs", {}).get("chart_decision", {}).get("decision", "skip_chart")
                    if chart_decision == "generate_chart":
                        state = chart_process_node(state)
                        await _emit(state)
                    
                    state = await llm_processing_node(state)
                    await _emit(state)

            elif paused_node == "result_merge_node":
                # Continue from result merge to chart decision
                state = chart_decision_node(state)
                await _emit(state)
                
                # Check chart decision
                chart_decision = state.get("node_outputs", {}).get("chart_decision", {}).get("decision", "skip_chart")
                if chart_decision == "generate_chart":
                    state = chart_process_node(state)
                    await _emit(state)
                
                state = await llm_processing_node(state)
                await _emit(state)

            elif paused_node == "chart_decision_node":
                # Continue from chart decision
                chart_decision = state.get("node_outputs", {}).get("chart_decision", {}).get("decision", "skip_chart")
                if chart_decision == "generate_chart":
                    state = chart_process_node(state)
                    await _emit(state)
                
                    state = await llm_processing_node(state)
                    await _emit(state)

            elif paused_node == "intent_analysis_node":
                # Continue from intent analysis based on determined path
                query_path = state.get("query_path", "rag_only")
                
                if query_path == "rag_only":
                    state = await rag_query_node(state)
                    await _emit(state)
                    state = await llm_processing_node(state)
                    await _emit(state)
                elif query_path == "sql_only":
                    state = await sql_query_node(state)
                    await _emit(state)
                    state = chart_decision_node(state)
                    await _emit(state)
                    
                    chart_decision = state.get("node_outputs", {}).get("chart_decision", {}).get("decision", "skip_chart")
                    if chart_decision == "generate_chart":
                        state = chart_process_node(state)
                        await _emit(state)
                    
                    state = await llm_processing_node(state)
                    await _emit(state)
                elif query_path == "rag_sql":
                    state = await rag_query_node(state)
                    await _emit(state)
                    state = await sql_query_node(state)
                    await _emit(state)
                    state = result_merge_node(state)
                    await _emit(state)
                    state = chart_decision_node(state)
                    await _emit(state)
                    
                    chart_decision = state.get("node_outputs", {}).get("chart_decision", {}).get("decision", "skip_chart")
                    if chart_decision == "generate_chart":
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
            "query_path": "",  # Will be set by intent_analysis_node
            "need_chart": False,  # Will be set by intent_analysis_node
            "analysis_reasoning": "",
            "detected_keywords": [],
            "query_type": None,  # Legacy field
            "sql_task_type": None,  # Legacy field
            "rag_result": None,
            "rag_sources": None,
            "rag_confidence": None,
            "rag_executed": False,
        "structured_data": None,
            "sql_answer": None,
            "executed_sql": None,
            "merged_context": None,
            "data_with_metadata": None,
        "chart_config": None,
            "chart_data": None,
            "chart_type": None,
        "chart_image": None,
        "answer": "",
            "final_result": None,
        "quality_score": 10,
        "retry_count": 0,
            "error": None,
            "hitl_status": None,
            "hitl_node": None,
            "hitl_reason": None,
            "hitl_parameters": None,
            "hitl_timestamp": None,
            "node_outputs": {}
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
        try:
            async for event in app.astream_events(initial_state, config, version="v1"):
                kind = event.get("event")
                node_name = event.get("name", "")

                if kind == "on_chain_start":
                    logger.info(f"Node started: {node_name}")
                    await emit_event("node_started", node_id=node_name)

                elif kind == "on_chain_end":
                    logger.info(f"Node completed: {node_name}")
                    data = event.get("data")
                    # Accumulate any state-like data emitted by nodes
                    if isinstance(data, dict):
                        for key, value in data.items():
                            accumulated_state[key] = value
                    await emit_event("node_completed", node_id=node_name, data=data)

                elif kind == "on_chain_error":
                    logger.error(f"Node error: {node_name} - {event.get('data')}")
                    await emit_event("node_error", node_id=node_name, error=str(event.get("data", "")))

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
    
    logger.info(f"�?[BACKEND-LG] set_execution_final_state completed successfully")
