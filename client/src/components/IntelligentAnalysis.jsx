import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
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
  FaStop
} from 'react-icons/fa';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Alert, AlertDescription } from './ui/alert';
import { Spinner } from './ui/spinner';

function IntelligentAnalysis() {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [activeDataSource, setActiveDataSource] = useState(null);
  const [availableDataSources, setAvailableDataSources] = useState([]);
  
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

  // Process monitoring state
  const [currentNode, setCurrentNode] = useState(null);
  const [executedNodes, setExecutedNodes] = useState([]);
  const [activeEdges, setActiveEdges] = useState([]);
  const [nodeStates, setNodeStates] = useState({});

  // Initialize node states
  useEffect(() => {
    const initialStates = {};
    langGraphNodes.forEach(node => {
      initialStates[node.id] = 'pending';
    });
    setNodeStates(initialStates);
  }, []);

  // Simulate LangGraph flow execution
  const simulateLangGraphFlow = async (query) => {
    // Reset state
    const initialStates = {};
    langGraphNodes.forEach(node => {
      initialStates[node.id] = 'pending';
    });
    setNodeStates(initialStates);
    setExecutedNodes([]);
    setActiveEdges([]);
    setCurrentNode(null);
    
    // Simulate real LangGraph execution path
    const executionPath = determineExecutionPath(query);
    
    for (let i = 0; i < executionPath.length; i++) {
      const nodeId = executionPath[i];
      
      // Set current node
      setCurrentNode(nodeId);
      setNodeStates(prev => ({ ...prev, [nodeId]: 'running' }));
      
      // Activate edges
      if (i > 0) {
        const fromNode = executionPath[i - 1];
        const edge = langGraphEdges.find(e => e.from === fromNode && e.to === nodeId);
        if (edge) {
          setActiveEdges(prev => [...prev, edge]);
        }
      }
      
      // Simulate node execution time
      await new Promise(resolve => setTimeout(resolve, 1000 + Math.random() * 1500));
      
      // Complete current node
      setNodeStates(prev => ({ ...prev, [nodeId]: 'completed' }));
      setExecutedNodes(prev => [...prev, nodeId]);
    }
    
    setCurrentNode(null);
  };
  
  // Determine execution path based on query content
  const determineExecutionPath = (query) => {
    const lowerQuery = query.toLowerCase();
    const isChart = lowerQuery.includes('chart') || lowerQuery.includes('graph') || 
                    lowerQuery.includes('plot') || lowerQuery.includes('trend') ||
                    lowerQuery.includes('generate') || lowerQuery.includes('visualization');
    const isRAG = lowerQuery.includes('langgraph') || lowerQuery.includes('what is') || 
                  lowerQuery.includes('explain') || lowerQuery.includes('how');
    
    if (isRAG) {
      return ['start_node', 'router_node', 'rag_query_node', 'llm_processing_node', 'validation_node', 'end_node'];
    } else if (isChart) {
      return ['start_node', 'router_node', 'sql_classifier_node', 'sql_execution_node', 'chart_config_node', 'chart_rendering_node', 'llm_processing_node', 'validation_node', 'end_node'];
    } else {
      return ['start_node', 'router_node', 'sql_classifier_node', 'sql_execution_node', 'llm_processing_node', 'validation_node', 'end_node'];
    }
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

    setLoading(true);
    setError('');
    setResult(null);
    
    // Start LangGraph flow monitoring
    simulateLangGraphFlow(query.trim());

    try {
      const response = await fetch('/api/v1/intelligent-analysis', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: query.trim(),
          datasource_id: activeDataSource.id,
        }),
      });

      if (!response.ok) {
        throw new Error(t('intelligentAnalysis.networkError'));
      }

      const data = await response.json();
      setResult(data);
    } catch (error) {
      setError(error.message);
      // Mark currently running node as failed when error occurs
      if (currentNode) {
        setNodeStates(prev => ({ ...prev, [currentNode]: 'error' }));
      }
    } finally {
      setLoading(false);
    }
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
    return (
      <div className="w-full">
        <h6 className="font-bold text-blue-600 mb-4 flex items-center text-lg">
          <FaProjectDiagram className="mr-2 h-5 w-5" />
          {t('intelligentAnalysis.langGraphProcess')}
          {currentNode && (
            <Badge className="ml-3 bg-blue-100 text-blue-800 text-xs">
              Running: {langGraphNodes.find(n => n.id === currentNode)?.name}
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
              
              const isActive = activeEdges.some(ae => ae.from === edge.from && ae.to === edge.to);
              
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
            const status = nodeStates[node.id] || 'pending';
            const isCurrentNode = currentNode === node.id;
            const isExecuted = executedNodes.includes(node.id);
            
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
                <div className={`w-12 h-12 rounded-full border-2 ${nodeColor} flex items-center justify-center shadow-lg relative`}>
                  {/* Node icon */}
                  <div className="text-white text-lg">
                    {getNodeIcon(node, status)}
                  </div>
                  
                  {/* Execution completion mark */}
                  {isExecuted && (
                    <div className="absolute -top-1 -right-1 w-4 h-4 bg-green-600 rounded-full flex items-center justify-center">
                      <span className="text-white text-xs">✓</span>
                    </div>
                  )}
                  
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
    const examples = ['salesThisMonth', 'lowStockProducts', 'customerDistribution', 'salesTrendChart', 'whatIsLangGraph'];
    
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

  useEffect(() => {
    fetchActiveDataSource();
    fetchAvailableDataSources();
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 dark:from-gray-900 dark:via-blue-900 dark:to-indigo-900">
      <div className="w-full px-6 py-6 space-y-8">
        {/* Main content area */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-16 w-full">
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

        {/* Right side: LangGraph flow */}
        <div className="h-full">
          {/* Flow chart - aligned with left side height */}
          <Card className="shadow-xl border-0 h-full">
            <CardContent className="p-6 h-full">
              {renderLangGraphDiagram()}
            </CardContent>
          </Card>
        </div>
      </div>

        {/* Analysis results - full width display */}
        {result && (
          <Card className="shadow-xl border-0 bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-950 dark:to-teal-950 w-full">
          <CardHeader className="bg-gradient-to-r from-emerald-200 to-teal-200 text-gray-700 rounded-t-lg">
            <CardTitle className="flex items-center text-xl justify-between">
              <div className="flex items-center">
                <FaLightbulb className="mr-3 h-7 w-7" />
                {t('intelligentAnalysis.analysisResult')}
              </div>
              {result.quality_score && (
                <Badge variant="secondary" className="bg-green-100 text-green-800">
                  {t('intelligentAnalysis.qualityScore')}: {result.quality_score}/10
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6 space-y-6">
            {/* Answer */}
            {result.answer && (
              <div className="prose prose-lg max-w-none">
                <h6 className="font-bold text-gray-800 dark:text-gray-200 mb-3 flex items-center">
                  <FaComments className="mr-2 h-5 w-5 text-teal-300" />
                  {t('intelligentAnalysis.answer')}
                </h6>
                <p className="text-gray-800 dark:text-gray-200 leading-relaxed text-lg font-medium bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-emerald-100">
                  {result.answer}
                </p>
              </div>
            )}

            {/* Generated chart */}
            {result.chart_image && (
              <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-teal-100 dark:border-gray-700 shadow-md">
                <h6 className="font-bold text-gray-800 dark:text-gray-200 mb-4 flex items-center">
                  <FaChartLine className="mr-2 h-5 w-5 text-teal-300" />
                  {t('intelligentAnalysis.generatedChart')}
                </h6>
                <img 
                  src={result.chart_image} 
                  alt="Generated Chart" 
                  className="w-full h-auto rounded-lg shadow-sm"
                />
              </div>
            )}

            {/* Data details */}
            {result.data && (
              <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-teal-100 dark:border-gray-700 shadow-md">
                <h6 className="font-bold text-gray-800 dark:text-gray-200 mb-4 flex items-center">
                  <FaDatabase className="mr-2 h-5 w-5 text-teal-300" />
                  {t('intelligentAnalysis.dataDetails')}
                </h6>
                <pre 
                  className="text-sm bg-gray-50 dark:bg-gray-900 p-4 rounded-lg border overflow-auto font-mono max-h-64" 
                  style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}
                >
                  {JSON.stringify(result.data, null, 2)}
                </pre>
              </div>
            )}

            {/* Chart configuration */}
            {result.chart_config && (
              <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-yellow-100 dark:border-gray-700 shadow-md">
                <h6 className="font-bold text-gray-800 dark:text-gray-200 mb-4 flex items-center">
                  <FaCode className="mr-2 h-5 w-5 text-yellow-400" />
                  {t('intelligentAnalysis.chartConfig')}
                </h6>
                <pre 
                  className="text-sm bg-gray-50 dark:bg-gray-900 p-4 rounded-lg border overflow-auto font-mono max-h-64" 
                  style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}
                >
                  {JSON.stringify(result.chart_config, null, 2)}
                </pre>
              </div>
            )}

            {/* Error information */}
            {result.error && (
              <div className="bg-red-50 dark:bg-red-950 rounded-xl p-6 border border-red-200 dark:border-red-800 shadow-md">
                <h6 className="font-bold text-red-800 dark:text-red-200 mb-4 flex items-center">
                  <FaExclamationTriangle className="mr-2 h-5 w-5 text-red-500" />
                  {t('intelligentAnalysis.errorInfo')}
                </h6>
                <p className="text-red-700 dark:text-red-300 font-mono text-sm">
                  {result.error}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}
      </div>
    </div>
  );
}

export default IntelligentAnalysis; 