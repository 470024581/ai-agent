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
import useRateLimit from '../hooks/useRateLimit';
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
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem, SelectGroup, SelectLabel } from './ui/select';
import { ChevronsUpDown, Lightbulb, ChevronDown, ChevronRight, Clock, Database, FileText, AlertCircle } from 'lucide-react';

function IntelligentAnalysis() {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  
  // Rate limiting hook
  const {
    isLimited,
    remainingClicks,
    recordClick,
    getTimeUntilReset,
    maxClicks
  } = useRateLimit('analysis_clicks', 10, 60 * 60 * 1000); // 每小时最多10次
  
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
    { id: 'sql_chart_node', name: 'SQL Chart', type: 'process', position: { x: 50, y: 270 }, description: 'Execute chart data query' },
    { id: 'sql_query_node', name: 'SQL Query', type: 'process', position: { x: 300, y: 270 }, description: 'Execute database query' },
    { id: 'chart_config_node', name: 'Chart Config', type: 'process', position: { x: 50, y: 400 }, description: 'Generate chart configuration' },
    { id: 'chart_rendering_node', name: 'Chart Render', type: 'process', position: { x: 190, y: 400 }, description: 'Call QuickChart API' },
    { id: 'llm_processing_node', name: 'LLM Process', type: 'process', position: { x: 300, y: 400 }, description: 'Generate natural language response' },
    { id: 'validation_node', name: 'Validation', type: 'validation', position: { x: 300, y: 520 }, description: 'Quality score validation' },
    { id: 'retry_node', name: 'Retry', type: 'retry', position: { x: 150, y: 520 }, description: 'Retry with improvements' },
    { id: 'end_node', name: 'End', type: 'end', position: { x: 200, y: 680 }, description: 'Process completed' }
  ];

  const langGraphEdges = [
    { from: 'start_node', to: 'router_node', condition: 'Start Process', color: '#22c55e' },
    { from: 'router_node', to: 'sql_classifier_node', condition: 'SQL Path', color: '#3b82f6' },
    { from: 'router_node', to: 'rag_query_node', condition: 'RAG Path', color: '#8b5cf6' },
    { from: 'sql_classifier_node', to: 'sql_chart_node', condition: 'Chart Type', color: '#f59e0b' },
    { from: 'sql_classifier_node', to: 'sql_query_node', condition: 'Query Type', color: '#10b981' },
    { from: 'sql_chart_node', to: 'chart_config_node', condition: 'Chart Data', color: '#f59e0b' },
    { from: 'sql_query_node', to: 'llm_processing_node', condition: 'Query Result', color: '#10b981' },
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
  
  // Node detail dialog state
  const [selectedNodeId, setSelectedNodeId] = useState(null);

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
      console.log('Setting result from completed execution:', executionResult);
      console.log('Result keys:', Object.keys(executionResult));
      setResult(executionResult);
      setLoading(false); // Reset loading state when we get a result
    }
    // Don't reset result when executionResult becomes null
    // This allows the result to persist after execution completes
  }, [executionResult]);
  
  // Handler for node click
  const handleNodeClick = (nodeId) => {
    if (currentExecutionNodes[nodeId]) {
      setSelectedNodeId(nodeId);
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
    if (!query.trim()) {
      setError(t('intelligentAnalysis.enterQueryError'));
      return;
    }

    // Check rate limit before proceeding
    if (isLimited) {
      return;
    }

    // Record the click attempt
    const clickRecorded = recordClick();
    if (!clickRecorded) {
      return;
    }

    // Check WebSocket connection status
    if (connectionStatus !== 'connected') {
      setError('WebSocket连接未建立，请等待连接后重试');
      return;
    }

    // Clear previous results and set loading state at the start
    setResult(null);
    setLoading(true);
    setError('');
    
    // Reset Redux execution state
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
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      if (data.error) {
        setError(data.error);
        setLoading(false);
      }
    } catch (error) {
      console.error('Error:', error);
      setError(error.message);
      setLoading(false);
    }
  };

  // Example queries data structure
  const exampleQueries = [
    {
      category: 'SQL Chart',
      color: 'blue',
      examples: [
        'Generate a monthly sales trend chart for 2025.',
        'The pie chart shows the sales proportion of each product.'
      ]
    },
    {
      category: 'SQL Query',
      color: 'green',
      examples: [
        "What's the average price of each product category?",
        'What are the sales this month?'
      ]
    },
    {
      category: 'RAG Query',
      color: 'purple',
      examples: [
        'Do you know any software developers?',
        'Who is Longliang?'
      ]
    }
  ];

  const handleExampleClick = (exampleQuery) => {
    setQuery(exampleQuery);
  };

  // Handle example select change
  const handleExampleSelect = (value) => {
    if (value && value !== 'placeholder') {
      setQuery(value);
    }
  };

  // Data formatting utilities for node details
  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'N/A';
    return new Date(timestamp).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  const formatDuration = (duration) => {
    if (!duration) return 'N/A';
    if (duration < 1) {
      return `${Math.round(duration * 1000)}ms`;
    }
    return `${duration.toFixed(2)}s`;
  };

  const formatNodeData = (data, maxLength = 200) => {
    if (data === null || data === undefined) return 'No data';
    
    let jsonString;
    if (typeof data === 'string') {
      jsonString = data;
    } else {
      try {
        jsonString = JSON.stringify(data, null, 2);
      } catch (e) {
        jsonString = String(data);
      }
    }
    
    if (jsonString.length <= maxLength) {
      return jsonString;
    }
    
    return jsonString.substring(0, maxLength) + '...';
  };

  const formatBytes = (bytes) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Node detail dialog component
  const renderNodeDetailDialog = () => {
    if (!selectedNodeId) return null;

    const nodeInfo = langGraphNodes.find(n => n.id === selectedNodeId);
    const nodeExecution = currentExecutionNodes[selectedNodeId];
    
    if (!nodeInfo || !nodeExecution) return null;

    const getStatusBadgeVariant = (status) => {
      switch (status) {
        case 'completed': return 'default';
        case 'running': return 'secondary';
        case 'error': return 'destructive';
        default: return 'outline';
      }
    };

    const getStatusIcon = (status) => {
      switch (status) {
        case 'completed': return <FaCheck className="h-3 w-3" />;
        case 'running': return <FaSpinner className="h-3 w-3 animate-spin" />;
        case 'error': return <AlertCircle className="h-3 w-3" />;
        default: return <Clock className="h-3 w-3" />;
      }
    };

    return (
      <Dialog open={!!selectedNodeId} onOpenChange={(open) => !open && setSelectedNodeId(null)}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                {getNodeIcon(nodeInfo, nodeExecution.status)}
                <span>{nodeInfo.name}</span>
              </div>
              <Badge variant={getStatusBadgeVariant(nodeExecution.status)} className="flex items-center gap-1">
                {getStatusIcon(nodeExecution.status)}
                {nodeExecution.status}
              </Badge>
            </DialogTitle>
          </DialogHeader>
          
          <div className="space-y-6">
            {/* Basic Information */}
                         <div className="space-y-3">
               <h4 className="text-sm font-medium text-gray-900 dark:text-gray-100 flex items-center gap-2">
                 <Database className="h-4 w-4" />
                 {t('intelligentAnalysis.nodeDetail.basicInfo')}
               </h4>
               <div className="grid grid-cols-2 gap-4 text-sm">
                 <div>
                   <span className="text-gray-500 dark:text-gray-400">{t('intelligentAnalysis.nodeDetail.nodeType')}:</span>
                   <span className="ml-2 font-medium">{nodeInfo.type}</span>
                 </div>
                 <div>
                   <span className="text-gray-500 dark:text-gray-400">{t('intelligentAnalysis.nodeDetail.nodeId')}:</span>
                   <span className="ml-2 font-mono text-xs bg-gray-100 dark:bg-gray-800 px-1 rounded">{nodeInfo.id}</span>
                 </div>
                 <div className="col-span-2">
                   <span className="text-gray-500 dark:text-gray-400">{t('intelligentAnalysis.nodeDetail.description')}:</span>
                   <span className="ml-2">{nodeInfo.description}</span>
                 </div>
               </div>
             </div>

            {/* Execution Information */}
                         <div className="space-y-3">
               <h4 className="text-sm font-medium text-gray-900 dark:text-gray-100 flex items-center gap-2">
                 <Clock className="h-4 w-4" />
                 {t('intelligentAnalysis.nodeDetail.executionInfo')}
               </h4>
               <div className="grid grid-cols-2 gap-4 text-sm">
                 <div>
                   <span className="text-gray-500 dark:text-gray-400">{t('intelligentAnalysis.nodeDetail.startTime')}:</span>
                   <span className="ml-2 font-mono text-xs">{formatTimestamp(nodeExecution.startTime)}</span>
                 </div>
                 <div>
                   <span className="text-gray-500 dark:text-gray-400">{t('intelligentAnalysis.nodeDetail.endTime')}:</span>
                   <span className="ml-2 font-mono text-xs">{formatTimestamp(nodeExecution.endTime)}</span>
                 </div>
                 <div>
                   <span className="text-gray-500 dark:text-gray-400">{t('intelligentAnalysis.nodeDetail.duration')}:</span>
                   <span className="ml-2 font-medium text-blue-600 dark:text-blue-400">{formatDuration(nodeExecution.duration)}</span>
                 </div>
                 <div>
                   <span className="text-gray-500 dark:text-gray-400">{t('intelligentAnalysis.nodeDetail.retryCount')}:</span>
                   <span className="ml-2">{nodeExecution.retryCount || 0}</span>
                 </div>
               </div>
             </div>

            {/* Input Data */}
                         {nodeExecution.input && (
               <div className="space-y-3">
                 <Collapsible>
                   <CollapsibleTrigger className="flex items-center gap-2 text-sm font-medium text-gray-900 dark:text-gray-100 hover:text-blue-600 dark:hover:text-blue-400 transition-colors">
                     <ChevronRight className="h-4 w-4 transition-transform data-[state=open]:rotate-90" />
                     <FileText className="h-4 w-4" />
                     {t('intelligentAnalysis.nodeDetail.inputData')}
                   </CollapsibleTrigger>
                   <CollapsibleContent>
                     <div className="mt-2 p-3 bg-gray-50 dark:bg-gray-900 rounded-lg border">
                       <pre className="text-xs overflow-x-auto whitespace-pre-wrap text-gray-700 dark:text-gray-300">
                         {formatNodeData(nodeExecution.input, 500)}
                       </pre>
                     </div>
                   </CollapsibleContent>
                 </Collapsible>
               </div>
             )}

            {/* Output Data */}
                         {nodeExecution.output && (
               <div className="space-y-3">
                 <Collapsible>
                   <CollapsibleTrigger className="flex items-center gap-2 text-sm font-medium text-gray-900 dark:text-gray-100 hover:text-blue-600 dark:hover:text-blue-400 transition-colors">
                     <ChevronRight className="h-4 w-4 transition-transform data-[state=open]:rotate-90" />
                     <FileText className="h-4 w-4" />
                     {t('intelligentAnalysis.nodeDetail.outputData')}
                   </CollapsibleTrigger>
                   <CollapsibleContent>
                     <div className="mt-2 p-3 bg-gray-50 dark:bg-gray-900 rounded-lg border">
                       <pre className="text-xs overflow-x-auto whitespace-pre-wrap text-gray-700 dark:text-gray-300">
                         {formatNodeData(nodeExecution.output, 500)}
                       </pre>
                     </div>
                   </CollapsibleContent>
                 </Collapsible>
               </div>
             )}

            {/* Error Information */}
                         {nodeExecution.error && (
               <div className="space-y-3">
                 <h4 className="text-sm font-medium text-red-600 dark:text-red-400 flex items-center gap-2">
                   <AlertCircle className="h-4 w-4" />
                   {t('intelligentAnalysis.nodeDetail.errorInfo')}
                 </h4>
                 <div className="p-3 bg-red-50 dark:bg-red-950 rounded-lg border border-red-200 dark:border-red-800">
                   <pre className="text-xs text-red-700 dark:text-red-300 whitespace-pre-wrap">
                     {nodeExecution.error}
                   </pre>
                 </div>
               </div>
             )}
          </div>
        </DialogContent>
      </Dialog>
    );
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
          
          {/* Legend removed as per user request */}
        </div>
      </div>
    );
  };

  const renderExampleQueries = () => {
    const examples = [
      'currentMonthSales',      // Basic sales query
      'topProductsByAmount',    // Analysis of top selling products
      'categoryPriceAnalysis',  // Average price analysis by category
      'salesTrendChart2025',    // Sales trend visualization
      'bestSellerByQuantity',   // Best-selling product analysis
      'whoIsLongliang'         // Keep this as a non-data query example
    ];
    
    return (
      <div className="space-y-3">
        <Label className="text-sm font-medium text-blue-500 flex items-center gap-2">
          <Lightbulb size={18} />
          {t('intelligentAnalysis.exampleTitle')}
        </Label>
        
        <Select onValueChange={handleExampleSelect} disabled={loading}>
          <SelectTrigger className="w-full">
            <SelectValue placeholder={t('intelligentAnalysis.selectExample') || 'Select an example query...'} />
          </SelectTrigger>
          <SelectContent>
            {exampleQueries.map((category, index) => (
              <SelectGroup key={index}>
                <SelectLabel className={`text-${category.color}-600 font-semibold`}>
                  {category.category}
                </SelectLabel>
                {category.examples.map((example, exampleIndex) => (
                  <SelectItem 
                    key={`${index}-${exampleIndex}`} 
                    value={example}
                    className="cursor-pointer"
                  >
                    <span className="text-sm">
                      {category.category} - {example}
                    </span>
                  </SelectItem>
                ))}
              </SelectGroup>
            ))}
          </SelectContent>
        </Select>
      </div>
    );
  };

  const fetchActiveDataSource = async () => {
    try {
      const response = await fetch('/api/v1/datasources/active');
      if (response.ok) {
        const result = await response.json();
        if (result.success && result.data) {
          setActiveDataSource(result.data);
        } else {
          setActiveDataSource(null);
        }
      } else {
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
        if (result.success && Array.isArray(result.data)) {
          // Filter out default data source
          const customDataSources = result.data.filter(ds => ds.type !== 'DEFAULT' && ds.id !== 1);
          setAvailableDataSources(customDataSources);
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

  // Format remaining clicks text
  const formatRemainingClicks = () => {
    const text = t('intelligentAnalysis.rateLimit.remainingClicks');
    return text.replace('{remaining}', remainingClicks).replace('{total}', maxClicks);
  };

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
               {availableDataSources.length > 0 && (
                 <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-blue-100 dark:border-gray-700">
                   <Label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3 block">
                     {t('intelligentAnalysis.currentDataSource')}:
                   </Label>
                   <div className="space-y-3">
                     <div className="flex items-center space-x-2">
                       <FaDatabase className="h-4 w-4 text-blue-500" />
                       <span className="text-gray-800 dark:text-gray-200 font-medium">
                         {activeDataSource?.name || t('intelligentAnalysis.noDataSource')}
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
                         <option value="">{t('intelligentAnalysis.selectDataSource')}</option>
                         {availableDataSources.map((ds) => (
                           <option key={ds.id} value={ds.id}>
                             {ds.name} ({ds.type})
                           </option>
                         ))}
                       </select>
                     </div>
                   </div>
                 </div>
               )}

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

                <div className="space-y-2">
                <Button
                  type="submit"
                    disabled={loading || isLimited}
                    className="w-full bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white py-3 rounded-lg font-medium transition-all duration-200 shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? (
                    <>
                      <Spinner className="mr-2 h-5 w-5" />
                      {t('intelligentAnalysis.analyzing')}
                    </>
                    ) : isLimited ? (
                      <>
                        <FaClock className="mr-2 h-4 w-4" />
                        {t('intelligentAnalysis.rateLimit.buttonExceeded')}
                        {getTimeUntilReset() && (
                          <span className="ml-1">
                            ({t('intelligentAnalysis.rateLimit.waitTime').replace('{time}', getTimeUntilReset())})
                          </span>
                        )}
                      </>
                  ) : (
                    <>
                      <FaPaperPlane className="mr-2 h-4 w-4" />
                      {t('intelligentAnalysis.startAnalysis')}
                    </>
                  )}
                </Button>
                  
                  {/* Rate limit status */}
                  <div className="text-sm text-center">
                    {isLimited ? (
                      <div className="space-y-2">
                        <Alert variant="destructive">
                          <AlertCircle className="h-4 w-4" />
                          <AlertDescription>
                            {t('intelligentAnalysis.rateLimit.exceeded')}
                          </AlertDescription>
                        </Alert>
                        <p className="text-red-600">
                          <span>{t('intelligentAnalysis.rateLimit.pleaseContactAuthor')}</span>
                          <a href={`mailto:${t('intelligentAnalysis.rateLimit.contactAuthor')}`} className="text-blue-600 hover:underline mx-1">
                            {t('intelligentAnalysis.rateLimit.contactAuthor')}
                          </a>
                          {getTimeUntilReset() && (
                            <span className="block mt-1 text-red-600">
                              {t('intelligentAnalysis.rateLimit.waitTime').replace('{time}', getTimeUntilReset())}
                            </span>
                          )}
                        </p>
                      </div>
                    ) : (
                      <p className="text-gray-600">
                        {formatRemainingClicks()}
                        {remainingClicks <= 3 && remainingClicks > 0 && (
                          <span className="text-amber-600 ml-2">
                            {t('intelligentAnalysis.rateLimit.almostExceeded')}
                          </span>
                        )}
                      </p>
                    )}
                  </div>
                </div>
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
                  <Spinner className="h-8 w-8" />
                  <p className="ml-4 text-lg text-gray-600">{t('intelligentAnalysis.analyzing')}</p>
                </div>
              )}
              
              {(result || currentExecutionData?.result || currentExecutionData?.streamingAnswer) && (() => {
                const actualResult = result || currentExecutionData?.result;
                // Safely extract chart image and answer from the workflow result
                console.log('Extracting data from actualResult:', actualResult);
                const chartImage = actualResult?.chart_rendering_node?.chart_image || actualResult?.chart_image;
                
                // Priority: streaming answer > final answer > static answer
                const streamingAnswer = currentExecutionData?.streamingAnswer;
                const finalAnswer = currentExecutionData?.finalAnswer || actualResult?.llm_processing_node?.answer || actualResult?.sql_execution_node?.answer || actualResult?.answer;
                const isStreaming = currentExecutionData?.isStreaming || false;
                const displayAnswer = streamingAnswer || finalAnswer;
                
                console.log('Extracted chartImage:', chartImage);
                console.log('Streaming answer:', streamingAnswer?.substring(0, 100));
                console.log('Final answer:', finalAnswer?.substring(0, 100));
                console.log('Is streaming:', isStreaming);

                return (
                  <div className="flex flex-col gap-6">
                    {/* Streaming Indicator */}
                    {isStreaming && (
                      <div className="flex items-center gap-2 text-blue-600 animate-pulse">
                        <FaSpinner className="animate-spin" />
                        <span className="text-sm font-medium">{t('intelligentAnalysis.generatingAnswer') || 'Generating answer...'}</span>
                      </div>
                    )}
                    
                    {/* Answer Text with Streaming Support */}
                    {displayAnswer && (
                      <div className="prose max-w-none text-gray-700 relative">
                        <p className="whitespace-pre-wrap">
                          {displayAnswer}
                          {isStreaming && (
                            <span className="inline-block w-2 h-5 ml-1 bg-blue-600 animate-pulse">|</span>
                          )}
                        </p>
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
      
      {/* Node Detail Dialog */}
      {renderNodeDetailDialog()}
    </div>
  );
}

export default IntelligentAnalysis; 