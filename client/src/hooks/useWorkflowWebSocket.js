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

  return { getClientId, sendMessage };
};

export default useWorkflowWebSocket; 