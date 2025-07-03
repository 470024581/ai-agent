"""
Real LangGraph Implementation for Intelligent Data Analysis
"""
import time
import uuid
import asyncio
import logging
from typing import Dict, Any, List, Optional, TypedDict, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ..models.data_models import WorkflowEvent, WorkflowEventType, NodeStatus
from ..agents.intelligent_agent import llm, perform_rag_query, get_answer_from_sqltable_datasource

logger = logging.getLogger(__name__)

class WorkflowState(TypedDict):
    """LangGraph state definition"""
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
    execution_id: str
    node_outputs: Dict[str, Any]  # Store outputs from each node
    execution_metadata: Dict[str, Any]  # Store execution metadata

class LangGraphWorkflowTracker:
    """Enhanced workflow tracker with detailed monitoring"""
    
    def __init__(self, execution_id: str, websocket_manager=None):
        self.execution_id = execution_id
        self.websocket_manager = websocket_manager
        self.node_start_times = {}
        self.node_outputs = {}
        
    async def emit_event(self, event_type: WorkflowEventType, node_id: str = None, **kwargs):
        """Emit workflow events via WebSocket"""
        if not self.websocket_manager:
            return
            
        try:
            event = WorkflowEvent(
                type=event_type,
                execution_id=self.execution_id,
                timestamp=time.time(),
                node_id=node_id,
                **kwargs
            )
            await self.websocket_manager.broadcast_to_execution(self.execution_id, event)
        except Exception as e:
            logger.error(f"Error emitting event: {e}")
    
    async def on_node_start(self, node_id: str, state: WorkflowState):
        """Called when a node starts execution"""
        self.node_start_times[node_id] = time.time()
        await self.emit_event(
            WorkflowEventType.NODE_STARTED,
            node_id=node_id,
            data={
                "input_data": {k: v for k, v in state.items() if k not in ['datasource', 'node_outputs']},
                "node_type": self._get_node_type(node_id)
            }
        )
    
    async def on_node_end(self, node_id: str, state: WorkflowState, output: Any = None):
        """Called when a node completes execution"""
        start_time = self.node_start_times.get(node_id)
        duration = time.time() - start_time if start_time else 0
        
        # Store node output
        self.node_outputs[node_id] = output
        
        await self.emit_event(
            WorkflowEventType.NODE_COMPLETED,
            node_id=node_id,
            duration=duration,
            data={
                "duration": duration,
                "output_summary": self._summarize_output(output),
                "node_type": self._get_node_type(node_id),
                "execution_stats": {
                    "memory_usage": self._get_memory_usage(),
                    "total_nodes_completed": len(self.node_outputs)
                }
            }
        )
    
    async def on_node_error(self, node_id: str, error: Exception):
        """Called when a node encounters an error"""
        start_time = self.node_start_times.get(node_id)
        duration = time.time() - start_time if start_time else 0
        
        await self.emit_event(
            WorkflowEventType.NODE_ERROR,
            node_id=node_id,
            duration=duration,
            error=str(error),
            data={
                "error_type": type(error).__name__,
                "error_details": str(error),
                "duration": duration,
                "node_type": self._get_node_type(node_id)
            }
        )
    
    def _get_node_type(self, node_id: str) -> str:
        """Get node type based on node ID"""
        node_types = {
            "router_node": "decision",
            "sql_classifier_node": "classifier", 
            "sql_execution_node": "execution",
            "chart_config_node": "processing",
            "chart_rendering_node": "rendering",
            "rag_query_node": "retrieval",
            "llm_processing_node": "generation",
            "validation_node": "validation",
            "retry_node": "retry"
        }
        return node_types.get(node_id, "process")
    
    def _summarize_output(self, output: Any) -> Dict[str, Any]:
        """Create a summary of node output"""
        if isinstance(output, dict):
            return {
                "type": "dictionary",
                "keys": list(output.keys()),
                "size": len(output)
            }
        elif isinstance(output, str):
            return {
                "type": "string",
                "length": len(output),
                "preview": output[:100] + "..." if len(output) > 100 else output
            }
        elif isinstance(output, list):
            return {
                "type": "list",
                "length": len(output),
                "sample": output[:3] if len(output) > 3 else output
            }
        else:
            return {
                "type": type(output).__name__,
                "value": str(output)[:100]
            }
    
    def _get_memory_usage(self) -> int:
        """Get current memory usage in MB"""
        try:
            import psutil
            process = psutil.Process()
            return int(process.memory_info().rss / 1024 / 1024)
        except:
            return 0

# Global enhanced flow instance (simplified for now)
async def process_with_real_langgraph(user_input: str, datasource: Dict[str, Any], execution_id: str = None) -> Dict[str, Any]:
    """Process query using enhanced tracking (simplified implementation)"""
    
    if not execution_id:
        execution_id = str(uuid.uuid4())
    
    # Import WebSocket manager
    from ..websocket.websocket_manager import websocket_manager
    
    # Create tracker
    tracker = LangGraphWorkflowTracker(execution_id, websocket_manager)
    
    # Emit execution started
    await tracker.emit_event(WorkflowEventType.EXECUTION_STARTED, data={"query": user_input})
    
    try:
        # For now, use the existing flow but with enhanced tracking
        from .langgraph_flow import process_intelligent_query
        
        # Execute with enhanced tracking
        result = await process_intelligent_query(user_input, datasource, execution_id)
        
        # Add enhanced metadata
        result["node_outputs"] = tracker.node_outputs
        result["execution_metadata"] = {
            "total_nodes_executed": len(tracker.node_outputs),
            "node_timings": {
                node_id: time.time() - start_time
                for node_id, start_time in tracker.node_start_times.items()
            }
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error in enhanced LangGraph execution: {e}")
        
        # Emit execution error
        await tracker.emit_event(
            WorkflowEventType.EXECUTION_ERROR,
            error=str(e),
            data={"error_type": type(e).__name__}
        )
        
        return {
            "success": False,
            "answer": f"Error occurred during execution: {str(e)}",
            "error": str(e),
            "execution_id": execution_id
        } 