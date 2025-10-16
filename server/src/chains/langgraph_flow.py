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
# GraphState definition
class GraphState(TypedDict):
    """Define graph state"""
    user_input: str
    query_type: str  # "sql" or "rag"
    sql_task_type: str  # "query" or "chart"
    structured_data: Optional[Dict[str, Any]]
    chart_config: Optional[Dict[str, Any]]
    chart_image: Optional[str]
    answer: str
    quality_score: int
    retry_count: int
    datasource: Dict[str, Any]
    error: Optional[str]
    execution_id: str  # For WebSocket routing and token streaming
    
    # HITL (Human-in-the-Loop) state fields
    hitl_status: Optional[str]  # "paused", "interrupted", "resumed", None
    hitl_node: Optional[str]  # Node where HITL action occurred
    hitl_reason: Optional[str]  # Reason for HITL action
    hitl_parameters: Optional[Dict[str, Any]]  # Parameters for adjustment
    hitl_timestamp: Optional[str]  # Timestamp of HITL action

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

def router_node(state: GraphState) -> GraphState:
    """Router node: determine whether to use SQL or RAG based on user input"""
    user_input = state["user_input"]
    
    if not llm:
        logger.warning("LLM not available, using fallback rule-based routing")
        # Fallback to simple rule-based routing
        sql_keywords = [
            "sales", "count", "sum", "average", "total", "report", "data", "table", 
            "chart", "graph", "visualization", "trend", "statistics", "analysis",
            "product", "inventory", "amount", "quantity", "value", "calculate",
            "show me", "how many", "how much", "what is the", "pie chart", "bar chart",
            "line chart", "proportion", "percentage", "distribution", "breakdown"
        ]
        
        if any(keyword in user_input.lower() for keyword in sql_keywords):
            query_type = "sql"
        else:
            query_type = "rag"
    else:
        # Use LLM for semantic understanding
        try:
            prompt = f"""
            Analyze the following user query and determine the most appropriate processing method:
            1. sql - Data analysis, statistics, calculations, reports, charts, visualizations (requires structured data from database)
               Examples: "show sales data", "generate pie chart", "sales proportion", "monthly trends", "product analysis"
            2. rag - Knowledge search, document questions, explanations, general information (requires document search)
               Examples: "what is machine learning", "explain the concept", "tell me about the company"
            
            User query: "{user_input}"
            
            Key indicators for SQL:
            - Chart/graph requests (pie chart, bar chart, line chart)
            - Data analysis (sales, products, trends, proportions)
            - Statistical calculations (sum, count, average)
            - Database queries (show me data, analyze results)
            
            Based on the query content, should this be processed with 'sql' or 'rag'?
            Only answer 'sql' or 'rag' (lowercase, no explanation needed).
            """
            
            response = llm.invoke(prompt)
            
            # Handle different response types
            if hasattr(response, 'content'):
                raw_response = response.content.strip().lower()
            elif isinstance(response, str):
                raw_response = response.strip().lower()
            else:
                raw_response = str(response).strip().lower()
            
            # Extract the first word/line (Bedrock may add explanations)
            # Try to extract just 'sql' or 'rag' from the response
            query_type = None
            
            # Check if response contains 'sql' or 'rag' in the first line
            first_line = raw_response.split('\n')[0].strip()
            
            # Try exact match on first line/word
            if first_line in ["sql", "rag"]:
                query_type = first_line
            # Try to find sql or rag in first line
            elif "sql" in first_line and "rag" not in first_line:
                query_type = "sql"
            elif "rag" in first_line and "sql" not in first_line:
                query_type = "rag"
            # Try to find in full response
            elif "rag" in raw_response and "sql" not in raw_response[:20]:  # Check first 20 chars
                query_type = "rag"
            elif "sql" in raw_response and "rag" not in raw_response[:20]:
                query_type = "sql"
            
            # Validate response
            if not query_type or query_type not in ["sql", "rag"]:
                logger.warning(f"Invalid LLM routing response: {raw_response[:200]}, defaulting to sql")
                query_type = "sql"
            else:
                logger.info(f"Router extracted '{query_type}' from response: {raw_response[:100]}")
                
        except Exception as e:
            logger.error(f"Error in LLM routing: {e}, falling back to rule-based")
            # Fallback to rule-based
            sql_keywords = [
                "sales", "count", "sum", "average", "total", "report", "data", "table", 
                "chart", "graph", "visualization", "trend", "statistics", "analysis",
                "product", "inventory", "amount", "quantity", "value", "calculate",
                "show me", "how many", "how much", "what is the"
            ]
            
            if any(keyword in user_input.lower() for keyword in sql_keywords):
                query_type = "sql"
            else:
                query_type = "rag"
    
    logger.info(f"Router decision result: {query_type} for input: {user_input}")
    
    return {**state, "query_type": query_type}

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
    """SQL query node: execute SQL query and return results"""
    try:
        user_input = state["user_input"]
        datasource = state.get("datasource")  # Get datasource from state
        
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
        
        # Call SQL query logic with improved error handling
        result = await get_query_from_sqltable_datasource(
            user_input, 
            datasource
        )
        
        if result["success"]:
            structured_data = result.get("data", {})
            executed_sql = result.get("executed_sql", "")
            
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
            
            # Strong intent-to-chart enforcement when data matches category-value schema
            chart_intent = state.get("sql_task_type") == "chart" or any(k in user_input.lower() for k in [
                "pie", "pie chart", "proportion", "percentage", "distribution", "breakdown", "饼图", "占比", "比例"
            ])
            if chart_intent and isinstance(structured_data, dict) and structured_data.get("rows"):
                rows = structured_data.get("rows", [])
                if rows and isinstance(rows[0], dict) and ("category" in rows[0] and "value" in rows[0]):
                    logger.info("Chart intent detected with compatible data; ensuring downstream chart path.")
                    state = {**state, "sql_task_type": "chart"}
            
            return {
                **state,
                "structured_data": structured_data,
                "answer": result["answer"],
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "sql_query": {
                        "status": "completed",
                        "timestamp": time.time(),
                        "data_summary": {
                            "row_count": len(structured_data.get("rows", [])),
                            "executed_sql": executed_sql,
                            "has_answer": bool(result.get("answer"))
                        }
                    }
                }
            }
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

