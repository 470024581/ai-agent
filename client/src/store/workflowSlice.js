import { createSlice, createSelector } from '@reduxjs/toolkit';
import { v4 as uuidv4 } from 'uuid';

const initialState = {
  connectionStatus: 'disconnected', // 'connected', 'disconnected', 'connecting', 'error'
  error: null,
  currentExecution: null, // ID of the currently active execution
  executions: {}, // Store all execution data, keyed by ID
  executionHistory: [], // Array of execution summaries for history panel
};

const workflowSlice = createSlice({
  name: 'workflow',
  initialState,
  reducers: {
    setConnectionStatus: (state, action) => {
      state.connectionStatus = action.payload;
    },
    setConnectionError: (state, action) => {
      state.error = action.payload;
      state.connectionStatus = 'error';
    },
    clearError: (state) => {
      state.error = null;
    },
    startExecution: (state, action) => {
      const { executionId, query, timestamp } = action.payload;
      const id = executionId || uuidv4(); // Use server ID if provided, fallback to generated ID
      state.currentExecution = id;
      const newExecution = {
        id: id,
        query,
        status: 'running',
        startTime: timestamp || Date.now(),
        endTime: null,
        nodes: {},
        activeEdges: [],
        currentNode: null,
      };
      state.executions[id] = newExecution;
      
      // Add to history
      state.executionHistory.unshift({
        id: id,
        query,
        status: 'running',
        timestamp: newExecution.startTime,
        error: null,
        endTime: null,
      });
    },
    completeExecution: (state, action) => {
        const { executionId, summary } = action.payload;
        if (state.executions[executionId]) {
            const execution = state.executions[executionId];
            execution.status = 'completed';
            execution.endTime = Date.now();
            execution.result = summary; // Store the execution result
            
            const historyItem = state.executionHistory.find(h => h.id === executionId);
            if (historyItem) {
                historyItem.status = 'completed';
                historyItem.endTime = execution.endTime;
            }
        }
        // Don't clear currentExecution or currentNode immediately - let user see the result
        // Keep the final state visible for completed executions
        // state.currentExecution = null;
        // state.currentNode = null; // Keep this to show final execution state
    },
    errorExecution: (state, action) => {
        const { executionId, error } = action.payload;
        if (state.executions[executionId]) {
            const execution = state.executions[executionId];
            execution.status = 'error';
            execution.endTime = Date.now();
            execution.error = error;

            const historyItem = state.executionHistory.find(h => h.id === executionId);
            if (historyItem) {
                historyItem.status = 'error';
                historyItem.error = error;
                historyItem.endTime = execution.endTime;
            }
        }
        if (state.currentExecution === executionId) {
            state.currentExecution = null;
            state.currentNode = null;
        }
    },
    startNode: (state, action) => {
        const { executionId, nodeId, nodeType } = action.payload;
        if (state.executions[executionId]) {
            const execution = state.executions[executionId];
            execution.currentNode = nodeId;
            execution.nodes[nodeId] = {
                id: nodeId,
                nodeType: nodeType || 'unknown',
                status: 'running',
                startTime: Date.now(),
                endTime: null,
                duration: null,
                input: null,
                output: null,
                error: null,
                retryCount: 0,
            };
        }
    },
    completeNode: (state, action) => {
        const { executionId, nodeId, output } = action.payload;
        if (state.executions[executionId]?.nodes[nodeId]) {
            const node = state.executions[executionId].nodes[nodeId];
            node.status = 'completed';
            node.endTime = Date.now();
            node.duration = (node.endTime - node.startTime) / 1000;
            node.output = output;
        }
    },
    errorNode: (state, action) => {
        const { executionId, nodeId, error } = action.payload;
        if (state.executions[executionId]?.nodes[nodeId]) {
            const node = state.executions[executionId].nodes[nodeId];
            node.status = 'error';
            node.endTime = Date.now();
            node.duration = (node.endTime - node.startTime) / 1000;
            node.error = error;
        }
    },
    activateEdge: (state, action) => {
      const { executionId, from, to } = action.payload;
      if (state.executions[executionId]) {
        state.executions[executionId].activeEdges.push({ from, to });
      }
    },
    clearActiveEdges: (state, action) => {
        const { executionId } = action.payload;
        if (state.executions[executionId]) {
            state.executions[executionId].activeEdges = [];
        }
    },
    resetCurrentExecution: (state) => {
      // Don't clear the previous execution data - just reset current pointer
      // The previous execution data will be preserved for viewing
      state.currentExecution = null;
    },
    resetAllStates: () => initialState,
    clearExecutionHistory: (state) => {
      state.executionHistory = [];
      state.executions = {};
      state.currentExecution = null;
    },
    removeExecution: (state, action) => {
        const executionIdToRemove = action.payload;
        state.executionHistory = state.executionHistory.filter(
            (item) => item.id !== executionIdToRemove
        );
        delete state.executions[executionIdToRemove];
        if (state.currentExecution === executionIdToRemove) {
            state.currentExecution = null;
        }
    },
  },
});

