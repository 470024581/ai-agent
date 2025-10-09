"""
WebSocket connection manager for real-time workflow tracking
"""
import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from ..models.data_models import WorkflowEvent, ExecutionState, NodeState, NodeStatus

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manage WebSocket connections for workflow tracking"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.client_to_execution: Dict[str, str] = {}
        self.execution_to_client: Dict[str, str] = {}
        self.execution_states: Dict[str, Dict[str, Any]] = {}
        self.pending_cleanup: List[str] = []
        self.execution_paused: Dict[str, bool] = {}
        self.execution_cancelled: Dict[str, bool] = {}
        
        # HITL state management
        self.hitl_interrupted_executions: Dict[str, Dict[str, Any]] = {}
    
    def make_serializable(self, obj):
        """Convert complex objects to serializable format"""
        if isinstance(obj, dict):
            return {k: self.make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self.make_serializable(item) for item in obj]
        elif hasattr(obj, '__dict__'):
            # For complex objects, extract basic attributes
            try:
                return {k: self.make_serializable(v) for k, v in obj.__dict__.items() 
                        if not k.startswith('_')}
            except:
                return str(obj)
        else:
            return obj
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """Connect a new WebSocket client."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket connected for client_id: {client_id}")
    
    def get_client_execution(self, client_id: str) -> Optional[str]:
        """Get the current execution ID for a client."""
        return self.client_to_execution.get(client_id)
    
    def mark_for_cleanup(self, execution_id: str):
        """Mark an execution for cleanup."""
        if execution_id not in self.pending_cleanup:
            self.pending_cleanup.append(execution_id)
            logger.info(f"Marked execution {execution_id} for cleanup")
            
    def cleanup_marked_executions(self):
        """Clean up all executions that have been marked for cleanup."""
        for execution_id in self.pending_cleanup[:]:
            self.cleanup_execution(execution_id)
            self.pending_cleanup.remove(execution_id)
            logger.info(f"Cleaned up all resources for execution {execution_id}")
    
    def associate_execution(self, client_id: str, execution_id: str) -> bool:
        """Associate a client with an execution ID."""
        if client_id not in self.active_connections:
            logger.warning(f"Client {client_id} not found for association with execution {execution_id}")
            return False
            
        # Clean up any marked executions before creating new association
        self.cleanup_marked_executions()
        
        # Create new association
        self.client_to_execution[client_id] = execution_id
        self.execution_to_client[execution_id] = client_id
        self.execution_states[execution_id] = {}
        return True
    
    def disconnect(self, websocket: WebSocket, client_id: str):
        """Disconnect a WebSocket client."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            # Only clean up execution mapping if it exists
            if client_id in self.client_to_execution:
                execution_id = self.client_to_execution[client_id]
                if execution_id in self.execution_to_client:
                    del self.execution_to_client[execution_id]
                del self.client_to_execution[client_id]
    
    async def send_to_websocket(self, websocket: WebSocket, data: dict):
        """Send data to a specific WebSocket."""
        try:
            await websocket.send_text(json.dumps(data, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {e}")
    
    async def broadcast_to_execution(self, execution_id: str, event: WorkflowEvent):
        """Broadcast event to all connections for an execution."""
        if execution_id not in self.execution_to_client:
            logger.warning(f"No active WebSocket connections for execution {execution_id} to broadcast event {event.type}.")
            return
        
        logger.info(f"Broadcasting {event.type} event to {len(self.execution_to_client)} connections for execution {execution_id}")
        
        # Update execution state
        self.update_execution_state(execution_id, event)
        
        # Prepare message
        message = event.dict()
        
        # Send to all connected clients for this execution
        disconnected_clients = []
        for cid, websocket in self.active_connections.items():
            if self.execution_to_client.get(execution_id) == cid:
                try:
                    await self.send_to_websocket(websocket, message)
                except WebSocketDisconnect:
                    disconnected_clients.append((websocket, cid))
                except Exception as e:
                    logger.error(f"Error broadcasting to WebSocket: {e}")
                    disconnected_clients.append((websocket, cid))
        
        # Clean up disconnected WebSockets
        for websocket, client_id in disconnected_clients:
            self.disconnect(websocket, client_id)
    
    async def stream_token(self, execution_id: str, token: str, node_id: str = "llm_processing_node", stream_complete: bool = False):
        """Stream a single token to all connections for an execution.
        
        Args:
            execution_id: Execution ID
            token: Token text to stream
            node_id: Node ID generating the token (default: llm_processing_node)
            stream_complete: Whether this is the last token in the stream
        """
        from ..models.data_models import WorkflowEvent, WorkflowEventType
        import time
        
        if execution_id not in self.execution_to_client:
            logger.warning(f"No active WebSocket connections for execution {execution_id} to stream token.")
            return
        
        # Create token stream event
        event = WorkflowEvent(
            type=WorkflowEventType.TOKEN_STREAM,
            execution_id=execution_id,
            timestamp=time.time(),
            node_id=node_id,
            token=token,
            stream_complete=stream_complete
        )
        
        # Prepare message
        message = event.dict()
        
        # Send to all connected clients for this execution
        disconnected_clients = []
        for cid, websocket in self.active_connections.items():
            if self.execution_to_client.get(execution_id) == cid:
                try:
                    await self.send_to_websocket(websocket, message)
                except WebSocketDisconnect:
                    disconnected_clients.append((websocket, cid))
                except Exception as e:
                    logger.error(f"Error streaming token to WebSocket: {e}")
                    disconnected_clients.append((websocket, cid))
        
        # Clean up disconnected WebSockets
        for websocket, client_id in disconnected_clients:
            self.disconnect(websocket, client_id)
    
    def update_execution_state(self, execution_id: str, event: WorkflowEvent):
        """Update execution state based on event"""
        if execution_id not in self.execution_states:
            self.execution_states[execution_id] = {}
        
        execution_state = self.execution_states[execution_id]
        
        if event.type == "execution_started":
            execution_state["status"] = NodeStatus.RUNNING
            execution_state["start_time"] = event.timestamp
        
        elif event.type == "node_started":
            if event.node_id:
                execution_state["current_node"] = event.node_id
                execution_state[event.node_id] = NodeState(
                    id=event.node_id,
                    status=NodeStatus.RUNNING,
                    start_time=event.timestamp
                )
        
        elif event.type == "node_completed":
            if event.node_id and event.node_id in execution_state:
                node_state = execution_state[event.node_id]
                node_state.status = NodeStatus.COMPLETED
                node_state.end_time = event.timestamp
                if node_state.start_time:
                    node_state.duration = event.timestamp - node_state.start_time
                node_state.data = event.data
        
        elif event.type == "node_error":
            if event.node_id and event.node_id in execution_state:
                node_state = execution_state[event.node_id]
                node_state.status = NodeStatus.ERROR
                node_state.end_time = event.timestamp
                node_state.error = event.error
                if node_state.start_time:
                    node_state.duration = event.timestamp - node_state.start_time
        
        elif event.type == "execution_completed":
            execution_state["status"] = NodeStatus.COMPLETED
            execution_state["end_time"] = event.timestamp
            execution_state["current_node"] = None
            # Keep execution state and connections for user to review results
            # Don't auto-cleanup - let user start new analysis to trigger cleanup
            logger.info(f"Execution {execution_id} marked as completed, keeping all states for review")
        
        elif event.type == "execution_error":
            execution_state["status"] = NodeStatus.ERROR
            execution_state["end_time"] = event.timestamp
            execution_state["error"] = event.error
            execution_state["current_node"] = None
            # Cleanup after error
            self.cleanup_execution(execution_id)
    
    def get_execution_state(self, execution_id: str) -> ExecutionState:
        """Get current execution state"""
        return self.execution_states.get(execution_id)
    
    def cleanup_execution(self, execution_id: str):
        """Clean up execution related resources without affecting WebSocket connections."""
        if execution_id in self.execution_states:
            del self.execution_states[execution_id]
        if execution_id in self.execution_paused:
            del self.execution_paused[execution_id]
        if execution_id in self.execution_cancelled:
            del self.execution_cancelled[execution_id]
        
        # Remove execution mappings but keep WebSocket connection
        if execution_id in self.execution_to_client:
            client_id = self.execution_to_client[execution_id]
            if client_id in self.client_to_execution:
                del self.client_to_execution[client_id]
            del self.execution_to_client[execution_id]
        logger.info(f"Cleaned up all resources for execution {execution_id}")
    
    async def get_execution_details(self, execution_id: str) -> dict:
        """Get detailed execution information"""
        execution_state = self.execution_states.get(execution_id)
        if not execution_state:
            return {"error": "Execution not found"}
        
        return {
            "execution_id": execution_id,
            "start_time": execution_state.get("start_time"),
            "end_time": execution_state.get("end_time"),
            "status": execution_state.get("status", NodeStatus.PENDING).value,
            "current_node": execution_state.get("current_node"),
            "total_duration": (execution_state.get("end_time") or execution_state.get("start_time")) - execution_state.get("start_time"),
            "nodes": {
                node_id: {
                    "status": node_state.status.value if hasattr(node_state, 'status') else "unknown",
                    "start_time": getattr(node_state, 'start_time', None),
                    "end_time": getattr(node_state, 'end_time', None),
                    "duration": getattr(node_state, 'duration', None),
                    "error": getattr(node_state, 'error', None)
                }
                for node_id, node_state in execution_state.items()
                if isinstance(node_state, NodeState)
            }
        }
    
    def get_active_executions(self) -> List[str]:
        """Get list of active execution IDs"""
        return list(self.execution_states.keys())
    
    async def get_execution_summary(self, execution_id: str) -> dict:
        """Get execution summary information"""
        execution_state = self.execution_states.get(execution_id)
        if not execution_state:
            return {"error": "Execution not found"}
        
        completed_nodes = sum(1 for state in execution_state.values() 
                             if isinstance(state, NodeState) and state.status == NodeStatus.COMPLETED)
        error_nodes = sum(1 for state in execution_state.values()
                         if isinstance(state, NodeState) and state.status == NodeStatus.ERROR)
        total_nodes = sum(1 for state in execution_state.values() if isinstance(state, NodeState))
        
        return {
            "execution_id": execution_id,
            "status": execution_state.get("status", NodeStatus.PENDING).value,
            "progress": {
                "completed": completed_nodes,
                "errors": error_nodes,
                "total": total_nodes,
                "percentage": (completed_nodes / total_nodes * 100) if total_nodes > 0 else 0
            },
            "timing": {
                "start_time": execution_state.get("start_time"),
                "end_time": execution_state.get("end_time"),
                "duration": (execution_state.get("end_time", 0) - execution_state.get("start_time", 0)) if execution_state.get("start_time") else None
            }
        }

    # ==================== HITL (Human-in-the-Loop) Methods ====================
    
    async def handle_hitl_message(self, client_id: str, message: Dict[str, Any]):
        """Handle HITL control messages from client"""
        logger.info(f"🔄 [BACKEND-WS] handle_hitl_message called")
        logger.info(f"📥 [BACKEND-WS] handle_hitl_message input params: client_id={client_id}, message={message}")
        
        try:
            message_type = message.get("type")
            execution_id = message.get("execution_id")
            
            logger.info(f"📊 [BACKEND-WS] handle_hitl_message processing: type={message_type}, execution_id={execution_id}")
            
            if not execution_id:
                logger.error(f"❌ [BACKEND-WS] handle_hitl_message failed: Missing execution_id")
                await self.send_error(client_id, "Missing execution_id in HITL message")
                return
            
            if message_type == "hitl_interrupt":
                logger.info(f"🔄 [BACKEND-WS] handle_hitl_message routing to interrupt_execution")
                await self.interrupt_execution(client_id, execution_id, message)
            elif message_type == "hitl_resume":
                logger.info(f"🔄 [BACKEND-WS] handle_hitl_message routing to resume_execution")
                await self.resume_execution(client_id, execution_id, message)
            elif message_type == "hitl_cancel":
                logger.info(f"🔄 [BACKEND-WS] handle_hitl_message routing to cancel_execution")
                await self.cancel_execution(client_id, execution_id, message)
            else:
                logger.error(f"❌ [BACKEND-WS] handle_hitl_message failed: Unknown message type {message_type}")
                await self.send_error(client_id, f"Unknown HITL message type: {message_type}")
            
            logger.info(f"✅ [BACKEND-WS] handle_hitl_message completed successfully")
                
        except Exception as e:
            logger.error(f"❌ [BACKEND-WS] handle_hitl_message failed: {e}")
            await self.send_error(client_id, f"Error processing HITL message: {str(e)}")
    
    async def interrupt_execution(self, client_id: str, execution_id: str, message: Dict[str, Any]):
        """Interrupt workflow execution"""
        try:
            from ..utils.hitl_state_manager import hitl_state_manager
            
            # Get current execution state
            execution_state = self.execution_states.get(execution_id)
            if not execution_state:
                await self.send_error(client_id, f"Execution {execution_id} not found")
                return
            
            node_name = message.get("node_name", "unknown")
            reason = message.get("reason", "user_request")
            
            # Create serializable state snapshot for interrupt  
            interrupt_state = {
                "execution_id": execution_id,
                "user_input": execution_state.get("user_input", ""),
                "current_node": execution_state.get("current_node"),
                "status": execution_state.get("status"),
                "structured_data": execution_state.get("structured_data"),
                "chart_config": execution_state.get("chart_config"),
                "query_type": execution_state.get("query_type"),
                "sql_task_type": execution_state.get("sql_task_type"),
                "answer": execution_state.get("answer", ""),
                "error": execution_state.get("error"),
                "quality_score": execution_state.get("quality_score", 0),
                "timestamp": message.get("timestamp")
            }
            
            # Make all state values JSON serializable
            interrupt_state = self.make_serializable(interrupt_state)
            
            # Store interrupt state in database
            success = hitl_state_manager.interrupt_execution(execution_id, interrupt_state, node_name, reason)
            
            if success:
                self.hitl_interrupted_executions[execution_id] = interrupt_state
                self.execution_cancelled[execution_id] = True
                
                # Notify client with current state
                await self.send_to_client(client_id, {
                    "type": "hitl_interrupted", 
                    "execution_id": execution_id,
                    "node_name": node_name,
                    "reason": reason,
                    "current_state": interrupt_state,
                    "timestamp": message.get("timestamp")
                })
                
                logger.info(f"Execution {execution_id} interrupted at node {node_name}")
            else:
                await self.send_error(client_id, f"Failed to interrupt execution {execution_id}")
                
        except Exception as e:
            logger.error(f"Error interrupting execution {execution_id}: {e}")
            await self.send_error(client_id, f"Error interrupting execution: {str(e)}")
    
    async def resume_execution(self, client_id: str, execution_id: str, message: Dict[str, Any]):
        """Resume paused or interrupted execution"""
        logger.info(f"🔄 [BACKEND-WS] resume_execution called")
        logger.info(f"📥 [BACKEND-WS] resume_execution input params: client_id={client_id}, execution_id={execution_id}, message={message}")
        
        try:
            from ..utils.hitl_state_manager import hitl_state_manager
            
            parameters = message.get("parameters", {})
            execution_type = message.get("execution_type", "interrupt")  # Only "interrupt" now
            
            logger.info(f"📊 [BACKEND-WS] resume_execution parameters: {parameters}")
            logger.info(f"📊 [BACKEND-WS] resume_execution execution_type: {execution_type}")
            
            # Restore state for interrupt
            logger.info(f"🔄 [BACKEND-WS] resume_execution calling hitl_state_manager.restore_interrupt")
            restored_state = hitl_state_manager.restore_interrupt(execution_id, parameters)
            logger.info(f"📊 [BACKEND-WS] resume_execution hitl_state_manager.restore_interrupt result: {restored_state}")
            
            if execution_id in self.hitl_interrupted_executions:
                del self.hitl_interrupted_executions[execution_id]
                logger.info(f"📊 [BACKEND-WS] resume_execution removed execution {execution_id} from hitl_interrupted_executions")
            
            if restored_state:
                logger.info(f"📊 [BACKEND-WS] resume_execution restored_state keys: {list(restored_state.keys())}")
                
                # Update execution state
                if execution_id in self.execution_states:
                    self.execution_states[execution_id].update(restored_state.get("node_states", {}))
                    logger.info(f"📊 [BACKEND-WS] resume_execution updated execution_states for {execution_id}")
                
                # Clear pause/cancel flags
                if execution_id in self.execution_paused:
                    del self.execution_paused[execution_id]
                    logger.info(f"📊 [BACKEND-WS] resume_execution removed execution {execution_id} from execution_paused")
                if execution_id in self.execution_cancelled:
                    del self.execution_cancelled[execution_id]
                    logger.info(f"📊 [BACKEND-WS] resume_execution removed execution {execution_id} from execution_cancelled")
                
                # Clear pause status from restored state but keep paused node info
                restored_state["hitl_status"] = "running"
                # Don't remove hitl_paused - we need it for resume logic
                # restored_state.pop("hitl_paused", None)
                restored_state.pop("hitl_reason", None)
                
                # Notify client
                response_message = {
                    "type": "hitl_resumed",
                    "execution_id": execution_id,
                    "execution_type": execution_type,
                    "parameters": parameters,
                    "timestamp": message.get("timestamp")
                }
                
                logger.info(f"📤 [BACKEND-WS] resume_execution sending response to client: {response_message}")
                await self.send_to_client(client_id, response_message)
                
                logger.info(f"✅ [BACKEND-WS] resume_execution completed successfully for execution {execution_id}")
                
                # Restart workflow execution from the restored state
                logger.info(f"🔄 [BACKEND-WS] resume_execution calling restart_workflow_execution")
                await self.restart_workflow_execution(execution_id, restored_state)
                logger.info(f"✅ [BACKEND-WS] resume_execution restart_workflow_execution completed")
                
            else:
                logger.error(f"❌ [BACKEND-WS] resume_execution failed: Failed to resume execution {execution_id}")
                await self.send_error(client_id, f"Failed to resume execution {execution_id}")
                
        except Exception as e:
            logger.error(f"❌ [BACKEND-WS] resume_execution failed: Error resuming execution {execution_id}: {e}")
            await self.send_error(client_id, f"Error resuming execution: {str(e)}")
    
    async def restart_workflow_execution(self, execution_id: str, restored_state: Dict[str, Any]):
        """Resume workflow execution from paused state"""
        try:
            from ..chains.langgraph_flow import resume_workflow_from_paused_state
            
            # Extract necessary parameters from restored state
            user_input = restored_state.get("user_input", "")
            datasource = restored_state.get("datasource", {})
            paused_node = restored_state.get("hitl_paused", "")
            
            # Log the paused node for debugging
            logger.info(f"Paused node from restored state: '{paused_node}'")
            
            logger.info(f"Resuming workflow execution {execution_id} from paused state")
            logger.info(f"Restored user_input: {user_input}")
            logger.info(f"Restored datasource: {datasource}")
            logger.info(f"Paused at node: {paused_node}")
            logger.info(f"Restored state keys: {list(restored_state.keys())}")
            
            # Ensure execution_id is set in restored state
            restored_state["execution_id"] = execution_id
            
            # Resume the workflow from the paused state
            result = await resume_workflow_from_paused_state(
                execution_id=execution_id,
                paused_state=restored_state,
                paused_node=paused_node
            )
            
            logger.info(f"Workflow execution {execution_id} resumed successfully")
            logger.info(f"Resume result keys: {list(result.keys()) if isinstance(result, dict) else 'not_dict'}")
            
        except Exception as e:
            logger.error(f"Error resuming workflow execution {execution_id}: {e}")
            logger.error(f"Restart error details: {str(e)}", exc_info=True)
            # Notify client about restart error
            client_id = self.execution_to_client.get(execution_id)
            if client_id:
                await self.send_error(client_id, f"Error restarting workflow: {str(e)}")
    
    async def cancel_execution(self, client_id: str, execution_id: str, message: Dict[str, Any]):
        """Cancel paused or interrupted execution"""
        try:
            from ..utils.hitl_state_manager import hitl_state_manager
            
            execution_type = message.get("execution_type", "interrupt")
            
            # Cancel execution
            success = hitl_state_manager.cancel_execution(execution_id, execution_type)
            
            if success:
                # Clean up local state
                if execution_id in self.hitl_interrupted_executions:
                    del self.hitl_interrupted_executions[execution_id]
                if execution_id in self.execution_cancelled:
                    del self.execution_cancelled[execution_id]
                
                # Notify client
                await self.send_to_client(client_id, {
                    "type": "hitl_cancelled",
                    "execution_id": execution_id,
                    "execution_type": execution_type,
                    "timestamp": message.get("timestamp")
                })
                
                logger.info(f"Execution {execution_id} cancelled ({execution_type})")
            else:
                await self.send_error(client_id, f"Failed to cancel execution {execution_id}")
                
        except Exception as e:
            logger.error(f"Error cancelling execution {execution_id}: {e}")
            await self.send_error(client_id, f"Error cancelling execution: {str(e)}")
    
    async def send_to_client(self, client_id: str, message: dict):
        """Send message to specific client"""
        try:
            if client_id in self.active_connections:
                websocket = self.active_connections[client_id]
                await websocket.send_text(json.dumps(message, ensure_ascii=False))
                logger.debug(f"Sent message to client {client_id}: {message.get('type', 'unknown')}")
        except Exception as e:
            logger.error(f"Error sending message to client {client_id}: {e}")
    
    async def send_error(self, client_id: str, error_message: str):
        """Send error message to client"""
        await self.send_to_client(client_id, {
            "type": "error",
            "message": error_message,
            "timestamp": time.time()
        })

# Create a singleton instance
websocket_manager = WebSocketManager() 