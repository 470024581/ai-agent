"""
Custom exceptions for HITL (Human-in-the-Loop) functionality
"""

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
