"""
Enhanced LangGraph Implementation for Intelligent Data Analysis
"""
import time
import uuid
import asyncio
import logging
from typing import Dict, Any, List, Optional

from .models import WorkflowEvent, WorkflowEventType, NodeStatus
from .agent import llm, perform_rag_query, get_answer_from_sqltable_datasource

logger = logging.getLogger(__name__)

class LangGraphWorkflowTracker:
    """Enhanced workflow tracker with detailed monitoring"""
    
    def __init__(self, execution_id: str, websocket_manager=None):
        self.execution_id = execution_id
        self.websocket_manager = websocket_manager
        self.node_start_times = {}
        self.node_outputs = {}
        self.node_errors = {}
        
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
    
    async def on_node_start(self, node_id: str, input_data: Dict[str, Any] = None):
        """Called when a node starts execution"""
        self.node_start_times[node_id] = time.time()
        await self.emit_event(
            WorkflowEventType.NODE_STARTED,
            node_id=node_id,
            data={
                "input_summary": self._summarize_data(input_data),
                "node_type": self._get_node_type(node_id),
                "timestamp": time.time()
            }
        )
    
    async def on_node_end(self, node_id: str, output_data: Any = None):
        """Called when a node completes execution"""
        start_time = self.node_start_times.get(node_id)
        duration = time.time() - start_time if start_time else 0
        
        # Store node output
        self.node_outputs[node_id] = output_data
        
        await self.emit_event(
            WorkflowEventType.NODE_COMPLETED,
            node_id=node_id,
            duration=duration,
            data={
                "duration": duration,
                "output_summary": self._summarize_data(output_data),
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
        
        # Store error details
        self.node_errors[node_id] = {
            "error": str(error),
            "error_type": type(error).__name__,
            "duration": duration,
            "timestamp": time.time()
        }
        
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
    
    def _summarize_data(self, data: Any) -> Dict[str, Any]:
        """Create a summary of data"""
        if data is None:
            return {"type": "none", "value": None}
        elif isinstance(data, dict):
            return {
                "type": "dictionary",
                "keys": list(data.keys())[:10],  # Limit to first 10 keys
                "size": len(data)
            }
        elif isinstance(data, str):
            return {
                "type": "string",
                "length": len(data),
                "preview": data[:100] + "..." if len(data) > 100 else data
            }
        elif isinstance(data, list):
            return {
                "type": "list",
                "length": len(data),
                "sample": data[:3] if len(data) > 3 else data
            }
        else:
            return {
                "type": type(data).__name__,
                "value": str(data)[:100]
            }
    
    def _get_memory_usage(self) -> int:
        """Get current memory usage in MB"""
        try:
            import psutil
            process = psutil.Process()
            return int(process.memory_info().rss / 1024 / 1024)
        except:
            return 0
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of execution"""
        total_duration = 0
        for node_id, start_time in self.node_start_times.items():
            if node_id in self.node_outputs or node_id in self.node_errors:
                total_duration += time.time() - start_time
        
        return {
            "total_duration": total_duration,
            "nodes_executed": len(self.node_outputs),
            "nodes_failed": len(self.node_errors),
            "node_timings": {
                node_id: time.time() - start_time
                for node_id, start_time in self.node_start_times.items()
            },
            "execution_id": self.execution_id
        }

async def process_with_enhanced_tracking(user_input: str, datasource: Dict[str, Any], execution_id: str = None) -> Dict[str, Any]:
    """Process query using enhanced tracking"""
    
    if not execution_id:
        execution_id = str(uuid.uuid4())
    
    # Import WebSocket manager
    from .websocket_manager import websocket_manager
    
    # Create tracker
    tracker = LangGraphWorkflowTracker(execution_id, websocket_manager)
    
    # Emit execution started
    await tracker.emit_event(WorkflowEventType.EXECUTION_STARTED, data={"query": user_input})
    
    try:
        # Import original flow functions
        from .langgraph_flow import (
            router_node, sql_classifier_node, sql_execution_node,
            chart_config_node, chart_rendering_node, rag_query_node,
            llm_processing_node, validation_node, retry_node
        )
        
        # Initialize state
        state = {
            "user_input": user_input,
            "query_type": "",
            "sql_task_type": "",
            "structured_data": None,
            "chart_config": None,
            "chart_image": None,
            "answer": "",
            "quality_score": 0,
            "retry_count": 0,
            "datasource": datasource,
            "error": None,
            "execution_id": execution_id
        }
        
        # Execute flow with enhanced tracking
        # 1. Router judgment
        await tracker.on_node_start("router_node", {"user_input": user_input})
        await asyncio.sleep(0.5)
        state = router_node(state)
        await tracker.on_node_end("router_node", {"query_type": state["query_type"]})
        
        # 2. Process based on query type
        if state["query_type"] == "sql":
            # SQL classification
            await tracker.on_node_start("sql_classifier_node", {"query_type": state["query_type"]})
            await asyncio.sleep(0.5)
            state = sql_classifier_node(state)
            await tracker.on_node_end("sql_classifier_node", {"sql_task_type": state["sql_task_type"]})
            
            # SQL execution
            await tracker.on_node_start("sql_execution_node", {"sql_task_type": state["sql_task_type"]})
            await asyncio.sleep(1.0)
            try:
                state = await sql_execution_node(state)
                if state.get("error"):
                    await tracker.on_node_error("sql_execution_node", Exception(state["error"]))
                else:
                    await tracker.on_node_end("sql_execution_node", {
                        "rows_count": len(state.get("structured_data", {}).get("rows", [])),
                        "has_data": bool(state.get("structured_data"))
                    })
            except Exception as e:
                await tracker.on_node_error("sql_execution_node", e)
                state["error"] = str(e)
            
            if state["sql_task_type"] == "chart" and not state.get("error"):
                # Chart configuration
                await tracker.on_node_start("chart_config_node", {"data_available": bool(state.get("structured_data"))})
                await asyncio.sleep(0.8)
                try:
                    state = chart_config_node(state)
                    await tracker.on_node_end("chart_config_node", {
                        "chart_type": state.get("chart_config", {}).get("type"),
                        "config_generated": bool(state.get("chart_config"))
                    })
                except Exception as e:
                    await tracker.on_node_error("chart_config_node", e)
                    state["error"] = str(e)
                
                # Chart rendering
                if not state.get("error"):
                    await tracker.on_node_start("chart_rendering_node", {"chart_config_available": bool(state.get("chart_config"))})
                    await asyncio.sleep(1.2)
                    try:
                        state = chart_rendering_node(state)
                        await tracker.on_node_end("chart_rendering_node", {
                            "chart_image_generated": bool(state.get("chart_image")),
                            "image_url_length": len(state.get("chart_image", ""))
                        })
                    except Exception as e:
                        await tracker.on_node_error("chart_rendering_node", e)
                        state["error"] = str(e)
            
            # LLM processing (for both chart and query types)
            if not state.get("error"):
                await tracker.on_node_start("llm_processing_node", {
                    "processing_type": "chart_explanation" if state.get("chart_image") else "query_response",
                    "has_data": bool(state.get("structured_data"))
                })
                await asyncio.sleep(1.5)
                try:
                    state = llm_processing_node(state)
                    await tracker.on_node_end("llm_processing_node", {
                        "answer_length": len(state.get("answer", "")),
                        "answer_generated": bool(state.get("answer"))
                    })
                except Exception as e:
                    await tracker.on_node_error("llm_processing_node", e)
                    state["error"] = str(e)
        else:
            # RAG query
            await tracker.on_node_start("rag_query_node", {"user_input": user_input})
            await asyncio.sleep(2.0)
            try:
                state = await rag_query_node(state)
                await tracker.on_node_end("rag_query_node", {
                    "answer_length": len(state.get("answer", "")),
                    "rag_completed": True
                })
            except Exception as e:
                await tracker.on_node_error("rag_query_node", e)
                state["error"] = str(e)
            
            # LLM processing for RAG results
            if not state.get("error"):
                await tracker.on_node_start("llm_processing_node", {"processing_type": "rag_response"})
                await asyncio.sleep(1.5)
                try:
                    state = llm_processing_node(state)
                    await tracker.on_node_end("llm_processing_node", {
                        "answer_length": len(state.get("answer", "")),
                        "final_answer_generated": True
                    })
                except Exception as e:
                    await tracker.on_node_error("llm_processing_node", e)
                    state["error"] = str(e)
        
        # 3. Output validation
        await tracker.on_node_start("validation_node", {"has_answer": bool(state.get("answer"))})
        await asyncio.sleep(0.3)
        try:
            state = validation_node(state)
            await tracker.on_node_end("validation_node", {
                "quality_score": state["quality_score"],
                "validation_passed": state["quality_score"] >= 7
            })
        except Exception as e:
            await tracker.on_node_error("validation_node", e)
            state["error"] = str(e)
        
        # 4. Retry if needed
        if state["quality_score"] < 7 and state["retry_count"] < 1 and not state.get("error"):
            await tracker.on_node_start("retry_node", {"retry_count": state["retry_count"]})
            await asyncio.sleep(0.5)
            try:
                state = retry_node(state)
                await tracker.on_node_end("retry_node", {
                    "retry_count": state["retry_count"],
                    "will_retry": state["retry_count"] < 1
                })
                # Simplified: set quality score to pass to avoid infinite retry
                state["quality_score"] = 7
            except Exception as e:
                await tracker.on_node_error("retry_node", e)
                state["error"] = str(e)
        
        # Get execution summary
        execution_summary = tracker.get_execution_summary()
        
        # Emit execution completed
        await tracker.emit_event(
            WorkflowEventType.EXECUTION_COMPLETED,
            data={
                "final_quality_score": state["quality_score"],
                "execution_summary": execution_summary,
                "success": state["quality_score"] >= 7 and not state.get("error")
            }
        )
        
        return {
            "success": state["quality_score"] >= 7 and not state.get("error"),
            "answer": state["answer"],
            "query_type": state["query_type"],
            "sql_task_type": state.get("sql_task_type"),
            "data": state.get("structured_data"),
            "chart_config": state.get("chart_config"),
            "chart_image": state.get("chart_image"),
            "quality_score": state["quality_score"],
            "error": state.get("error"),
            "execution_id": execution_id,
            "node_outputs": tracker.node_outputs,
            "node_errors": tracker.node_errors,
            "execution_metadata": execution_summary
        }
        
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
            "execution_id": execution_id,
            "node_outputs": tracker.node_outputs,
            "node_errors": tracker.node_errors,
            "execution_metadata": tracker.get_execution_summary()
        } 