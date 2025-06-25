"""
Enhanced workflow processing with detailed tracking and monitoring
"""
import time
import uuid
import asyncio
import logging
from typing import Dict, Any, List, Optional

from .models import WorkflowEvent, WorkflowEventType, NodeStatus, NodeExecutionDetails, ExecutionSummary
from .langgraph_flow import (
    router_node, sql_classifier_node, sql_execution_node,
    chart_config_node, chart_rendering_node, rag_query_node,
    llm_processing_node, validation_node, retry_node
)

logger = logging.getLogger(__name__)

class EnhancedWorkflowTracker:
    """Enhanced workflow tracker with comprehensive monitoring"""
    
    def __init__(self, execution_id: str, websocket_manager=None):
        self.execution_id = execution_id
        self.websocket_manager = websocket_manager
        self.start_time = time.time()
        self.node_details: Dict[str, NodeExecutionDetails] = {}
        self.execution_errors = []
        self.total_memory_peak = 0
        
    async def emit_event(self, event_type: WorkflowEventType, node_id: str = None, **kwargs):
        """Emit workflow events via WebSocket with enhanced data"""
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
    
    async def start_node(self, node_id: str, input_data: Dict[str, Any] = None):
        """Track node start with detailed information"""
        current_time = time.time()
        
        # Create node execution details
        node_detail = NodeExecutionDetails(
            node_id=node_id,
            node_type=self._get_node_type(node_id),
            status=NodeStatus.RUNNING,
            start_time=current_time,
            input_summary=self._summarize_data(input_data),
            memory_usage=self._get_memory_usage()
        )
        
        self.node_details[node_id] = node_detail
        
        # Update peak memory
        current_memory = self._get_memory_usage()
        if current_memory > self.total_memory_peak:
            self.total_memory_peak = current_memory
        
        # Emit enhanced event
        await self.emit_event(
            WorkflowEventType.NODE_STARTED,
            node_id=node_id,
            data={
                "input_summary": node_detail.input_summary,
                "node_type": node_detail.node_type,
                "memory_usage": node_detail.memory_usage,
                "timestamp": current_time,
                "execution_context": {
                    "total_nodes_started": len(self.node_details),
                    "execution_time_elapsed": current_time - self.start_time
                }
            }
        )
    
    async def complete_node(self, node_id: str, output_data: Any = None, retry_count: int = 0):
        """Track node completion with detailed information"""
        current_time = time.time()
        
        if node_id not in self.node_details:
            logger.warning(f"Node {node_id} not found in tracking details")
            return
        
        node_detail = self.node_details[node_id]
        node_detail.status = NodeStatus.COMPLETED
        node_detail.end_time = current_time
        node_detail.duration = current_time - node_detail.start_time
        node_detail.output_summary = self._summarize_data(output_data)
        node_detail.retry_count = retry_count
        
        # Emit enhanced completion event
        await self.emit_event(
            WorkflowEventType.NODE_COMPLETED,
            node_id=node_id,
            duration=node_detail.duration,
            data={
                "duration": node_detail.duration,
                "output_summary": node_detail.output_summary,
                "node_type": node_detail.node_type,
                "retry_count": retry_count,
                "performance_metrics": {
                    "memory_usage": self._get_memory_usage(),
                    "avg_execution_time": self._get_avg_execution_time(),
                    "nodes_completed": len([n for n in self.node_details.values() if n.status == NodeStatus.COMPLETED])
                }
            }
        )
    
    async def error_node(self, node_id: str, error: Exception, retry_count: int = 0):
        """Track node error with detailed information"""
        current_time = time.time()
        
        if node_id not in self.node_details:
            logger.warning(f"Node {node_id} not found in tracking details")
            return
        
        node_detail = self.node_details[node_id]
        node_detail.status = NodeStatus.ERROR
        node_detail.end_time = current_time
        node_detail.duration = current_time - node_detail.start_time
        node_detail.error_details = str(error)
        node_detail.retry_count = retry_count
        
        # Store error for summary
        self.execution_errors.append({
            "node_id": node_id,
            "error": str(error),
            "error_type": type(error).__name__,
            "timestamp": current_time,
            "retry_count": retry_count
        })
        
        # Emit enhanced error event
        await self.emit_event(
            WorkflowEventType.NODE_ERROR,
            node_id=node_id,
            duration=node_detail.duration,
            error=str(error),
            data={
                "error_type": type(error).__name__,
                "error_details": str(error),
                "duration": node_detail.duration,
                "node_type": node_detail.node_type,
                "retry_count": retry_count,
                "error_context": {
                    "total_errors": len(self.execution_errors),
                    "error_rate": len(self.execution_errors) / len(self.node_details) if self.node_details else 0
                }
            }
        )
    
    async def emit_execution_summary(self, final_state: Dict[str, Any]):
        """Emit comprehensive execution summary"""
        current_time = time.time()
        total_duration = current_time - self.start_time
        
        # Create execution summary
        summary = ExecutionSummary(
            execution_id=self.execution_id,
            total_duration=total_duration,
            nodes_executed=len([n for n in self.node_details.values() if n.status in [NodeStatus.COMPLETED, NodeStatus.ERROR]]),
            nodes_failed=len([n for n in self.node_details.values() if n.status == NodeStatus.ERROR]),
            total_memory_peak=self.total_memory_peak,
            start_timestamp=self.start_time,
            end_timestamp=current_time,
            final_quality_score=final_state.get("quality_score", 0),
            success=final_state.get("quality_score", 0) >= 8 and not final_state.get("error"),
            node_details=list(self.node_details.values())
        )
        
        # Emit execution completed event with comprehensive data
        await self.emit_event(
            WorkflowEventType.EXECUTION_COMPLETED,
            data={
                "execution_summary": summary.dict(),
                "performance_analysis": {
                    "total_duration": total_duration,
                    "average_node_time": self._get_avg_execution_time(),
                    "slowest_node": self._get_slowest_node(),
                    "fastest_node": self._get_fastest_node(),
                    "memory_efficiency": self._calculate_memory_efficiency(),
                    "error_rate": len(self.execution_errors) / len(self.node_details) if self.node_details else 0
                },
                "workflow_insights": {
                    "path_taken": self._get_execution_path(),
                    "retry_statistics": self._get_retry_statistics(),
                    "bottleneck_analysis": self._analyze_bottlenecks()
                }
            }
        )
    
    def _get_node_type(self, node_id: str) -> str:
        """Get enhanced node type classification"""
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
        """Create enhanced data summary"""
        if data is None:
            return {"type": "none", "value": None}
        
        if isinstance(data, dict):
            summary = {
                "type": "dictionary",
                "size": len(data),
                "keys": list(data.keys())[:10]
            }
            
            # Special handling for structured data
            if "rows" in data:
                summary["data_structure"] = "tabular"
                summary["row_count"] = len(data.get("rows", []))
                summary["columns"] = data.get("columns", [])
            elif "answer" in data:
                summary["data_structure"] = "text_response"
                summary["answer_length"] = len(str(data["answer"]))
            
            return summary
        
        elif isinstance(data, str):
            return {
                "type": "string",
                "length": len(data),
                "preview": data[:100] + "..." if len(data) > 100 else data,
                "encoding": "utf-8"
            }
        
        elif isinstance(data, list):
            return {
                "type": "list",
                "length": len(data),
                "sample": data[:3] if len(data) > 3 else data,
                "item_types": list(set(type(item).__name__ for item in data[:10]))
            }
        
        else:
            return {
                "type": type(data).__name__,
                "value": str(data)[:100],
                "size_estimate": len(str(data))
            }
    
    def _get_memory_usage(self) -> int:
        """Get current memory usage in MB"""
        try:
            import psutil
            process = psutil.Process()
            return int(process.memory_info().rss / 1024 / 1024)
        except:
            return 0
    
    def _get_avg_execution_time(self) -> float:
        """Calculate average execution time for completed nodes"""
        completed_nodes = [n for n in self.node_details.values() if n.duration is not None]
        if not completed_nodes:
            return 0.0
        return sum(n.duration for n in completed_nodes) / len(completed_nodes)
    
    def _get_slowest_node(self) -> Dict[str, Any]:
        """Get information about the slowest node"""
        completed_nodes = [n for n in self.node_details.values() if n.duration is not None]
        if not completed_nodes:
            return {"node_id": None, "duration": 0}
        
        slowest = max(completed_nodes, key=lambda n: n.duration)
        return {
            "node_id": slowest.node_id,
            "duration": slowest.duration,
            "node_type": slowest.node_type
        }
    
    def _get_fastest_node(self) -> Dict[str, Any]:
        """Get information about the fastest node"""
        completed_nodes = [n for n in self.node_details.values() if n.duration is not None]
        if not completed_nodes:
            return {"node_id": None, "duration": 0}
        
        fastest = min(completed_nodes, key=lambda n: n.duration)
        return {
            "node_id": fastest.node_id,
            "duration": fastest.duration,
            "node_type": fastest.node_type
        }
    
    def _calculate_memory_efficiency(self) -> float:
        """Calculate memory efficiency score"""
        if self.total_memory_peak == 0:
            return 100.0
        
        # Simple efficiency calculation (lower memory usage = higher efficiency)
        base_memory = 50  # MB baseline
        if self.total_memory_peak <= base_memory:
            return 100.0
        else:
            # Decreasing efficiency as memory usage increases
            return max(0.0, 100.0 - ((self.total_memory_peak - base_memory) / base_memory) * 50)
    
    def _get_execution_path(self) -> List[str]:
        """Get the execution path taken"""
        return [detail.node_id for detail in sorted(self.node_details.values(), key=lambda n: n.start_time)]
    
    def _get_retry_statistics(self) -> Dict[str, Any]:
        """Get retry statistics"""
        total_retries = sum(detail.retry_count for detail in self.node_details.values())
        nodes_with_retries = len([detail for detail in self.node_details.values() if detail.retry_count > 0])
        
        return {
            "total_retries": total_retries,
            "nodes_with_retries": nodes_with_retries,
            "retry_rate": nodes_with_retries / len(self.node_details) if self.node_details else 0
        }
    
    def _analyze_bottlenecks(self) -> List[Dict[str, Any]]:
        """Analyze workflow bottlenecks"""
        bottlenecks = []
        avg_time = self._get_avg_execution_time()
        
        for detail in self.node_details.values():
            if detail.duration and detail.duration > avg_time * 2:  # 2x slower than average
                bottlenecks.append({
                    "node_id": detail.node_id,
                    "node_type": detail.node_type,
                    "duration": detail.duration,
                    "slowdown_factor": detail.duration / avg_time if avg_time > 0 else 0,
                    "recommendation": self._get_optimization_recommendation(detail)
                })
        
        return sorted(bottlenecks, key=lambda b: b["duration"], reverse=True)
    
    def _get_optimization_recommendation(self, node_detail: NodeExecutionDetails) -> str:
        """Get optimization recommendation for slow nodes"""
        recommendations = {
            "sql_execution_node": "Consider optimizing SQL queries or database indexes",
            "rag_query_node": "Consider reducing document search scope or improving embeddings",
            "llm_processing_node": "Consider using a faster LLM model or reducing prompt complexity",
            "chart_rendering_node": "Consider optimizing chart configuration or data size",
            "chart_config_node": "Consider simplifying chart configuration logic"
        }
        return recommendations.get(node_detail.node_id, "Consider profiling this node for performance improvements")

