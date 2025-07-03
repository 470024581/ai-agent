"""
WebSocket connection manager for real-time workflow tracking
"""
import asyncio
import json
import logging
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

# Create a singleton instance
websocket_manager = WebSocketManager() 