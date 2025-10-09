import { useEffect, useRef, useCallback, useState } from 'react';
import { useDispatch } from 'react-redux';
import { v4 as uuidv4 } from 'uuid';
import {
  setConnectionStatus,
  setConnectionError,
  clearError,
  startExecution,
  completeExecution,
  errorExecution,
  startNode,
  completeNode,
  streamToken,
  errorNode,
  activateEdge,
  openHITLPanel,
  updateHITLExecutionState,
} from '../store/workflowSlice';

const useWorkflowWebSocket = () => {
  const dispatch = useDispatch();
  const websocketRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;
  const reconnectDelay = 2000;
  
  const [clientId] = useState(() => uuidv4());

  const getWebSocketUrl = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    return `${protocol}//${host}/ws/workflow/${clientId}`;
  }, [clientId]);
  
  const getClientId = useCallback(() => {
    return clientId;
  }, [clientId]);

  const handleMessage = useCallback((event) => {
    try {
      const data = JSON.parse(event.data);
      console.log('WebSocket message received:', data);
      console.log('Message type:', data.type, 'Execution ID:', data.execution_id);

      switch (data.type) {
        case 'execution_started':
          dispatch(startExecution({
            executionId: data.execution_id,
            query: data.data?.query || 'Unknown query',
            timestamp: data.timestamp
          }));
          break;

        case 'node_started':
          dispatch(startNode({
            executionId: data.execution_id,
            nodeId: data.node_id,
            timestamp: data.timestamp,
            nodeType: data.data?.node_type
          }));
          break;

        case 'node_completed':
          dispatch(completeNode({
            executionId: data.execution_id,
            nodeId: data.node_id,
            timestamp: data.timestamp,
            output: data.data?.output
          }));
          break;

        case 'token_stream':
          // Handle token-level streaming
          dispatch(streamToken({
            executionId: data.execution_id,
            token: data.token,
            nodeId: data.node_id,
            stream_complete: data.stream_complete
          }));
          break;

        case 'node_error':
          dispatch(errorNode({
            executionId: data.execution_id,
            nodeId: data.node_id,
            timestamp: data.timestamp,
            error: data.error
          }));
          break;

        case 'edge_activated':
          dispatch(activateEdge({
            executionId: data.execution_id,
            from: data.from,
            to: data.to,
          }));
          break;

        case 'execution_completed':
          console.log('Execution completed successfully:', data);
          console.log('Final state data keys:', data.data ? Object.keys(data.data) : 'no data');
          console.log('Final state data:', data.data);
          
          // Dispatch completion with final state
          dispatch(completeExecution({
            executionId: data.execution_id,
            timestamp: data.timestamp,
            summary: data.data, // Pass the whole final state as summary
            keepActive: true // New flag to indicate we want to keep the execution active
          }));
          break;

        case 'execution_error':
          console.log('Execution error:', data);
          dispatch(errorExecution({
            executionId: data.execution_id,
            timestamp: data.timestamp,
            error: data.error
          }));
          break;

        case 'pong':
          console.log('Received pong from server');
          break;

        // HITL message handlers
        case 'hitl_paused':
          console.log('🔄 [FRONTEND-WS] hitl_paused message received');
          console.log('📥 [FRONTEND-WS] hitl_paused data:', data);
          console.log('📍 [FRONTEND-WS] hitl_paused current_state:', data.current_state);
          
          dispatch(updateHITLExecutionState({
            executionId: data.execution_id,
            hitlStatus: 'paused',
            nodeName: data.node_name,
            reason: data.reason,
            currentState: data.current_state
          }));
          
          // Stop loading state when paused
          dispatch(setLoading(false));
          console.log('✅ [FRONTEND-WS] hitl_paused processing completed');
          break;

        case 'hitl_interrupted':
          console.log('🚫 Execution interrupted:', data);
          console.log('📍 Current state:', data.current_state);
          dispatch(updateHITLExecutionState({
            executionId: data.execution_id,
            hitlStatus: 'interrupted',
            nodeName: data.node_name,
            reason: data.reason
          }));
          dispatch(openHITLPanel({
            executionId: data.execution_id,
            nodeName: data.node_name,
            executionType: 'interrupt',
            currentState: data.current_state
          }));
          console.log('✅ HITL interrupt panel action dispatched');
          break;

        case 'hitl_resumed':
          console.log('🔄 [FRONTEND-WS] hitl_resumed message received');
          console.log('📥 [FRONTEND-WS] hitl_resumed data:', data);
          
          dispatch(updateHITLExecutionState({
            executionId: data.execution_id,
            hitlStatus: 'resumed',
            nodeName: data.node_name,
            reason: 'resumed'
          }));
          
          console.log('✅ [FRONTEND-WS] hitl_resumed processing completed');
          break;

        case 'hitl_cancelled':
          console.log('Execution cancelled:', data);
          dispatch(updateHITLExecutionState({
            executionId: data.execution_id,
            hitlStatus: 'cancelled',
            nodeName: data.node_name,
            reason: 'cancelled'
          }));
          break;

        default:
          console.log('Unknown message type:', data.type);
      }
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  }, [dispatch]);

  const handleOpen = useCallback(() => {
    console.log('WebSocket connected with client_id:', clientId);
    dispatch(setConnectionStatus('connected'));
    dispatch(clearError());
    reconnectAttemptsRef.current = 0;
  }, [clientId, dispatch]);

  const handleClose = useCallback((event) => {
    console.warn('WebSocket disconnected.', event.reason);
    dispatch(setConnectionStatus('disconnected'));
    
    if (event.code !== 1000 && reconnectAttemptsRef.current < maxReconnectAttempts) {
      reconnectAttemptsRef.current += 1;
      console.log(`Attempting to reconnect (${reconnectAttemptsRef.current}/${maxReconnectAttempts})...`);
      reconnectTimeoutRef.current = setTimeout(() => connect(), reconnectDelay * reconnectAttemptsRef.current);
    }
  }, [dispatch, maxReconnectAttempts, reconnectDelay]);

  const handleError = useCallback((event) => {
    console.error('WebSocket error:', event);
    dispatch(setConnectionError('WebSocket connection error.'));
  }, [dispatch]);

  const connect = useCallback(() => {
    if (websocketRef.current && websocketRef.current.readyState === WebSocket.OPEN) {
      console.log('WebSocket is already connected.');
      return;
    }

    dispatch(setConnectionStatus('connecting'));
    const url = getWebSocketUrl();
    console.log('Connecting to WebSocket:', url);
    websocketRef.current = new WebSocket(url);

    websocketRef.current.onopen = handleOpen;
    websocketRef.current.onmessage = handleMessage;
    websocketRef.current.onclose = handleClose;
    websocketRef.current.onerror = handleError;
  }, [getWebSocketUrl, handleOpen, handleMessage, handleClose, handleError, dispatch]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (websocketRef.current) {
      websocketRef.current.close(1000, 'User disconnected');
      websocketRef.current = null;
    }
    dispatch(setConnectionStatus('disconnected'));
  }, [dispatch]);

  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  const sendMessage = useCallback((message) => {
    if (websocketRef.current && websocketRef.current.readyState === WebSocket.OPEN) {
        websocketRef.current.send(JSON.stringify(message));
    } else {
        console.error('WebSocket is not connected.');
    }
  }, []);

  // HITL control functions
  const interruptExecution = useCallback((nodeName, executionId) => {
    const message = {
      type: 'hitl_interrupt',
      execution_id: executionId,
      node_name: nodeName,
      reason: 'user_request',
      timestamp: new Date().toISOString()
    };
    console.log('Sending HITL interrupt message:', message);
    sendMessage(message);
  }, [sendMessage]);

  const resumeExecution = useCallback((executionId, parameters, executionType) => {
    console.log('🔄 [FRONTEND-WS] resumeExecution called');
    console.log('📥 [FRONTEND-WS] resumeExecution input params:', { executionId, parameters, executionType });
    
    const message = {
      type: 'hitl_resume',
      execution_id: executionId,
      execution_type: executionType,
      parameters: parameters,
      timestamp: new Date().toISOString()
    };
    
    console.log('📤 [FRONTEND-WS] resumeExecution sending message:', message);
    sendMessage(message);
    console.log('✅ [FRONTEND-WS] resumeExecution message sent successfully');
  }, [sendMessage]);

  const cancelExecution = useCallback((executionId, executionType) => {
    sendMessage({
      type: 'hitl_cancel',
      execution_id: executionId,
      execution_type: executionType,
      timestamp: new Date().toISOString()
    });
  }, [sendMessage]);

  return { 
    getClientId, 
    sendMessage, 
    interruptExecution,
    resumeExecution, 
    cancelExecution 
  };
};

export default useWorkflowWebSocket; 