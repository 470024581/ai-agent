import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { AlertCircle, CheckCircle, XCircle } from 'lucide-react';

export function HITLParameterPanel({ 
  isOpen, 
  onClose, 
  executionId, 
  nodeName, 
  currentState, 
  onResume, 
  onCancel,
  executionType = "pause" // "pause" or "interrupt"
}) {
  const [parameters, setParameters] = useState({});
  const [validationErrors, setValidationErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Map internal node ids to friendly display names
  const getDisplayNodeName = (id) => {
    const map = {
      rag_retriever_node: 'RAG Retriever',
      rerank_node: 'Rerank',
      rag_answer_node: 'RAG Answer',
      router_node: 'Router',
      sql_agent_node: 'SQL Agent',
      chart_process_node: 'Chart Process',
      llm_processing_node: 'LLM Process',
      start_node: 'Start',
      end_node: 'Complete',
    };
    return map[id] || id || '';
  };

  // Debug: Log all props
  console.log('HITLParameterPanel props:', {
    isOpen,
    executionId,
    nodeName,
    currentState,
    executionType
  });
  
  // Debug: Log when component renders
  console.log('HITLParameterPanel rendering, isOpen:', isOpen);

  useEffect(() => {
    if (isOpen) {
      // Debug: Log currentState structure
      console.log('🔄 [FRONTEND-HITL] HITLParameterPanel useEffect called');
      console.log('📥 [FRONTEND-HITL] HITLParameterPanel currentState received:', currentState);
      console.log('📥 [FRONTEND-HITL] HITLParameterPanel currentState keys:', currentState ? Object.keys(currentState) : 'null');
      
      // Robust extraction helpers
      const pick = (obj, paths, fallback = undefined) => {
        for (const p of paths) {
          try {
            const val = p.split('.').reduce((o, k) => (o ? o[k] : undefined), obj);
            if (val !== undefined && val !== null && val !== '') return val;
          } catch (_) { /* ignore */ }
        }
        return fallback;
      };

      // Derive sensible defaults when backend snapshot misses fields (common on interrupts)
      const derivedQueryType = pick(currentState, ['query_type', 'input.query_type'],
        nodeName === 'chart_process_node' || nodeName === 'sql_agent_node' ? 'sql' : (nodeName === 'rag_answer_node' ? 'rag' : ''));
      const derivedNeedSqlAgent = pick(currentState, ['need_sql_agent', 'input.need_sql_agent'],
        nodeName === 'router_node' ? true : false);

      const initialParams = {
        user_input: pick(currentState, ['user_input', 'query', 'input.user_input'], ''),
        query_type: derivedQueryType,
        need_sql_agent: derivedNeedSqlAgent,
        retrieved_documents: pick(currentState, ['retrieved_documents', 'input.retrieved_documents'], []),
        reranked_documents: pick(currentState, ['reranked_documents', 'input.reranked_documents'], []),
        rag_answer: pick(currentState, ['rag_answer', 'input.rag_answer', 'output.rag_answer'], ''),
        sql_agent_answer: pick(currentState, ['sql_agent_answer', 'input.sql_agent_answer', 'output.sql_agent_answer'], ''),
        executed_sqls: pick(currentState, ['executed_sqls', 'input.executed_sqls'], []),
        structured_data: pick(currentState, ['structured_data', 'input.structured_data', 'output.structured_data'], null),
        chart_config: pick(currentState, ['chart_config', 'input.chart_config', 'output.chart_config'], null),
        chart_suitable: pick(currentState, ['chart_suitable', 'input.chart_suitable'], false),
        answer: pick(currentState, ['answer', 'input.answer', 'output.answer'], ''),
        datasource: pick(currentState, ['datasource'], null),
        execution_id: pick(currentState, ['execution_id'], executionId || ''),
        hitl_status: pick(currentState, ['hitl_status'], ''),
        hitl_node: pick(currentState, ['hitl_node'], nodeName || ''),
      };
      
      console.log('📊 [FRONTEND-HITL] HITLParameterPanel initialParams:', initialParams);
      console.log('📊 [FRONTEND-HITL] HITLParameterPanel query_type from state:', currentState?.query_type);
      console.log('📊 [FRONTEND-HITL] HITLParameterPanel datasource from state:', currentState?.datasource);
      setParameters(initialParams);
      setValidationErrors({});
      console.log('✅ [FRONTEND-HITL] HITLParameterPanel initialization completed');
    }
  }, [isOpen, currentState, executionId, nodeName]);

  const handleParameterChange = (key, value) => {
    setParameters(prev => ({
      ...prev,
      [key]: value
    }));
    
    // Clear validation error for this field
    if (validationErrors[key]) {
      setValidationErrors(prev => ({
        ...prev,
        [key]: null
      }));
    }
  };

  const validateParameters = () => {
    const errors = {};
    
    if (!parameters.user_input?.trim()) {
      errors.user_input = 'User input is required';
    }
    
    if (parameters.query_type && !['sql', 'rag'].includes(parameters.query_type)) {
      errors.query_type = 'Query type must be either "sql" or "rag"';
    }
    
    if (parameters.need_sql_agent !== undefined && typeof parameters.need_sql_agent !== 'boolean') {
      errors.need_sql_agent = 'Need SQL Agent must be true or false';
    }
    
    if (parameters.chart_suitable !== undefined && typeof parameters.chart_suitable !== 'boolean') {
      errors.chart_suitable = 'Chart suitable must be true or false';
    }
    
    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleResume = async () => {
    console.log('🔄 [FRONTEND-HITL] handleResume called');
    console.log('📥 [FRONTEND-HITL] handleResume input params:', { parameters, executionId, executionType });
    
    if (!validateParameters()) {
      console.error('❌ [FRONTEND-HITL] handleResume validation failed');
      return;
    }
    
    setIsSubmitting(true);
    try {
      // Only send parameters that have been modified (non-empty values)
      const modifiedParams = {};
      Object.keys(parameters).forEach(key => {
        const value = parameters[key];
        if (value !== null && value !== undefined && value !== '') {
          modifiedParams[key] = value;
        }
      });
      
      console.log('📤 [FRONTEND-HITL] handleResume sending modified parameters:', modifiedParams);
      await onResume(executionId, modifiedParams, executionType);
      onClose();
      // Prevent users from interrupting immediately after resume
      const interruptBtn = document.querySelector('button:has(svg.h-3.w-3)');
      if (interruptBtn) {
        interruptBtn.setAttribute('disabled', 'true');
      }
      console.log('✅ [FRONTEND-HITL] handleResume completed successfully');
    } catch (error) {
      console.error('❌ [FRONTEND-HITL] handleResume failed:', error);
    } finally {
      setIsSubmitting(false);
    }
  };


  const handleCancel = async () => {
    setIsSubmitting(true);
    try {
      await onCancel(executionId, executionType);
      onClose();
    } catch (error) {
      console.error('Error cancelling execution:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-3">
      <Card className="w-full max-w-2xl max-h-[92vh]">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <AlertCircle className="h-5 w-5 text-yellow-500" />
                HITL Parameter Adjustment
              </CardTitle>
              <CardDescription>
                Adjust parameters for {executionType === 'pause' ? 'paused' : 'interrupted'} execution
              </CardDescription>
            </div>
            <Badge variant={executionType === 'pause' ? 'secondary' : 'destructive'}>
              {executionType === 'pause' ? 'Paused' : 'Interrupted'}
            </Badge>
          </div>
        </CardHeader>
        
        <CardContent className="space-y-4 overflow-y-auto">
          {/* Execution Info */}
          <div className="grid grid-cols-2 gap-3 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
            <div>
              <Label className="text-sm font-medium text-gray-600 dark:text-gray-400">Execution ID</Label>
              <p className="text-sm font-mono">{executionId}</p>
            </div>
            <div>
              <Label className="text-sm font-medium text-gray-600 dark:text-gray-400">Node</Label>
              <p className="text-sm">{getDisplayNodeName(nodeName)}</p>
            </div>
          </div>

          <Separator />

          {/* Parameter Adjustments */}
          <div className="space-y-3">
            <h3 className="text-lg font-semibold">Parameter Adjustments</h3>
            
            {/* User Input */}
            <div className="space-y-1.5">
              <Label htmlFor="user_input">User Input</Label>
              <Textarea
                id="user_input"
                value={parameters.user_input || ''}
                onChange={(e) => handleParameterChange('user_input', e.target.value)}
                placeholder="Enter your query..."
                className={validationErrors.user_input ? 'border-red-500' : ''}
                rows={2}
              />
              {validationErrors.user_input && (
                <p className="text-sm text-red-500 flex items-center gap-1">
                  <XCircle className="h-4 w-4" />
                  {validationErrors.user_input}
                </p>
              )}
            </div>

            {/* Query Type */}
            <div className="space-y-1.5">
              <Label htmlFor="query_type">Query Type</Label>
              <select
                id="query_type"
                value={parameters.query_type || ''}
                onChange={(e) => handleParameterChange('query_type', e.target.value)}
                className={`w-full p-2 border rounded-md ${validationErrors.query_type ? 'border-red-500' : 'border-gray-300'}`}
              >
                <option value="">Select query type...</option>
                <option value="sql">SQL Query</option>
                <option value="rag">RAG Query</option>
              </select>
              {validationErrors.query_type && (
                <p className="text-sm text-red-500 flex items-center gap-1">
                  <XCircle className="h-4 w-4" />
                  {validationErrors.query_type}
                </p>
              )}
            </div>

            {/* Additional Parameters */}
            <div className="space-y-1.5">
              <Label htmlFor="additional_params">Additional Parameters (JSON)</Label>
              <Textarea
                id="additional_params"
                value={JSON.stringify(parameters.additional_params || {}, null, 2)}
                onChange={(e) => {
                  try {
                    const parsed = JSON.parse(e.target.value);
                    handleParameterChange('additional_params', parsed);
                  } catch (error) {
                    // Invalid JSON, keep the text for editing
                  }
                }}
                placeholder='{"key": "value"}'
                rows={3}
                className="font-mono text-sm"
              />
            </div>
          </div>

          <Separator />

          {/* Action Buttons */}
          <div className="flex gap-3 justify-end">
            <Button
              variant="outline"
              onClick={handleCancel}
              disabled={isSubmitting}
              className="flex items-center gap-2"
            >
              <XCircle className="h-4 w-4" />
              Cancel Execution
            </Button>
            <Button
              onClick={handleResume}
              disabled={isSubmitting}
              className="flex items-center gap-2"
            >
              <CheckCircle className="h-4 w-4" />
              Resume with Parameters
            </Button>
          </div>

          {/* Status Messages */}
          {isSubmitting && (
            <div className="flex items-center gap-2 text-blue-600">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
              Processing...
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