async def process_with_enhanced_tracking(user_input: str, datasource: Dict[str, Any], execution_id: str = None) -> Dict[str, Any]:
    """Process query with comprehensive enhanced tracking"""
    
    if not execution_id:
        execution_id = str(uuid.uuid4())
    
    # Import WebSocket manager
    from .websocket_manager import websocket_manager
    
    # Create enhanced tracker
    tracker = EnhancedWorkflowTracker(execution_id, websocket_manager)
    
    # Emit execution started
    await tracker.emit_event(WorkflowEventType.EXECUTION_STARTED, data={
        "query": user_input,
        "datasource_type": datasource.get("type", "unknown"),
        "execution_context": {
            "timestamp": time.time(),
            "estimated_complexity": "medium"  # Could be calculated based on query
        }
    })
    
    try:
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
        
        # Execute enhanced workflow with comprehensive tracking
        # 1. Router judgment
        await tracker.start_node("router_node", {"user_input": user_input})
        await asyncio.sleep(0.5)
        try:
            state = router_node(state)
            await tracker.complete_node("router_node", {"query_type": state["query_type"]})
        except Exception as e:
            await tracker.error_node("router_node", e)
            state["error"] = str(e)
        
        # 2. Process based on query type
        if state["query_type"] == "sql" and not state.get("error"):
            # SQL classification
            await tracker.start_node("sql_classifier_node", {"query_type": state["query_type"]})
            await asyncio.sleep(0.5)
            try:
                state = sql_classifier_node(state)
                await tracker.complete_node("sql_classifier_node", {"sql_task_type": state["sql_task_type"]})
            except Exception as e:
                await tracker.error_node("sql_classifier_node", e)
                state["error"] = str(e)
            
            # SQL execution
            if not state.get("error"):
                await tracker.start_node("sql_execution_node", {"sql_task_type": state["sql_task_type"]})
                await asyncio.sleep(1.0)
                try:
                    state = await sql_execution_node(state)
                    if state.get("error"):
                        await tracker.error_node("sql_execution_node", Exception(state["error"]))
                    else:
                        await tracker.complete_node("sql_execution_node", {
                            "rows_count": len(state.get("structured_data", {}).get("rows", [])),
                            "data_size": len(str(state.get("structured_data", {})))
                        })
                except Exception as e:
                    await tracker.error_node("sql_execution_node", e)
                    state["error"] = str(e)
            
            # Chart processing path
            if state["sql_task_type"] == "chart" and not state.get("error"):
                # Chart configuration
                await tracker.start_node("chart_config_node", {"data_available": bool(state.get("structured_data"))})
                await asyncio.sleep(0.8)
                try:
                    state = chart_config_node(state)
                    await tracker.complete_node("chart_config_node", {
                        "chart_type": state.get("chart_config", {}).get("type"),
                        "config_complexity": len(str(state.get("chart_config", {})))
                    })
                except Exception as e:
                    await tracker.error_node("chart_config_node", e)
                    state["error"] = str(e)
                
                # Chart rendering
                if not state.get("error"):
                    await tracker.start_node("chart_rendering_node", {"chart_config_available": bool(state.get("chart_config"))})
                    await asyncio.sleep(1.2)
                    try:
                        state = chart_rendering_node(state)
                        await tracker.complete_node("chart_rendering_node", {
                            "chart_image_generated": bool(state.get("chart_image")),
                            "image_url_length": len(state.get("chart_image", ""))
                        })
                    except Exception as e:
                        await tracker.error_node("chart_rendering_node", e)
                        state["error"] = str(e)
            
            # LLM processing (for both chart and query types)
            if not state.get("error"):
                processing_type = "chart_explanation" if state.get("chart_image") else "query_response"
                await tracker.start_node("llm_processing_node", {
                    "processing_type": processing_type,
                    "has_data": bool(state.get("structured_data")),
                    "has_chart": bool(state.get("chart_image"))
                })
                await asyncio.sleep(1.5)
                try:
                    state = llm_processing_node(state)
                    await tracker.complete_node("llm_processing_node", {
                        "answer_length": len(state.get("answer", "")),
                        "processing_type": processing_type
                    })
                except Exception as e:
                    await tracker.error_node("llm_processing_node", e)
                    state["error"] = str(e)
        
        elif state["query_type"] == "rag" and not state.get("error"):
            # RAG query path
            await tracker.start_node("rag_query_node", {"user_input": user_input})
            await asyncio.sleep(2.0)
            try:
                state = await rag_query_node(state)
                await tracker.complete_node("rag_query_node", {
                    "answer_length": len(state.get("answer", "")),
                    "rag_completed": True
                })
            except Exception as e:
                await tracker.error_node("rag_query_node", e)
                state["error"] = str(e)
            
            # LLM processing for RAG results
            if not state.get("error"):
                await tracker.start_node("llm_processing_node", {"processing_type": "rag_response"})
                await asyncio.sleep(1.5)
                try:
                    state = llm_processing_node(state)
                    await tracker.complete_node("llm_processing_node", {
                        "answer_length": len(state.get("answer", "")),
                        "processing_type": "rag_response"
                    })
                except Exception as e:
                    await tracker.error_node("llm_processing_node", e)
                    state["error"] = str(e)
        
        # 3. Output validation
        if not state.get("error"):
            await tracker.start_node("validation_node", {"has_answer": bool(state.get("answer"))})
            await asyncio.sleep(0.3)
            try:
                state = validation_node(state)
                await tracker.complete_node("validation_node", {
                    "quality_score": state["quality_score"],
                    "validation_passed": state["quality_score"] >= 8
                })
            except Exception as e:
                await tracker.error_node("validation_node", e)
                state["error"] = str(e)
        
        # 4. Retry logic with enhanced tracking
        original_retry_count = state.get("retry_count", 0)
        max_retries = 2
        
        while (state.get("quality_score", 0) < 8 and 
               state.get("retry_count", 0) < max_retries and 
               not state.get("error")):
            
            await tracker.start_node("retry_node", {
                "retry_count": state["retry_count"],
                "current_quality": state.get("quality_score", 0)
            })
            await asyncio.sleep(0.5)
            try:
                state = retry_node(state)
                await tracker.complete_node("retry_node", {
                    "retry_count": state["retry_count"],
                    "will_retry_again": state["retry_count"] < max_retries
                }, retry_count=state["retry_count"])
                
                # For demo purposes, improve quality after retry
                state["quality_score"] = min(10, state.get("quality_score", 0) + 3)
                
            except Exception as e:
                await tracker.error_node("retry_node", e, retry_count=state.get("retry_count", 0))
                state["error"] = str(e)
                break
        
        # Emit comprehensive execution summary
        await tracker.emit_execution_summary(state)
        
        return {
            "success": state.get("quality_score", 0) >= 8 and not state.get("error"),
            "answer": state.get("answer", ""),
            "query_type": state.get("query_type", ""),
            "sql_task_type": state.get("sql_task_type"),
            "data": state.get("structured_data"),
            "chart_config": state.get("chart_config"),
            "chart_image": state.get("chart_image"),
            "quality_score": state.get("quality_score", 0),
            "error": state.get("error"),
            "execution_id": execution_id,
            "execution_summary": {
                "node_details": {node_id: detail.dict() for node_id, detail in tracker.node_details.items()},
                "execution_errors": tracker.execution_errors,
                "total_memory_peak": tracker.total_memory_peak,
                "total_duration": time.time() - tracker.start_time
            }
        }
        
    except Exception as e:
        logger.error(f"Error in enhanced workflow execution: {e}")
        
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
            "execution_summary": {
                "node_details": {node_id: detail.dict() for node_id, detail in tracker.node_details.items()},
                "execution_errors": tracker.execution_errors,
                "error": str(e)
            }
        } 