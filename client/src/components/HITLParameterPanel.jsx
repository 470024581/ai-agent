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
      
      // Initialize parameters with current state values - use complete state
      const initialParams = {
        user_input: currentState?.user_input || currentState?.query || '',
        query_type: currentState?.query_type || '',
        sql_task_type: currentState?.sql_task_type || '',
        structured_data: currentState?.structured_data || null,
        chart_config: currentState?.chart_config || null,
        answer: currentState?.answer || '',
        datasource: currentState?.datasource || null,
        // Add any other fields that might be useful for debugging
        execution_id: currentState?.execution_id || executionId || '',
        hitl_status: currentState?.hitl_status || '',
        hitl_node: currentState?.hitl_node || nodeName || '',
      };
      
      console.log('📊 [FRONTEND-HITL] HITLParameterPanel initialParams:', initialParams);
      console.log('📊 [FRONTEND-HITL] HITLParameterPanel query_type from state:', currentState?.query_type);
      console.log('📊 [FRONTEND-HITL] HITLParameterPanel sql_task_type from state:', currentState?.sql_task_type);
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
    
    if (parameters.sql_task_type && !['query', 'chart'].includes(parameters.sql_task_type)) {
      errors.sql_task_type = 'SQL task type must be either "query" or "chart"';
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
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
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
        
        <CardContent className="space-y-6">
          {/* Execution Info */}
          <div className="grid grid-cols-2 gap-4 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
            <div>
              <Label className="text-sm font-medium text-gray-600 dark:text-gray-400">Execution ID</Label>
              <p className="text-sm font-mono">{executionId}</p>
            </div>
            <div>
              <Label className="text-sm font-medium text-gray-600 dark:text-gray-400">Node</Label>
              <p className="text-sm">{nodeName}</p>
            </div>
          </div>

          <Separator />

          {/* Parameter Adjustments */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Parameter Adjustments</h3>
            
            {/* User Input */}
            <div className="space-y-2">
              <Label htmlFor="user_input">User Input</Label>
              <Textarea
                id="user_input"
                value={parameters.user_input || ''}
                onChange={(e) => handleParameterChange('user_input', e.target.value)}
                placeholder="Enter your query..."
                className={validationErrors.user_input ? 'border-red-500' : ''}
                rows={3}
              />
              {validationErrors.user_input && (
                <p className="text-sm text-red-500 flex items-center gap-1">
                  <XCircle className="h-4 w-4" />
                  {validationErrors.user_input}
                </p>
              )}
            </div>

            {/* Query Type */}
            <div className="space-y-2">
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

            {/* SQL Task Type */}
            {parameters.query_type === 'sql' && (
              <div className="space-y-2">
                <Label htmlFor="sql_task_type">SQL Task Type</Label>
                <select
                  id="sql_task_type"
                  value={parameters.sql_task_type || ''}
                  onChange={(e) => handleParameterChange('sql_task_type', e.target.value)}
                  className={`w-full p-2 border rounded-md ${validationErrors.sql_task_type ? 'border-red-500' : 'border-gray-300'}`}
                >
                  <option value="">Select SQL task type...</option>
                  <option value="query">Data Query</option>
                  <option value="chart">Chart Generation</option>
                </select>
                {validationErrors.sql_task_type && (
                  <p className="text-sm text-red-500 flex items-center gap-1">
                    <XCircle className="h-4 w-4" />
                    {validationErrors.sql_task_type}
                  </p>
                )}
              </div>
            )}

            {/* Additional Parameters */}
            <div className="space-y-2">
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
                rows={4}
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
