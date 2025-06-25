import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { 
  FaBrain, 
  FaProjectDiagram, 
  FaDatabase, 
  FaChartLine, 
  FaLightbulb, 
  FaCode,
  FaComments,
  FaPaperPlane,
  FaSpinner,
  FaExclamationTriangle,
  FaCheck,
  FaArrowRight,
  FaSearch,
  FaFileAlt,
  FaRobot,
  FaClock,
  FaRoute,
  FaCogs,
  FaCheckCircle,
  FaRedo,
  FaPlay,
  FaStop,
} from 'react-icons/fa';
import { FaWifi } from 'react-icons/fa6';
import { TbWifiOff } from 'react-icons/tb';
import useWorkflowWebSocket from '../hooks/useWorkflowWebSocket';
import {
  selectConnectionStatus,
  selectCurrentNode,
  selectActiveEdges,
  selectCurrentExecutionData,
  resetCurrentExecution,
  selectMemoizedNodeStates,
  selectCurrentExecutionResult,
  startExecution,
} from '../store/workflowSlice';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Alert, AlertDescription } from './ui/alert';
import { Spinner } from './ui/spinner';
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from './ui/collapsible';
import { ChevronsUpDown } from 'lucide-react';

function IntelligentAnalysis() {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  
  // Local state
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [activeDataSource, setActiveDataSource] = useState(null);
  const [availableDataSources, setAvailableDataSources] = useState([]);
  const [executionId, setExecutionId] = useState(null);
  
  // Redux state
  const connectionStatus = useSelector(selectConnectionStatus);
  const reduxNodeStates = useSelector(selectMemoizedNodeStates);
  const currentNode = useSelector(selectCurrentNode);
  const activeEdges = useSelector(selectActiveEdges);
  const currentExecutionData = useSelector(selectCurrentExecutionData);
  const currentExecutionNodes = currentExecutionData?.nodes || {};
  const executionResult = useSelector(selectCurrentExecutionResult);
  
  // WebSocket connection
  const { 
    getClientId,
  } = useWorkflowWebSocket();
  
  // LangGraph nodes and edges definition - complete flow with start and end nodes
  const langGraphNodes = [
    { id: 'start_node', name: 'Start', type: 'start', position: { x: 200, y: 20 }, description: 'Begin analysis process' },
    { id: 'router_node', name: 'Router', type: 'decision', position: { x: 300, y: 100 }, description: 'Determine SQL or RAG path' },
    { id: 'sql_classifier_node', name: 'SQL Classifier', type: 'process', position: { x: 150, y: 180 }, description: 'Classify as query or chart' },
    { id: 'rag_query_node', name: 'RAG Query', type: 'process', position: { x: 450, y: 180 }, description: 'Vector search & retrieval' },
    { id: 'sql_execution_node', name: 'SQL Execution', type: 'process', position: { x: 150, y: 280 }, description: 'Execute database query' },
    { id: 'chart_config_node', name: 'Chart Config', type: 'process', position: { x: 50, y: 380 }, description: 'Generate chart configuration' },
    { id: 'chart_rendering_node', name: 'Chart Render', type: 'process', position: { x: 190, y: 380 }, description: 'Call QuickChart API' },
    { id: 'llm_processing_node', name: 'LLM Process', type: 'process', position: { x: 300, y: 400 }, description: 'Generate natural language response' },
    { id: 'retry_node', name: 'Retry', type: 'retry', position: { x: 150, y: 500 }, description: 'Retry with improvements' },
    { id: 'validation_node', name: 'Validation', type: 'validation', position: { x: 300, y: 600 }, description: 'Quality score validation' },
    { id: 'end_node', name: 'End', type: 'end', position: { x: 200, y: 680 }, description: 'Process completed' }
  ];

  const langGraphEdges = [
    { from: 'start_node', to: 'router_node', condition: 'Start Process', color: '#22c55e' },
    { from: 'router_node', to: 'sql_classifier_node', condition: 'SQL Path', color: '#3b82f6' },
    { from: 'router_node', to: 'rag_query_node', condition: 'RAG Path', color: '#8b5cf6' },
    { from: 'sql_classifier_node', to: 'sql_execution_node', condition: 'Both Paths', color: '#10b981' },
    { from: 'sql_execution_node', to: 'chart_config_node', condition: 'Chart Type', color: '#f59e0b' },
    { from: 'sql_execution_node', to: 'llm_processing_node', condition: 'Query Type', color: '#10b981' },
    { from: 'chart_config_node', to: 'chart_rendering_node', condition: 'Chart Config', color: '#f59e0b' },
    { from: 'chart_rendering_node', to: 'llm_processing_node', condition: 'Chart URL', color: '#f59e0b' },
    { from: 'rag_query_node', to: 'llm_processing_node', condition: 'RAG Result', color: '#8b5cf6' },
    { from: 'llm_processing_node', to: 'validation_node', condition: 'Generated Response', color: '#6b7280' },
    { from: 'validation_node', to: 'retry_node', condition: 'Score < 8', color: '#ef4444' },
    { from: 'retry_node', to: 'llm_processing_node', condition: 'Retry Attempt', color: '#ef4444' },
    { from: 'validation_node', to: 'end_node', condition: 'Score >= 8', color: '#22c55e' }
  ];

  // Legacy state for backward compatibility (will be removed)
  const [localNodeStates, setLocalNodeStates] = useState({});
  
  // Local state for expanded node details
  const [expandedNodeId, setExpandedNodeId] = useState(null);

  // Initialize node states for fallback
  useEffect(() => {
    const initialStates = {};
    langGraphNodes.forEach(node => {
      initialStates[node.id] = 'pending';
    });
    setLocalNodeStates(initialStates);
  }, []);
  
  // Listen for execution result from WebSocket
  useEffect(() => {
    console.log('ExecutionResult changed:', executionResult);
    if (executionResult) {
      console.log('Setting result from WebSocket execution result:', executionResult);
      console.log('Result keys:', Object.keys(executionResult));
      setResult(executionResult);
      setLoading(false);
    }
  }, [executionResult]);
  
  // Handler for node click
  const handleNodeClick = (nodeId) => {
    if (currentExecutionNodes[nodeId]) {
      setExpandedNodeId(expandedNodeId === nodeId ? null : nodeId);
    }
  };
  
  const handleSelectExecution = (executionId) => {
    // Switch to viewing historical execution
    console.log('Selecting execution for view:', executionId);
  };
  
  const handleReplayExecution = (query) => {
    // Set the query and clear current execution
    setQuery(query);
    dispatch(resetCurrentExecution());
    // User can then submit to execute
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!activeDataSource) {
      setError(t('intelligentAnalysis.noDataSourceError'));
      return;
    }
    if (!query.trim()) {
      setError(t('intelligentAnalysis.enterQueryError'));
      return;
    }

    // Check WebSocket connection status
    if (connectionStatus !== 'connected') {
      setError('WebSocket连接未建立，请等待连接后重试');
      return;
    }

    setLoading(true);
    setError('');
    setResult(null);
    
    // Reset previous execution states
    dispatch(resetCurrentExecution());

    try {
      const response = await fetch('/api/v1/intelligent-analysis', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: query.trim(),
          datasource_id: activeDataSource.id,
          client_id: getClientId(),
        }),
      });

      if (!response.ok) {
        throw new Error(t('intelligentAnalysis.networkError'));
      }

      const data = await response.json();
      // Don't set result immediately - wait for WebSocket execution_completed event
      // setResult(data);
      
      // Set execution ID for WebSocket connection and start execution tracking
      if (data.execution_id) {
        setExecutionId(data.execution_id);
        // Start execution tracking in Redux even if WebSocket message hasn't arrived yet
        dispatch(startExecution({
          executionId: data.execution_id,
          query: query.trim(),
          timestamp: Date.now()
        }));
      }
      
    } catch (error) {
      setError(error.message);
      setLoading(false);
    }
    // Don't set loading to false in finally block - wait for WebSocket completion or error
  };

  const handleExampleClick = (exampleQuery) => {
    setQuery(exampleQuery);
  };

  const getNodeIcon = (node, status) => {
    const baseClass = "h-4 w-4";
    
    switch (status) {
      case 'running':
        return <FaSpinner className={`animate-spin ${baseClass} text-blue-500`} />;
      case 'completed':
        return <FaCheck className={`${baseClass} text-green-500`} />;
      case 'error':
        return <FaExclamationTriangle className={`${baseClass} text-red-500`} />;
      default:
        // Show different icons based on node type
        switch (node.type) {
          case 'start':
            return <FaPlay className={`${baseClass} text-gray-400`} />;
          case 'end':
            return <FaStop className={`${baseClass} text-gray-400`} />;
          case 'decision':
            return <FaRoute className={`${baseClass} text-gray-400`} />;
          case 'process':
            return <FaCogs className={`${baseClass} text-gray-400`} />;
          case 'validation':
            return <FaCheckCircle className={`${baseClass} text-gray-400`} />;
          case 'retry':
            return <FaRedo className={`${baseClass} text-gray-400`} />;
          default:
            return <FaClock className={`${baseClass} text-gray-400`} />;
        }
    }
  };

  const getNodeClass = (status, isCurrentNode) => {
    let baseClass = 'p-3 rounded-lg border-2 transition-all duration-300 relative ';
    
    if (isCurrentNode) {
      baseClass += 'ring-2 ring-offset-2 ring-blue-300 ';
    }
    
    switch (status) {
      case 'running':
        return baseClass + 'border-blue-400 bg-blue-50 dark:bg-blue-950 shadow-lg';
      case 'completed':
        return baseClass + 'border-green-400 bg-green-50 dark:bg-green-950 shadow-md';
      case 'error':
        return baseClass + 'border-red-400 bg-red-50 dark:bg-red-950 shadow-md';
      default:
        return baseClass + 'border-gray-200 bg-gray-50 dark:bg-gray-800 opacity-60';
    }
  };

  const renderLangGraphDiagram = () => {
    const nodeStates = reduxNodeStates || localNodeStates;
    const currentActiveNode = currentNode || null;
    const currentActiveEdges = activeEdges || [];

    return (
      <div className="w-full">
        <h6 className="font-bold text-blue-600 mb-4 flex items-center text-lg">
          <FaProjectDiagram className="mr-2 h-5 w-5" />
          {t('intelligentAnalysis.langGraphProcess')}
          
          {/* Connection Status */}
          <div className="ml-4 flex items-center">
            {connectionStatus === 'connected' ? (
              <div className="flex items-center text-green-600">
                <FaWifi className="h-3 w-3 mr-1" />
                <span className="text-xs">{t('intelligentAnalysis.connectionStatus.connected')}</span>
              </div>
            ) : connectionStatus === 'connecting' ? (
              <div className="flex items-center text-yellow-600">
                <FaSpinner className="h-3 w-3 mr-1 animate-spin" />
                <span className="text-xs">{t('intelligentAnalysis.connectionStatus.connecting')}</span>
              </div>
            ) : connectionStatus === 'error' ? (
              <div className="flex items-center text-red-600">
                <TbWifiOff className="h-3 w-3 mr-1" />
                <span className="text-xs">{t('intelligentAnalysis.connectionStatus.error')}</span>
              </div>
            ) : (
              <div className="flex items-center text-gray-400">
                <TbWifiOff className="h-3 w-3 mr-1" />
                <span className="text-xs">{t('intelligentAnalysis.connectionStatus.disconnected')}</span>
              </div>
            )}
          </div>
          
          {/* Current Node */}
          {currentActiveNode && (
            <Badge className="ml-3 bg-blue-100 text-blue-800 text-xs">
              Running: {langGraphNodes.find(n => n.id === currentActiveNode)?.name}
            </Badge>
          )}
          
          {/* Execution ID */}
          {executionId && (
            <Badge className="ml-2 bg-gray-100 text-gray-600 text-xs font-mono">
              {executionId.substring(0, 8)}...
            </Badge>
          )}
        </h6>
        
        {/* Flowchart layout */}
        <div className="relative bg-white dark:bg-gray-900 rounded-lg p-6 border h-full min-h-[800px] overflow-hidden">
                      {/* Render connection lines */}
          <svg className="absolute inset-0 w-full h-full z-0 pointer-events-none" preserveAspectRatio="none">
            <defs>
              {/* Arrow marker definitions - fix display issues */}
              <marker id="arrowhead" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
                <path d="M0,0 L0,6 L9,3 z" fill="#d1d5db" />
              </marker>
              <marker id="arrowhead-active" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
                <path d="M0,0 L0,6 L9,3 z" fill="#3b82f6" />
              </marker>
              
              {/* Different colored arrow markers */}
              <marker id="arrowhead-green" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
                <path d="M0,0 L0,6 L9,3 z" fill="#22c55e" />
              </marker>
              <marker id="arrowhead-purple" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
                <path d="M0,0 L0,6 L9,3 z" fill="#8b5cf6" />
              </marker>
              <marker id="arrowhead-orange" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
                <path d="M0,0 L0,6 L9,3 z" fill="#f59e0b" />
              </marker>
              <marker id="arrowhead-red" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
                <path d="M0,0 L0,6 L9,3 z" fill="#ef4444" />
              </marker>
              <marker id="arrowhead-blue" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
                <path d="M0,0 L0,6 L9,3 z" fill="#10b981" />
              </marker>
            </defs>
            {langGraphEdges.map((edge, index) => {
              const fromNode = langGraphNodes.find(n => n.id === edge.from);
              const toNode = langGraphNodes.find(n => n.id === edge.to);
              if (!fromNode || !toNode) return null;
              
              const isActive = currentActiveEdges.some(ae => ae.from === edge.from && ae.to === edge.to);
              
              // Node parameter definitions
              const nodeRadius = 24; // Circular node radius (node is 48x48px)
              const arrowLength = 10; // Arrow length (consistent with marker definition)
              
              // Calculate node center coordinates (SVG coordinates now directly match HTML coordinates)
              // position is node top-left corner, add radius to get center
              const fromCenterX = fromNode.position.x + nodeRadius;
              const fromCenterY = fromNode.position.y + nodeRadius;
              const toCenterX = toNode.position.x + nodeRadius;
              const toCenterY = toNode.position.y + nodeRadius;
              
              // Calculate vector and distance between two centers
              const deltaX = toCenterX - fromCenterX;
              const deltaY = toCenterY - fromCenterY;
              const centerDistance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
              
              // Skip connections that are too close (avoid overlapping nodes)
              if (centerDistance < nodeRadius * 2) return null;
              
              // Calculate normalized direction vector (unit vector)
              const directionX = deltaX / centerDistance;
              const directionY = deltaY / centerDistance;
              
              // Connection line from source node edge to target node edge, avoiding node occlusion
              // Start point: extend from source node center towards target to circle edge
              const startX = fromCenterX + directionX * nodeRadius;
              const startY = fromCenterY + directionY * nodeRadius;
              
              // End point: retract from target node center towards source to circle edge
              const endX = toCenterX - directionX * nodeRadius;
              const endY = toCenterY - directionY * nodeRadius;
              
              // Calculate actual connection line length (for label display judgment)
              const lineLength = Math.sqrt((endX - startX) * (endX - startX) + (endY - startY) * (endY - startY));
              
              // Connection line explanation:
              // 1. Connection line points from source node circle edge to target node circle edge
              // 2. Direction based on straight line between two centers
              // 3. startX, startY = point on source node circle facing target
              // 4. endX, endY = point on target node circle facing source
              // 5. Arrow displays at target node edge, won't be occluded by node
              
              // Connection line length = center distance - two radii
              
              // Select corresponding arrow marker based on edge color
              const getArrowMarker = (color, isActive) => {
                if (!isActive) return "url(#arrowhead)";
                
                // Precisely match edge color to corresponding arrow
                switch (color) {
                  case '#22c55e': // Green (start flow)
                    return "url(#arrowhead-green)";
                  case '#8b5cf6': // Purple (RAG path)
                    return "url(#arrowhead-purple)";
                  case '#f59e0b': // Orange (chart configuration)
                    return "url(#arrowhead-orange)";
                  case '#ef4444': // Red (retry flow)
                    return "url(#arrowhead-red)";
                  case '#10b981': // Teal (SQL execution)
                    return "url(#arrowhead-blue)";
                  case '#3b82f6': // Blue (SQL path)
                  case '#6b7280': // Gray (LLM processing)
                  default:
                    return "url(#arrowhead-active)";
                }
              };

              return (
                <g key={index}>
                  {/* Connection line - from source node circle to target node circle */}
                  <line
                    x1={startX} 
                    y1={startY}
                    x2={endX} 
                    y2={endY}
                    stroke={isActive ? edge.color : '#d1d5db'}
                    strokeWidth={isActive ? 2.5 : 1.5}
                    strokeDasharray={isActive ? "0" : "5,5"}
                    markerEnd={getArrowMarker(edge.color, isActive)}
                    className="transition-all duration-300"
                  />
                  
                  {/* Center-to-center connection line now works properly */}
                  
                  {/* Edge labels - only show when line is long enough and active */}
                  {isActive && lineLength > 80 && (
                    <g>
                      {/* Calculate label position - at connection line midpoint */}
                      {(() => {
                        const labelX = (startX + endX) / 2;
                        const labelY = (startY + endY) / 2;
                        
                                                  return (
                            <>
                              {/* Text label background (white stroke) */}
                            <text
                              x={labelX}
                              y={labelY}
                              fill="white"
                              fontSize="9"
                              textAnchor="middle"
                              className="font-medium"
                              stroke="white"
                              strokeWidth="3"
                              dominantBaseline="middle"
                            >
                              {edge.condition}
                            </text>
                            {/* Text label foreground */}
                            <text
                              x={labelX}
                              y={labelY}
                              fill={edge.color}
                              fontSize="9"
                              textAnchor="middle"
                              className="font-medium"
                              dominantBaseline="middle"
                            >
                              {edge.condition}
                            </text>
                          </>
                        );
                      })()}
                    </g>
                  )}
                </g>
              );
            })}
          </svg>
          
                      {/* Render nodes */}
          {langGraphNodes.map((node) => {
            // Use Redux state if available, fallback to local state
            const status = nodeStates[node.id] || 'pending';
            const isCurrentNode = currentActiveNode === node.id;
            const nodeExecution = currentExecutionData?.nodes[node.id];
            const isExecuted = nodeExecution?.status === 'completed';
            
            // Determine circular node color based on state and node type
            let nodeColor = 'bg-gray-300 border-gray-400'; // pending
            
            // Colors for special node types
            if (node.type === 'start') {
              nodeColor = status === 'completed' ? 'bg-green-500 border-green-600' : 'bg-green-400 border-green-500';
            } else if (node.type === 'end') {
              nodeColor = status === 'completed' ? 'bg-purple-500 border-purple-600' : 'bg-gray-300 border-gray-400';
            } else {
              // Status colors for regular nodes
              if (status === 'running') {
                nodeColor = 'bg-blue-500 border-blue-600 animate-pulse';
              } else if (status === 'completed') {
                nodeColor = 'bg-green-500 border-green-600';
              } else if (status === 'error') {
                nodeColor = 'bg-red-500 border-red-600';
              }
            }
            
            return (
              <div key={node.id} style={{ position: 'absolute', left: `${node.position.x}px`, top: `${node.position.y}px`, zIndex: 10 }}>
                {/* Circular node */}
                <div 
                  className={`w-12 h-12 rounded-full border-2 ${nodeColor} flex items-center justify-center shadow-lg relative cursor-pointer transition-transform hover:scale-110 ${currentExecutionNodes[node.id] ? 'hover:shadow-xl' : ''}`}
                  onClick={() => handleNodeClick(node.id)}
                >
                  {/* Node icon - show checkmark for completed nodes, otherwise show default icon */}
                  <div className="text-white text-lg">
                    {status === 'completed' ? (
                      <FaCheck className="h-4 w-4 text-white" />
                    ) : (
                      getNodeIcon(node, status)
                    )}
                  </div>
                  
                  {/* Progress ring for running state */}
                  {status === 'running' && (
                    <div className="absolute inset-0 rounded-full border-2 border-blue-300 border-t-transparent animate-spin"></div>
                  )}
                </div>
                
                {/* Node labels - placed outside circles */}
                <div className="absolute top-13 left-1/2 transform -translate-x-1/2 text-center w-24">
                  <h6 className="font-medium text-xs text-gray-800 dark:text-gray-200 mb-0.5 leading-tight">
                    {node.name}
                  </h6>
                  <p className="text-xs text-gray-500 dark:text-gray-500 leading-tight line-clamp-2 max-h-7 overflow-hidden">
                    {node.description}
                  </p>
                  {/* Execution time display */}
                  {nodeExecution?.duration && (
                    <div className="text-xs text-blue-600 dark:text-blue-400 mt-1 font-medium">
                      {nodeExecution.duration.toFixed(2)}s
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          
          {/* Legend */}
          <div className="absolute bottom-2 right-2 bg-white dark:bg-gray-800 rounded-lg p-2 border shadow-sm z-20">
            <h6 className="text-xs font-medium mb-1">Legend</h6>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
              <div className="flex items-center">
                <div className="w-2 h-2 bg-green-500 rounded-full mr-1"></div>
                <span>Start/End</span>
              </div>
              <div className="flex items-center">
                <div className="w-2 h-2 bg-orange-500 rounded-full mr-1"></div>
                <span>Decision</span>
              </div>
              <div className="flex items-center">
                <div className="w-2 h-2 bg-purple-500 rounded-full mr-1"></div>
                <span>Validation</span>
              </div>
              <div className="flex items-center">
                <div className="w-2 h-2 bg-red-500 rounded-full mr-1"></div>
                <span>Retry</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderExampleQueries = () => {
    const examples = ['salesThisMonth', 'lowStockProducts', 'customerDistribution', 'salesTrendChart', 'salesBarChartLast10Months'];
    
    return (
      <Card className="shadow-xl border-0 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950 dark:to-indigo-950 h-full">
        <CardContent className="p-6 h-full flex flex-col">
          <h6 className="font-bold text-blue-600 mb-4 flex items-center text-lg">
            <FaLightbulb className="mr-2 h-5 w-5" />
            {t('intelligentAnalysis.exampleQueries')}
          </h6>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2 gap-3 flex-1 content-start">
            {examples.map((example, index) => (
              <Button
                key={index}
                variant="outline"
                size="sm"
                onClick={() => handleExampleClick(t(`intelligentAnalysis.examples.${example}`))}
                disabled={loading}
                className="text-left justify-start border-blue-200 hover:border-blue-300 hover:text-blue-500 hover:bg-blue-50 transition-all duration-200 rounded-lg h-auto py-3 px-4 text-sm whitespace-normal break-words min-h-[3rem]"
              >
                <span className="block w-full text-left leading-relaxed">
                  {t(`intelligentAnalysis.examples.${example}`)}
                </span>
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  };

  const fetchActiveDataSource = async () => {
    try {
      const response = await fetch('/api/v1/datasources/active');
      if (response.ok) {
        const result = await response.json();
        // Ensure returned data format is correct
        if (result.success && result.data) {
          setActiveDataSource(result.data);
        } else {
          console.warn('No active data source or unexpected format:', result);
          setActiveDataSource(null);
        }
      } else {
        console.error('Failed to fetch active data source:', response.status);
        setActiveDataSource(null);
      }
    } catch (error) {
      console.error('Failed to fetch active data source:', error);
      setActiveDataSource(null);
    }
  };

  const fetchAvailableDataSources = async () => {
    try {
      const response = await fetch('/api/v1/datasources');
      if (response.ok) {
        const result = await response.json();
        // Ensure returned data format is correct
        if (result.success && Array.isArray(result.data)) {
          setAvailableDataSources(result.data);
        } else {
          console.warn('Unexpected data format from datasources API:', result);
          setAvailableDataSources([]);
        }
      } else {
        console.error('Failed to fetch data sources:', response.status);
        setAvailableDataSources([]);
      }
    } catch (error) {
      console.error('Failed to fetch available data sources:', error);
      setAvailableDataSources([]);
    }
  };

  const handleDataSourceChange = async (dataSourceId) => {
    try {
      const response = await fetch(`/api/v1/datasources/${dataSourceId}/activate`, {
        method: 'POST'
      });
      if (response.ok) {
        await fetchActiveDataSource(); // Refresh active data source
      }
    } catch (error) {
      console.error('Failed to switch data source:', error);
    }
  };

  useEffect(() => {
    fetchActiveDataSource();
    fetchAvailableDataSources();
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 dark:from-gray-900 dark:via-blue-900 dark:to-indigo-900">
      <div className="w-full px-6 py-6 space-y-8">
        {/* Main content area */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 w-full">
        {/* Left side: Query form */}
        <div className="space-y-6 h-full flex flex-col">
          <Card className="shadow-xl border-0 bg-gradient-to-br from-blue-50 to-purple-50 dark:from-blue-950 dark:to-purple-950">
            <CardHeader className="bg-gradient-to-r from-blue-200 to-purple-200 text-gray-700 rounded-t-lg">
              <CardTitle className="flex items-center text-xl">
                <FaRobot className="mr-3 h-7 w-7" />
                {t('intelligentAnalysis.intelligentQuery')}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6 space-y-6">
                             {/* Current data source display and switching */}
               <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-blue-100 dark:border-gray-700">
                 <Label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3 block">
                   {t('intelligentAnalysis.currentDataSource')}:
                 </Label>
                 <div className="space-y-3">
                   <div className="flex items-center space-x-2">
                     <FaDatabase className="h-4 w-4 text-blue-500" />
                     <span className="text-gray-800 dark:text-gray-200 font-medium">
                       {activeDataSource?.name || 'No active data source'}
                     </span>
                     {activeDataSource && (
                       <Badge variant="secondary" className="bg-green-100 text-green-800 text-xs">
                         Active
                       </Badge>
                     )}
                   </div>
                   <div className="relative">
                     <select
                       value={activeDataSource?.id || ''}
                       onChange={(e) => e.target.value && handleDataSourceChange(parseInt(e.target.value))}
                       className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                       disabled={loading}
                     >
                       <option value="">Select a data source...</option>
                       {Array.isArray(availableDataSources) && availableDataSources.length > 0 ? (
                         availableDataSources.map((ds) => (
                           <option key={ds.id} value={ds.id}>
                             {ds.name} ({ds.type || 'Unknown'})
                           </option>
                         ))
                       ) : (
                         <option disabled>No data sources available</option>
                       )}
                     </select>
                   </div>
                 </div>
               </div>

              {/* Query form */}
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <Label htmlFor="query" className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
                    {t('intelligentAnalysis.inputLabel')}
                  </Label>
                  <Textarea
                    id="query"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder={t('intelligentAnalysis.inputPlaceholder')}
                    rows={4}
                    className="w-full border-blue-200 focus:border-blue-300 focus:ring-blue-300 rounded-lg"
                    disabled={loading}
                  />
                </div>

                <Button
                  type="submit"
                  disabled={loading || !activeDataSource}
                  className="w-full bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white py-3 rounded-lg font-medium transition-all duration-200 shadow-lg"
                >
                  {loading ? (
                    <>
                      <Spinner className="mr-2 h-4 w-4" />
                      {t('intelligentAnalysis.analyzing')}
                    </>
                  ) : (
                    <>
                      <FaPaperPlane className="mr-2 h-4 w-4" />
                      {t('intelligentAnalysis.startAnalysis')}
                    </>
                  )}
                </Button>
              </form>

              {/* Error display */}
              {error && (
                <Alert className="bg-red-50 border-red-200 dark:bg-red-950 dark:border-red-800">
                  <FaExclamationTriangle className="h-4 w-4 text-red-500" />
                  <AlertDescription className="text-red-700 dark:text-red-300 ml-2">
                    {error}
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>

          {/* Example queries */}
          <div className="flex-1">
            {renderExampleQueries()}
          </div>
        </div>

        {/* Center: LangGraph flow */}
        <div className="space-y-6">
          {/* Flow chart */}
          <Card className="shadow-xl border-0">
            <CardContent className="p-6">
              {renderLangGraphDiagram()}
            </CardContent>
          </Card>
          

        </div>

        
      </div>

        {/* Analysis results - full width display */}
        {(loading || result || currentExecutionData?.result) && (
          <Card className="w-full shadow-lg border-gray-300">
            <CardHeader className="bg-gradient-to-r from-emerald-200 to-teal-200 text-gray-700 rounded-t-lg">
              <CardTitle className="flex items-center text-xl justify-between">
                <div className="flex items-center">
                  <FaLightbulb className="mr-3 h-7 w-7" />
                  {t('intelligentAnalysis.analysisResult')}
                </div>
                {(result?.validation_node?.quality_score || currentExecutionData?.result?.validation_node?.quality_score || result?.quality_score || currentExecutionData?.result?.quality_score) && (
                  <Badge variant="secondary" className="bg-green-100 text-green-800">
                    {t('intelligentAnalysis.qualityScore')}: {result?.validation_node?.quality_score || currentExecutionData?.result?.validation_node?.quality_score || result?.quality_score || currentExecutionData?.result?.quality_score}/10
                  </Badge>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6 space-y-6">
              {loading && !result && !currentExecutionData?.result && (
                <div className="flex items-center justify-center h-40">
                  <Spinner size="large" />
                  <p className="ml-4 text-lg text-gray-600">{t('intelligentAnalysis.analyzing')}</p>
                </div>
              )}
              
              {(result || currentExecutionData?.result) && (() => {
                const actualResult = result || currentExecutionData?.result;
                // Safely extract chart image and answer from the workflow result
                console.log('Extracting data from actualResult:', actualResult);
                const chartImage = actualResult.chart_rendering_node?.chart_image || actualResult.chart_image;
                const answer = actualResult.llm_processing_node?.answer || actualResult.sql_execution_node?.answer || actualResult.answer;
                console.log('Extracted chartImage:', chartImage);
                console.log('Extracted answer:', answer);

                return (
                  <div className="flex flex-col gap-6">
                    {/* Answer Text */}
                    {answer && (
                      <div className="prose max-w-none text-gray-700">
                        <p className="whitespace-pre-wrap">{answer}</p>
                      </div>
                    )}

                    {/* Chart Image */}
                    {chartImage && (
                      <div className="flex items-center justify-center p-4 bg-gray-50 rounded-lg border">
                        <img 
                          src={chartImage} 
                          alt={t('intelligentAnalysis.analysisChart')} 
                          className="max-w-full h-auto rounded-md shadow-lg"
                        />
                      </div>
                    )}

                    {/* Raw Data Details - show only if there's data and it's not just the chart/answer */}
                    {actualResult && (
                      <Collapsible>
                        <CollapsibleTrigger asChild>
                          <Button variant="outline" size="sm" className="flex items-center gap-2 mt-4">
                            {t('intelligentAnalysis.dataDetails')} <ChevronsUpDown className="h-4 w-4" />
                          </Button>
                        </CollapsibleTrigger>
                        <CollapsibleContent>
                          <pre className="mt-4 p-4 bg-gray-900 text-white rounded-md overflow-x-auto text-sm">
                            {JSON.stringify(actualResult, null, 2)}
                          </pre>
                        </CollapsibleContent>
                      </Collapsible>
                    )}
                  </div>
                );
              })()}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

export default IntelligentAnalysis; 