export const {
  setConnectionStatus,
  setConnectionError,
  clearError,
  startExecution,
  completeExecution,
  errorExecution,
  startNode,
  completeNode,
  errorNode,
  activateEdge,
  clearActiveEdges,
  resetCurrentExecution,
  resetAllStates,
  clearExecutionHistory,
  removeExecution,
} = workflowSlice.actions;

// Selectors
export const selectConnectionStatus = (state) => state.workflow.connectionStatus;
export const selectCurrentExecution = (state) => state.workflow.currentExecution;

export const selectCurrentExecutionData = (state) => {
  const currentId = state.workflow.currentExecution;
  return currentId ? state.workflow.executions[currentId] : null;
};

export const selectNodeStates = (state) => state.workflow.nodeStates;
export const selectCurrentNode = (state) => {
  const currentId = state.workflow.currentExecution;
  return currentId ? state.workflow.executions[currentId]?.currentNode : null;
};
export const selectActiveEdges = (state) => {
  const currentId = state.workflow.currentExecution;
  return currentId ? state.workflow.executions[currentId]?.activeEdges || [] : [];
};
export const selectExecutionHistory = (state) => state.workflow.executionHistory;
export const selectWorkflowError = (state) => state.workflow.error;

// Selector with parameter
export const selectExecutionById = (executionId) => (state) => 
  state.workflow.executions[executionId] || null;

export const selectNodeById = (executionId, nodeId) => (state) => 
  state.workflow.executions[executionId]?.nodes[nodeId] || null;

// Memoized selectors for performance
const selectExecutions = (state) => state.workflow.executions;
const selectCurrentExecutionId = (state) => state.workflow.currentExecution;

export const selectMemoizedCurrentExecution = createSelector(
  [selectExecutions, selectCurrentExecutionId],
  (executions, currentId) => (currentId ? executions[currentId] : null)
);

export const selectMemoizedNodeStates = createSelector(
  [selectExecutions, selectCurrentExecutionId],
  (executions, currentId) => {
    // If there's a current execution, use it
    let targetExecution = currentId ? executions[currentId] : null;
    
    // If no current execution, use the most recent completed execution
    if (!targetExecution) {
      const executionEntries = Object.entries(executions);
      if (executionEntries.length > 0) {
        // Sort by creation time and get the most recent one
        const sortedExecutions = executionEntries.sort(([, a], [, b]) => 
          (b.startTime || 0) - (a.startTime || 0)
        );
        targetExecution = sortedExecutions[0][1];
      }
    }
    
    if (!targetExecution) return {};
    
    const states = {};
    if (targetExecution.nodes) {
      Object.values(targetExecution.nodes).forEach(node => {
        states[node.id] = node.status;
      });
    }
    return states;
  }
);

export const selectMemoizedCurrentNode = createSelector(
  [selectExecutions, selectCurrentExecutionId],
  (executions, currentId) => {
    // Show current node for both active and completed executions
    let targetExecution = currentId && executions[currentId] ? executions[currentId] : null;
    
    // If no current execution, get the most recent one to show its final state
    if (!targetExecution) {
      const executionEntries = Object.entries(executions);
      if (executionEntries.length > 0) {
        const sortedExecutions = executionEntries.sort(([, a], [, b]) => 
          (b.startTime || 0) - (a.startTime || 0)
        );
        targetExecution = sortedExecutions[0][1];
      }
    }
    
    return targetExecution?.currentNode || null;
  }
);

export const selectMemoizedActiveEdges = createSelector(
  [selectExecutions, selectCurrentExecutionId],
  (executions, currentId) => {
    // Show active edges for both active and completed executions
    let targetExecution = currentId && executions[currentId] ? executions[currentId] : null;
    
    // If no current execution, get the most recent one to show its final edges
    if (!targetExecution) {
      const executionEntries = Object.entries(executions);
      if (executionEntries.length > 0) {
        const sortedExecutions = executionEntries.sort(([, a], [, b]) => 
          (b.startTime || 0) - (a.startTime || 0)
        );
        targetExecution = sortedExecutions[0][1];
      }
    }
    
    return targetExecution?.activeEdges || [];
  }
);

export const selectCurrentExecutionResult = createSelector(
  [selectExecutions, selectCurrentExecutionId],
  (executions, currentId) => {
    // If there's a current execution, use its result
    let targetExecution = currentId ? executions[currentId] : null;
    
    // If no current execution, use the most recent completed execution's result
    if (!targetExecution) {
      const executionEntries = Object.entries(executions);
      if (executionEntries.length > 0) {
        // Sort by creation time and get the most recent one
        const sortedExecutions = executionEntries.sort(([, a], [, b]) => 
          (b.startTime || 0) - (a.startTime || 0)
        );
        targetExecution = sortedExecutions[0][1];
      }
    }
    
    return targetExecution?.result || null;
  }
);

export default workflowSlice.reducer;