async def sql_chart_node(state: GraphState) -> GraphState:
    """SQL chart node: execute SQL query for chart data"""
    try:
        user_input = state["user_input"]
        datasource = state["datasource"]
        
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
    """RAG query node"""
    try:
        user_input = state["user_input"]
        datasource = state["datasource"]
        # Guards: avoid duplicate RAG execution in the same run
        # 1) Upstream may have produced an answer
        if state.get("answer"):
            logger.info("RAG query skipped: answer already present in state (preventing duplicate execution)")
            return {**state}
        # 2) This node already executed before (e.g., re-entry in graph)
        if state.get("rag_executed"):
            logger.info("RAG query skipped: rag_executed flag present (preventing duplicate execution)")
            return {**state}
        
        # Call RAG query logic
        result = await perform_rag_query(user_input, datasource)
        
        if result["success"]:
            return {
                **state,
                "answer": result["answer"],
                "rag_executed": True,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "rag_query": {
                        "status": "completed",
                        "timestamp": time.time(),
                        "data": result.get("data", {})
                    }
                }
            }
        else:
            return {**state, "rag_executed": True, "error": result.get("error", "RAG query failed")}
    except Exception as e:
        logger.error(f"RAG query node error: {e}")
        return {**state, "error": str(e)}

# Sample data generation removed - system will use real data only

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
    """LLM processing node: process results with LLM for natural language response (with token streaming)"""
    try:
        user_input = state["user_input"]
        structured_data = state.get("structured_data")
        chart_image = state.get("chart_image")
        existing_answer = state.get("answer", "")
        error = state.get("error")
        execution_id = state.get("execution_id")
        
        # Debug logging
        logger.info(f"LLM Processing Node - Input: {user_input}")
        logger.info(f"LLM Processing Node - Has structured_data: {bool(structured_data)}")
        logger.info(f"LLM Processing Node - Has chart_image: {bool(chart_image)}")
        logger.info(f"LLM Processing Node - Existing answer: '{existing_answer}'")
        logger.info(f"LLM Processing Node - Error: {error}")
        
        if structured_data:
            logger.info(f"LLM Processing Node - Structured data keys: {list(structured_data.keys())}")
            rows = structured_data.get("rows", [])
            logger.info(f"LLM Processing Node - Number of rows: {len(rows)}")
            if rows:
                logger.info(f"LLM Processing Node - First row: {rows[0]}")
        
        # If there's an error, provide a helpful response (no streaming for errors)
        if error:
            final_answer = f"I encountered an issue while processing your request: {error}. Please try rephrasing your question or check if the data source is properly configured."
            logger.info(f"LLM Processing Node - Returning error response: {final_answer}")
            return {**state, "answer": final_answer}
        
        # If there's already an answer from RAG, stream it token by token for better UX
        if existing_answer and not structured_data and not chart_image:
            logger.info(f"LLM Processing Node - Streaming existing RAG answer: {existing_answer[:100]}...")
            await _stream_text_as_tokens(existing_answer, execution_id)
            return {**state, "answer": existing_answer}
        
        # For SQL results, generate a natural language response
        if structured_data:
            if chart_image:
                # For chart results, create a descriptive prompt and stream LLM response
                chart_prompt = f"""
                The user asked: "{user_input}"
                
                I've generated a visualization chart for this query. Please provide a brief, natural description
                of what the chart shows and what insights the user can gain from it.
                Keep the response concise (2-3 sentences) and friendly.
                """
                logger.info(f"LLM Processing Node - Streaming chart description via LLM")
                final_answer = await stream_llm_response(chart_prompt, execution_id, "llm_processing_node")
            else:
                # Generate intelligent text-based answer from structured data
                rows = structured_data.get("rows", [])
                columns = structured_data.get("columns", [])
                executed_sql = structured_data.get("executed_sql", "")
                
                logger.info(f"LLM Processing Node - Processing SQL results: rows={len(rows)}, columns={columns}")
                
                if rows:
                    logger.info("LLM Processing Node - Generating and streaming SQL response")
                    # Generate structured answer first
                    structured_answer = _generate_intelligent_sql_response(user_input, rows, columns, executed_sql)
                    # Stream it token by token for better UX
                    await _stream_text_as_tokens(structured_answer, execution_id)
                    final_answer = structured_answer
                    logger.info(f"LLM Processing Node - Streamed intelligent response: {final_answer[:200]}...")
                else:
                    final_answer = f"No data was found matching your query '{user_input}'. Please try a different question or check if the data exists."
                    logger.info(f"LLM Processing Node - No rows response: {final_answer}")
                    await _stream_text_as_tokens(final_answer, execution_id)
        else:
            final_answer = existing_answer or f"I've processed your query '{user_input}' but couldn't generate specific results. Please try rephrasing your question."
            logger.info(f"LLM Processing Node - Fallback response: {final_answer}")
            await _stream_text_as_tokens(final_answer, execution_id)
        
        logger.info(f"LLM Processing Node - Final answer: {final_answer[:200]}...")
        return {**state, "answer": final_answer}
    except Exception as e:
        logger.error(f"LLM processing error: {e}")
        import traceback
        logger.error(f"LLM processing traceback: {traceback.format_exc()}")
        return {**state, "error": f"LLM processing failed: {e}"}

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
                    
                    response_lines.append(f"�?{category}: {formatted_value}")
                
                # Add insights for average/price queries
                if 'average' in query_lower and 'price' in query_lower:
                    logger.info("Adding price insights")
                    highest = sorted_rows[0]
                    lowest = sorted_rows[-1]
                    response_lines.append(f"\nKey insights:")
                    response_lines.append(f"�?Highest average price: {highest['category']} (${highest['value']:.2f})")
                    response_lines.append(f"�?Lowest average price: {lowest['category']} (${lowest['value']:.2f})")
                    
                    price_diff = highest['value'] - lowest['value']
                    response_lines.append(f"�?Price range: ${price_diff:.2f}")
                
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
        chart_config = {
            "type": chart_analysis.get("chart_type", "bar"),
            "data": {
                "labels": [],
                "datasets": [{
                    "label": chart_analysis.get("y_axis_label", "Data"),
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
                            "text": chart_analysis.get("y_axis_label", "Value")
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
    """Extract chart data based on LLM analysis results"""
    try:
        labels = []
        values = []
        
        if not isinstance(data, dict) or "rows" not in data or not data["rows"]:
            logger.error("No valid data found in extract_chart_data_with_llm_guidance")
            return labels, values
        
        rows = data["rows"]
        aggregation_method = chart_analysis.get("aggregation_method", "none")
        time_grouping = chart_analysis.get("time_grouping", "none")
        is_time_series = chart_analysis.get("is_time_series", False)
        
        # Smart field detection based on data structure
        sample_row = rows[0] if rows else {}
        logger.info(f"Processing sample row: {sample_row}, type: {type(sample_row)}")
        
        # Handle dictionary format with category/value keys (from parsed string results)
        if isinstance(sample_row, dict) and "category" in sample_row and "value" in sample_row:
            logger.info(f"Processing {len(rows)} rows of category-value data")
            
            # Use LLM to intelligently analyze the data and user intent
            if llm:
                try:
                    # Prepare comprehensive data context for LLM
                    sample_data = rows[:5]  # Use first 5 rows as sample
                    sample_categories = [str(row.get("category", "")) for row in sample_data]
                    sample_values = [row.get("value", 0) for row in sample_data]
                    
                    # Let LLM freely analyze without constraints
                    analysis_prompt = f"""
                    You are an expert data analyst. Analyze the following user request and data to determine the best processing strategy.
                    
                    USER REQUEST: "{user_input}"
                    
                    DATA CONTEXT:
                    - Total records: {len(rows)}
                    - Sample categories: {sample_categories}
                    - Sample values: {sample_values}
                    - First few records: {sample_data}
                    
                    Based on your expertise, provide a comprehensive analysis plan in JSON format. You have complete freedom to design the response structure. Consider:
                    
                    1. What type of data is this? (time series, categorical, hierarchical, etc.)
                    2. What does the user want to achieve?
                    3. How should the data be filtered, sorted, and limited?
                    4. What would be the most meaningful way to present this data?
                    
                    Design your own JSON structure that best captures your analysis. Be creative and thorough.
                    
                    Return only valid JSON, no other text.
                    """
                    
                    response = llm.invoke(analysis_prompt)
                    
                    # Parse LLM response
                    if hasattr(response, 'content'):
                        analysis_text = response.content
                    elif isinstance(response, str):
                        analysis_text = response
                    else:
                        analysis_text = str(response)
                    
                    # Extract JSON
                    import json
                    json_match = re.search(r'\{.*\}', analysis_text, re.DOTALL)
                    if json_match:
                        intelligent_analysis = json.loads(json_match.group())
                        logger.info(f"LLM dynamic analysis result: {intelligent_analysis}")
                        
                        # Apply LLM's custom analysis strategy
                        processed_rows = _apply_dynamic_analysis_strategy(rows, intelligent_analysis, user_input)
                        
                    else:
                        raise ValueError("No valid JSON found in LLM response")
                        
                except Exception as e:
                    logger.warning(f"LLM dynamic analysis failed: {e}, using fallback detection")
                    # Fallback to simple pattern detection
                    intelligent_analysis = _fallback_data_analysis(sample_row, user_input, len(rows))
                    processed_rows = _apply_standard_analysis_strategy(rows, intelligent_analysis)
            else:
                # No LLM available, use fallback
                intelligent_analysis = _fallback_data_analysis(sample_row, user_input, len(rows))
                processed_rows = _apply_standard_analysis_strategy(rows, intelligent_analysis)
            
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
            
            logger.info(f"Successfully extracted {len(labels)} data points using dynamic analysis")
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
                            label = str(row[label_idx]) if row[label_idx] else f"Item{len(labels)+1}"
                        value_str = str(row[value_idx]) if row[value_idx] else "0"
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
    chart_config = {
        "type": "bar",
        "data": {
            "labels": ["No Data"],
            "datasets": [{
                "label": "Data",
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
    # Define workflow graph
    workflow = StateGraph(GraphState)
    
    # Add nodes to the graph
    workflow.add_node("start_node", lambda state: state)  # Start node just passes through
    workflow.add_node("router_node", router_node)
    workflow.add_node("sql_classifier_node", sql_classifier_node)
    workflow.add_node("sql_query_node", sql_query_node)  # New node for SQL queries
    workflow.add_node("sql_chart_node", sql_chart_node)  # Renamed from sql_execution_node
    workflow.add_node("rag_query_node", rag_query_node)
    # Merge Chart Config + Render as a single node
    def chart_process_node(state: GraphState) -> GraphState:
        """Generate chart config then render chart in one step."""
        try:
            # Step 1: build config
            cfg_state = chart_config_node(state)
            if cfg_state.get("error"):
                return cfg_state
            # Step 2: render
            rendered_state = chart_rendering_node(cfg_state)
            return rendered_state
        except Exception as e:
            logger.error(f"Chart process node error: {e}")
            return {**state, "error": str(e)}

    workflow.add_node("chart_process_node", chart_process_node)
    workflow.add_node("llm_processing_node", llm_processing_node)
    workflow.add_node("interrupt_node", interrupt_node)  # Add interrupt node
    workflow.add_node("end_node", lambda state: {"success": True})

    # Set entry point
    workflow.set_entry_point("start_node")
    
    # Connect start to router
    workflow.add_edge("start_node", "router_node")

    # Add edges
    workflow.add_conditional_edges(
        "router_node",
        lambda state: state["query_type"],
        {
            "sql": "sql_classifier_node",
            "rag": "rag_query_node"
        }
    )

    # SQL Classifier routes based on task type
    workflow.add_conditional_edges(
        "sql_classifier_node",
        lambda state: state["sql_task_type"],
        {
            "query": "sql_query_node",     # Query task goes to SQL Query node
            "chart": "sql_chart_node"      # Chart task goes to SQL Chart node
        }
    )

    # Connect SQL Query node to LLM Processing with interrupt check
    workflow.add_conditional_edges(
        "sql_query_node",
        check_interrupt_status,
        {
            "continue": "llm_processing_node",
            "interrupt": "interrupt_node"
        }
    )

    # Connect SQL Chart node to Chart Process with interrupt check
    workflow.add_conditional_edges(
        "sql_chart_node",
        check_interrupt_status,
        {
            "continue": "chart_process_node",
            "interrupt": "interrupt_node"
        }
    )

    # Chart process goes directly to LLM processing
    workflow.add_edge("chart_process_node", "llm_processing_node")
    workflow.add_edge("rag_query_node", "llm_processing_node")
    
    # LLM processing goes directly to end node (validation & retry removed)
    workflow.add_edge("llm_processing_node", "end_node")
    
    # Interrupt node goes to end (workflow stops)
    workflow.add_edge("interrupt_node", "end_node")

    # Set finish point
    workflow.set_finish_point("end_node")

    # Compile the graph
    return workflow.compile()
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
            if paused_node == "sql_chart_node":
                # Continue to chart_process → llm_processing
                def chart_process_node_local(s: Dict[str, Any]) -> Dict[str, Any]:
                    t1 = chart_config_node(s)
                    if t1.get("error"):
                        return t1
                    return chart_rendering_node(t1)

                state = chart_process_node_local(state)
                await _emit(state)

                state = await llm_processing_node(state)
                await _emit(state)

            elif paused_node == "sql_query_node":
                # Continue directly to llm_processing
                state = await llm_processing_node(state)
                await _emit(state)

            elif paused_node == "router_node":
                # Edge case: decide branch from existing state without re-running router
                branch = state.get("query_type")
                if branch == "sql":
                    # We assume classifier result already exists; route accordingly
                    task = state.get("sql_task_type")
                    if task == "chart":
                        def chart_process_node_local2(s: Dict[str, Any]) -> Dict[str, Any]:
                            t1 = chart_config_node(s)
                            if t1.get("error"):
                                return t1
                            return chart_rendering_node(t1)
                        state = chart_process_node_local2(state)
                        await _emit(state)
                        state = await llm_processing_node(state)
                        await _emit(state)
                    else:
                        state = await llm_processing_node(state)
                        await _emit(state)
                else:
                    # rag path: continue to llm_processing directly
                    state = await llm_processing_node(state)
                    await _emit(state)
            else:
                # Fallback: if we don't recognize the node, do minimal safe continuation
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
        "query_type": "",  # Will be set by router_node
        "sql_task_type": "",  # Will be set by sql_classifier_node
        "structured_data": None,
        "chart_config": None,
        "chart_image": None,
        "answer": "",
        "quality_score": 10,
        "retry_count": 0,
            "error": None,
            "execution_id": execution_id  # NEW: For token streaming
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
        
        # Determine year filter
        year_filter = None
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
                    rows = [row for row in rows if str(filter_value) in str(row.get("category", ""))]
                    logger.info(f"Applied flexible year filter '{filter_value}': {len(rows)} rows remaining")
                elif filter_key.lower() in ['range', 'time_range']:
                    if isinstance(filter_value, dict) and 'start' in filter_value and 'end' in filter_value:
                        start, end = filter_value['start'], filter_value['end']
                        rows = [row for row in rows if start <= str(row.get("category", "")) <= end]
                        logger.info(f"Applied flexible range filter {start}-{end}: {len(rows)} rows remaining")
        elif isinstance(filter_config, str):
            # Handle string-based filter instructions
            if any(year in filter_config for year in ['2025', '2024', '2023']):
                for year in ['2025', '2024', '2023']:
                    if year in filter_config:
                        rows = [row for row in rows if year in str(row.get("category", ""))]
                        logger.info(f"Applied string-based year filter '{year}': {len(rows)} rows remaining")
                        break
        
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
