"""
WebSocket connection manager for real-time workflow tracking
"""
import asyncio
import json
import logging
from typing import Dict, List
from fastapi import WebSocket, WebSocketDisconnect
from .models import WorkflowEvent, ExecutionState, NodeState, NodeStatus

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manage WebSocket connections for workflow tracking"""
    
    def __init__(self):
        # Store connections by client_id before an execution starts
        self.client_connections: Dict[str, WebSocket] = {}
        # Map client_id to execution_id once an execution is associated
        self.client_to_execution: Dict[str, str] = {}
        # Store active connections by execution_id
        self.execution_connections: Dict[str, List[WebSocket]] = {}
        # Store execution states
        self.execution_states: Dict[str, ExecutionState] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept new WebSocket connection with a client_id."""
        await websocket.accept()
        self.client_connections[client_id] = websocket
        logger.info(f"WebSocket connected for client_id: {client_id}")
    
    def associate_execution(self, client_id: str, execution_id: str):
        """Associate a client's connection with a new execution_id."""
        if client_id in self.client_connections:
            websocket = self.client_connections.pop(client_id)
            
            if execution_id not in self.execution_connections:
                self.execution_connections[execution_id] = []
            
            self.execution_connections[execution_id].append(websocket)
            self.client_to_execution[client_id] = execution_id
            logger.info(f"Associated client {client_id} with execution {execution_id}")
            return True
        else:
            logger.warning(f"Client {client_id} not found for association with execution {execution_id}")
            return False
    
    def disconnect(self, websocket: WebSocket, client_id: str):
        """Remove WebSocket connection using client_id."""
        # Check if the client was associated with an execution
        if client_id in self.client_to_execution:
            execution_id = self.client_to_execution.pop(client_id)
            if execution_id in self.execution_connections:
                if websocket in self.execution_connections[execution_id]:
                    self.execution_connections[execution_id].remove(websocket)
                    logger.info(f"WebSocket for client {client_id} (exec: {execution_id}) disconnected.")
                    if not self.execution_connections[execution_id]:
                        del self.execution_connections[execution_id]
                        logger.info(f"Cleaned up connection resources for execution {execution_id}")
        # If not associated, just remove from client connections
        elif client_id in self.client_connections:
            del self.client_connections[client_id]
            logger.info(f"Unassociated client {client_id} disconnected.")
    
    async def send_to_websocket(self, websocket: WebSocket, data: dict):
        """Send data to a specific WebSocket."""
        try:
            await websocket.send_text(json.dumps(data, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {e}")
    
    async def broadcast_to_execution(self, execution_id: str, event: WorkflowEvent):
        """Broadcast event to all connections for an execution."""
        if execution_id not in self.execution_connections:
            logger.warning(f"No active WebSocket connections for execution {execution_id} to broadcast event {event.type}.")
            return
        
        logger.info(f"Broadcasting {event.type} event to {len(self.execution_connections[execution_id])} connections for execution {execution_id}")
        
        # Update execution state
        self.update_execution_state(execution_id, event)
        
        # Prepare message
        message = event.dict()
        
        # Send to all connected clients for this execution
        disconnected_clients = []
        for websocket in self.execution_connections.get(execution_id, []):
            try:
                await self.send_to_websocket(websocket, message)
            except WebSocketDisconnect:
                # Find the client_id for this websocket to mark for disconnection
                for cid, eid in self.client_to_execution.items():
                    if eid == execution_id:
                        disconnected_clients.append((websocket, cid))
                        break
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket: {e}")
                for cid, eid in self.client_to_execution.items():
                    if eid == execution_id:
                        disconnected_clients.append((websocket, cid))
                        break
        
        # Clean up disconnected WebSockets
        for websocket, client_id in disconnected_clients:
            self.disconnect(websocket, client_id)
    
    def update_execution_state(self, execution_id: str, event: WorkflowEvent):
        """Update execution state based on event"""
        if execution_id not in self.execution_states:
            self.execution_states[execution_id] = ExecutionState(
                execution_id=execution_id,
                start_time=event.timestamp,
                status=NodeStatus.RUNNING
            )
        
        execution_state = self.execution_states[execution_id]
        
        if event.type == "execution_started":
            execution_state.status = NodeStatus.RUNNING
            execution_state.start_time = event.timestamp
        
        elif event.type == "node_started":
            if event.node_id:
                execution_state.current_node = event.node_id
                execution_state.nodes[event.node_id] = NodeState(
                    id=event.node_id,
                    status=NodeStatus.RUNNING,
                    start_time=event.timestamp
                )
        
        elif event.type == "node_completed":
            if event.node_id and event.node_id in execution_state.nodes:
                node_state = execution_state.nodes[event.node_id]
                node_state.status = NodeStatus.COMPLETED
                node_state.end_time = event.timestamp
                if node_state.start_time:
                    node_state.duration = event.timestamp - node_state.start_time
                node_state.data = event.data
        
        elif event.type == "node_error":
            if event.node_id and event.node_id in execution_state.nodes:
                node_state = execution_state.nodes[event.node_id]
                node_state.status = NodeStatus.ERROR
                node_state.end_time = event.timestamp
                node_state.error = event.error
                if node_state.start_time:
                    node_state.duration = event.timestamp - node_state.start_time
        
        elif event.type == "execution_completed":
            execution_state.status = NodeStatus.COMPLETED
            execution_state.end_time = event.timestamp
            execution_state.current_node = None
            # Keep execution state and connections for user to review results
            # Don't auto-cleanup - let user start new analysis to trigger cleanup
            logger.info(f"Execution {execution_id} marked as completed, keeping all states for review")
        
        elif event.type == "execution_error":
            execution_state.status = NodeStatus.ERROR
            execution_state.end_time = event.timestamp
            execution_state.error = event.error
            execution_state.current_node = None
            # Cleanup after error
            self.cleanup_execution(execution_id)
    
    def get_execution_state(self, execution_id: str) -> ExecutionState:
        """Get current execution state"""
        return self.execution_states.get(execution_id)
    
    def cleanup_execution(self, execution_id: str):
        """Clean up execution data"""
        if execution_id in self.execution_states:
            del self.execution_states[execution_id]
        if execution_id in self.execution_connections:
            del self.execution_connections[execution_id]
        
        # Also remove any client_id -> execution_id mappings
        clients_to_remove = [cid for cid, eid in self.client_to_execution.items() if eid == execution_id]
        for cid in clients_to_remove:
            if cid in self.client_to_execution:
                del self.client_to_execution[cid]
        logger.info(f"Cleaned up all resources for execution {execution_id}")
    
    async def get_execution_details(self, execution_id: str) -> dict:
        """Get detailed execution information"""
        execution_state = self.execution_states.get(execution_id)
        if not execution_state:
            return {"error": "Execution not found"}
        
        return {
            "execution_id": execution_id,
            "start_time": execution_state.start_time,
            "end_time": execution_state.end_time,
            "status": execution_state.status.value,
            "current_node": execution_state.current_node,
            "total_duration": (execution_state.end_time or execution_state.start_time) - execution_state.start_time,
            "nodes": {
                node_id: {
                    "id": node.id,
                    "status": node.status.value,
                    "start_time": node.start_time,
                    "end_time": node.end_time,
                    "duration": node.duration,
                    "error": node.error,
                    "data": node.data
                }
                for node_id, node in execution_state.nodes.items()
            },
            "error": execution_state.error
        }
    
    def get_active_executions(self) -> List[str]:
        """Get list of active execution IDs"""
        return [eid for eid, state in self.execution_states.items() 
                if state.status in [NodeStatus.PENDING, NodeStatus.RUNNING]]
    
    async def get_execution_summary(self, execution_id: str) -> dict:
        """Get execution performance summary"""
        execution_state = self.execution_states.get(execution_id)
        if not execution_state:
            return {"error": "Execution not found"}
        
        completed_nodes = [node for node in execution_state.nodes.values() 
                          if node.status == NodeStatus.COMPLETED and node.duration]
        failed_nodes = [node for node in execution_state.nodes.values() 
                       if node.status == NodeStatus.ERROR]
        
        total_duration = 0
        if execution_state.end_time and execution_state.start_time:
            total_duration = execution_state.end_time - execution_state.start_time
        
        avg_node_time = 0
        if completed_nodes:
            avg_node_time = sum(node.duration for node in completed_nodes) / len(completed_nodes)
        
        slowest_node = None
        if completed_nodes:
            slowest_node = max(completed_nodes, key=lambda n: n.duration)
        
        return {
            "execution_id": execution_id,
            "total_duration": total_duration,
            "total_nodes": len(execution_state.nodes),
            "completed_nodes": len(completed_nodes),
            "failed_nodes": len(failed_nodes),
            "success_rate": (len(completed_nodes) / len(execution_state.nodes)) if len(execution_state.nodes) > 0 else 0,
            "average_node_time": avg_node_time,
            "slowest_node": {
                "id": slowest_node.id, 
                "duration": slowest_node.duration
            } if slowest_node else None,
            "execution_path": [node.id for node in sorted(execution_state.nodes.values(), 
                                                         key=lambda n: n.start_time or 0)],
            "status": execution_state.status.value
        }

# Global WebSocket manager instance
websocket_manager = WebSocketManager() 