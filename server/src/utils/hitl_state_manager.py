"""
HITL (Human-in-the-Loop) State Manager

This module manages HITL workflow states with memory storage only:
- Pause states: Stored in memory for quick access and temporary suspension
- Interrupt states: Stored in memory for persistence during session
"""

import json
import time
import logging
from typing import Dict, Any, Optional, List
import threading

logger = logging.getLogger(__name__)


class HITLStateManager:
    """Manages HITL workflow states with memory storage only"""
    
    def __init__(self):
        self.pause_states: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.RLock()
        
    def pause_execution(self, execution_id: str, state: Dict[str, Any], node_name: str, reason: str = "user_request") -> bool:
        """
        Pause workflow execution and store complete state in memory
        
        Args:
            execution_id: Unique execution identifier
            state: Complete workflow state
            node_name: Node where pause occurred
            reason: Reason for pause
            
        Returns:
            bool: Success status
        """
        logger.info(f"🔄 [BACKEND-HITL] pause_execution called")
        logger.info(f"📥 [BACKEND-HITL] pause_execution input params: execution_id={execution_id}, node_name={node_name}, reason={reason}")
        logger.info(f"📥 [BACKEND-HITL] pause_execution state keys: {list(state.keys())}")
        
        try:
            with self.lock:
                # Create serializable state snapshot for pause - store complete state
                def make_serializable(obj):
                    """Convert complex objects to serializable format"""
                    if isinstance(obj, dict):
                        return {k: make_serializable(v) for k, v in obj.items()}
                    elif isinstance(obj, (list, tuple)):
                        return [make_serializable(item) for item in obj]
                    elif hasattr(obj, '__dict__'):
                        # For complex objects, extract basic attributes
                        try:
                            return {k: make_serializable(v) for k, v in obj.__dict__.items() 
                                    if not k.startswith('_')}
                        except:
                            return str(obj)
                    else:
                        return obj
                
                # Store the complete state as-is, don't cherry-pick fields
                complete_state = make_serializable(state.copy())
                
                # Ensure critical fields are present
                if "user_input" not in complete_state:
                    complete_state["user_input"] = ""
                if "datasource" not in complete_state:
                    complete_state["datasource"] = {}
                if "query_type" not in complete_state:
                    complete_state["query_type"] = ""
                if "sql_task_type" not in complete_state:
                    complete_state["sql_task_type"] = ""
                
                pause_data = {
                    "execution_id": execution_id,
                    "state": complete_state,  # Store complete state
                    "node_name": node_name,
                    "reason": reason,
                    "paused_at": time.time(),
                    "status": "paused"
                }
                
                logger.info(f"📊 [BACKEND-HITL] pause_execution prepared pause_data keys: {list(pause_data.keys())}")
                logger.info(f"📊 [BACKEND-HITL] pause_execution complete_state keys: {list(complete_state.keys())}")
                
                self.pause_states[execution_id] = pause_data
                logger.info(f"📊 [BACKEND-HITL] pause_execution stored in pause_states for execution {execution_id}")
                logger.info(f"📊 [BACKEND-HITL] pause_execution paused state keys: {list(complete_state.keys())}")
                logger.info(f"📊 [BACKEND-HITL] pause_execution paused query_type: {complete_state.get('query_type', 'NOT_SET')}")
                logger.info(f"📊 [BACKEND-HITL] pause_execution paused sql_task_type: {complete_state.get('sql_task_type', 'NOT_SET')}")
                logger.info(f"📊 [BACKEND-HITL] pause_execution paused datasource: {complete_state.get('datasource', 'NOT_SET')}")
                
                logger.info(f"✅ [BACKEND-HITL] pause_execution completed successfully for execution {execution_id}")
                return True
                
        except Exception as e:
            logger.error(f"❌ [BACKEND-HITL] pause_execution failed: Failed to pause execution {execution_id}: {e}")
            return False
    
    def interrupt_execution(self, execution_id: str, state: Dict[str, Any], node_name: str, reason: str = "user_request") -> bool:
        """
        Interrupt workflow execution and store state in memory
        
        Args:
            execution_id: Unique execution identifier
            state: Complete workflow state
            node_name: Node where interrupt occurred
            reason: Reason for interrupt
            
        Returns:
            bool: Success status
        """
        try:
            with self.lock:
                # Create serializable state snapshot for interrupt - store complete state
                def make_serializable(obj):
                    """Convert complex objects to serializable format"""
                    if isinstance(obj, dict):
                        return {k: make_serializable(v) for k, v in obj.items()}
                    elif isinstance(obj, (list, tuple)):
                        return [make_serializable(item) for item in obj]
                    elif hasattr(obj, '__dict__'):
                        # For complex objects, extract basic attributes
                        try:
                            return {k: make_serializable(v) for k, v in obj.__dict__.items() 
                                    if not k.startswith('_')}
                        except:
                            return str(obj)
                    elif hasattr(obj, 'page_content'):
                        # Handle Document objects from LangChain
                        return {
                            'page_content': getattr(obj, 'page_content', ''),
                            'metadata': getattr(obj, 'metadata', {}),
                            'type': 'Document'
                        }
                    elif hasattr(obj, 'content'):
                        # Handle other content objects
                        return {
                            'content': getattr(obj, 'content', ''),
                            'type': type(obj).__name__
                        }
                    else:
                        return obj
                
                # Store in memory only
                self.pause_states[execution_id] = {
                    "state": make_serializable(state),
                    "node_name": node_name,
                    "reason": reason,
                    "timestamp": time.time(),
                    "status": "interrupted"
                }
                
                logger.info(f"Workflow execution {execution_id} interrupted at node {node_name}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to interrupt execution {execution_id}: {e}")
            return False
    
    def resume_execution(self, execution_id: str, parameters: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Resume paused execution from memory with selective parameter updates
        
        Args:
            execution_id: Unique execution identifier
            parameters: Optional parameter updates (only non-empty values will be applied)
            
        Returns:
            Dict[str, Any]: Restored state or None if not found
        """
        logger.info(f"🔄 [BACKEND-HITL] resume_execution called")
        logger.info(f"📥 [BACKEND-HITL] resume_execution input params: execution_id={execution_id}, parameters={parameters}")
        
        try:
            with self.lock:
                if execution_id not in self.pause_states:
                    logger.warning(f"⚠️ [BACKEND-HITL] resume_execution: No paused execution found for {execution_id}")
                    return None
                
                pause_data = self.pause_states[execution_id]
                state = pause_data["state"].copy()
                
                logger.info(f"📊 [BACKEND-HITL] resume_execution found pause_data for execution {execution_id}")
                logger.info(f"📊 [BACKEND-HITL] resume_execution pause_data keys: {list(pause_data.keys())}")
                logger.info(f"📊 [BACKEND-HITL] resume_execution state keys: {list(state.keys())}")
                
                # Apply parameter updates selectively - only update non-empty values
                if parameters:
                    updated_fields = []
                    for key, value in parameters.items():
                        # Only update if value is not empty/None
                        if value is not None and value != "" and value != [] and value != {}:
                            old_value = state.get(key)
                            state[key] = value
                            updated_fields.append(f"{key}: {old_value} -> {value}")
                    
                    if updated_fields:
                        logger.info(f"📊 [BACKEND-HITL] resume_execution applied selective parameter updates to execution {execution_id}: {', '.join(updated_fields)}")
                    else:
                        logger.info(f"📊 [BACKEND-HITL] resume_execution no valid parameter updates for execution {execution_id} (all values were empty)")
                else:
                    logger.info(f"📊 [BACKEND-HITL] resume_execution no parameters provided for execution {execution_id}")
                
                # Remove from pause states
                del self.pause_states[execution_id]
                logger.info(f"📊 [BACKEND-HITL] resume_execution removed execution {execution_id} from pause_states")
                
                logger.info(f"📊 [BACKEND-HITL] resume_execution resumed state keys: {list(state.keys())}")
                logger.info(f"📊 [BACKEND-HITL] resume_execution resumed query_type: {state.get('query_type', 'NOT_SET')}")
                logger.info(f"📊 [BACKEND-HITL] resume_execution resumed sql_task_type: {state.get('sql_task_type', 'NOT_SET')}")
                logger.info(f"📊 [BACKEND-HITL] resume_execution resumed datasource: {state.get('datasource', 'NOT_SET')}")
                
                logger.info(f"✅ [BACKEND-HITL] resume_execution completed successfully for execution {execution_id}")
                return state
                
        except Exception as e:
            logger.error(f"❌ [BACKEND-HITL] resume_execution failed: Failed to resume execution {execution_id}: {e}")
            return None
    
    def restore_interrupt(self, execution_id: str, parameters: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Restore interrupted execution from memory
        
        Args:
            execution_id: Unique execution identifier
            parameters: Optional parameter updates
            
        Returns:
            Dict[str, Any]: Restored state or None if not found
        """
        try:
            with self.lock:
                if execution_id not in self.pause_states:
                    logger.warning(f"No interrupted execution found for {execution_id}")
                    return None
                
                interrupt_data = self.pause_states[execution_id]
                if interrupt_data.get("status") != "interrupted":
                    logger.warning(f"Execution {execution_id} is not in interrupted status")
                    return None
                
                state = interrupt_data["state"]
                
                # Apply parameter updates if provided
                if parameters:
                    state.update(parameters)
                    logger.info(f"Applied parameter updates to interrupted execution {execution_id}")
                
                # Remove from memory after restoration
                del self.pause_states[execution_id]
                
                logger.info(f"Workflow execution {execution_id} restored from interrupt")
                return state
                
        except Exception as e:
            logger.error(f"Failed to restore execution {execution_id}: {e}")
            return None
    
    def cancel_execution(self, execution_id: str, execution_type: str = "pause") -> bool:
        """
        Cancel paused or interrupted execution
        
        Args:
            execution_id: Unique execution identifier
            execution_type: "pause" or "interrupt"
            
        Returns:
            bool: Success status
        """
        try:
            with self.lock:
                if execution_id in self.pause_states:
                    del self.pause_states[execution_id]
                    logger.info(f"Cancelled {execution_type} execution {execution_id}")
                    return True
                else:
                    logger.warning(f"No {execution_type} execution found for {execution_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to cancel execution {execution_id}: {e}")
            return False
    
    def get_pause_state(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get paused execution state from memory"""
        with self.lock:
            return self.pause_states.get(execution_id)
    
    def get_interrupt_state(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get interrupted execution state from memory"""
        with self.lock:
            if execution_id in self.pause_states:
                interrupt_data = self.pause_states[execution_id]
                if interrupt_data.get("status") == "interrupted":
                    return interrupt_data
            return None
    
    def list_paused_executions(self) -> List[Dict[str, Any]]:
        """List all paused executions"""
        with self.lock:
            return list(self.pause_states.values())
    
    def list_interrupted_executions(self) -> List[Dict[str, Any]]:
        """List all interrupted executions from memory"""
        with self.lock:
            interrupted_executions = []
            for execution_id, pause_data in self.pause_states.items():
                if pause_data.get("status") == "interrupted":
                    interrupted_executions.append({
                        "execution_id": execution_id,
                        "user_input": pause_data["state"].get("user_input", ""),
                        "node_name": pause_data.get("node_name", ""),
                        "reason": pause_data.get("reason", ""),
                        "created_at": pause_data.get("timestamp", time.time()),
                        "status": pause_data.get("status", ""),
                        "id": execution_id  # Use execution_id as id for memory storage
                    })
            return interrupted_executions
    
    def cleanup_old_states(self, max_age_hours: int = 24):
        """Clean up old paused states from memory"""
        try:
            with self.lock:
                # Clean up old paused states
                current_time = time.time()
                to_remove = []
                
                for execution_id, pause_data in self.pause_states.items():
                    paused_at = pause_data.get("paused_at", current_time)
                    age_hours = (current_time - paused_at) / 3600
                    
                    if age_hours > max_age_hours:
                        to_remove.append(execution_id)
                
                for execution_id in to_remove:
                    del self.pause_states[execution_id]
                    logger.info(f"Cleaned up old paused execution {execution_id}")
                    
        except Exception as e:
            logger.error(f"Failed to cleanup old states: {e}")


# Global instance
hitl_state_manager = HITLStateManager()
