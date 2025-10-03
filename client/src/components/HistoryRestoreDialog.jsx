import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { AlertCircle, Clock, Database, Play } from 'lucide-react';
import { FaRedo, FaStop, FaPlay } from 'react-icons/fa';

export function HistoryRestoreDialog({ 
  isOpen, 
  onClose, 
  onRestoreTask,
  onCancelTask 
}) {
  const [historyTasks, setHistoryTasks] = useState([]);
  const [selectedTask, setSelectedTask] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (isOpen) {
      fetchHistoryTasks();
    }
  }, [isOpen]);

  const fetchHistoryTasks = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/v1/hitl/interrupts?status=interrupted&limit=50');
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data.success) {
        setHistoryTasks(data.data.interrupts);
      } else {
        throw new Error(data.message || 'Failed to fetch history tasks');
      }
    } catch (err) {
      setError('Failed to fetch history tasks: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRestoreTask = async () => {
    if (!selectedTask) return;
    
    try {
      const response = await fetch(`/api/v1/hitl/interrupts/${selectedTask.execution_id}/restore`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data.success) {
        await onRestoreTask(selectedTask);
        onClose();
      } else {
        throw new Error(data.message || 'Failed to restore task');
      }
    } catch (error) {
      console.error('Error restoring task:', error);
      setError('Failed to restore task: ' + error.message);
    }
  };

  const handleCancelTask = async () => {
    if (!selectedTask) return;
    
    try {
      const response = await fetch(`/api/v1/hitl/interrupts/${selectedTask.execution_id}/cancel`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data.success) {
        await onCancelTask(selectedTask);
        onClose();
      } else {
        throw new Error(data.message || 'Failed to cancel task');
      }
    } catch (error) {
      console.error('Error cancelling task:', error);
      setError('Failed to cancel task: ' + error.message);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-4xl max-h-[90vh] overflow-y-auto">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <AlertCircle className="h-5 w-5 text-purple-500" />
                Restore from History
              </CardTitle>
              <CardDescription>
                Select an interrupted task to restore and continue execution
              </CardDescription>
            </div>
            <Badge variant="secondary">
              {historyTasks.length} Tasks
            </Badge>
          </div>
        </CardHeader>
        
        <CardContent className="space-y-6">
          {loading && (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
              <span className="ml-2">Loading history tasks...</span>
            </div>
          )}

          {error && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
              <div className="flex items-center">
                <AlertCircle className="h-5 w-5 text-red-500 mr-3" />
                <div>
                  <h3 className="text-lg font-semibold text-red-800 dark:text-red-200">
                    Error
                  </h3>
                  <p className="text-sm text-red-600 dark:text-red-300 mt-1">
                    {error}
                  </p>
                </div>
              </div>
            </div>
          )}

          {!loading && !error && (
            <>
              {historyTasks.length === 0 ? (
                <div className="text-center py-8">
                  <Database className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-semibold text-gray-600 dark:text-gray-400 mb-2">
                    No History Tasks
                  </h3>
                  <p className="text-sm text-gray-500 dark:text-gray-500">
                    There are no interrupted tasks available for restoration.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">Select Task to Restore</h3>
                  
                  <div className="grid gap-3">
                    {historyTasks.map((task) => (
                      <Card 
                        key={task.id}
                        className={`cursor-pointer transition-all duration-200 ${
                          selectedTask?.id === task.id 
                            ? 'ring-2 ring-purple-500 bg-purple-50 dark:bg-purple-900/20' 
                            : 'hover:bg-gray-50 dark:hover:bg-gray-800'
                        }`}
                        onClick={() => setSelectedTask(task)}
                      >
                        <CardContent className="p-4">
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-2">
                                <Badge variant="destructive" className="text-xs">
                                  {task.status}
                                </Badge>
                                <span className="text-sm text-gray-500 dark:text-gray-400">
                                  {task.execution_id}
                                </span>
                              </div>
                              
                              <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-1">
                                {task.user_input}
                              </h4>
                              
                              <div className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400">
                                <div className="flex items-center gap-1">
                                  <Database className="h-4 w-4" />
                                  {task.node_name}
                                </div>
                                <div className="flex items-center gap-1">
                                  <Clock className="h-4 w-4" />
                                  {task.interrupted_at}
                                </div>
                              </div>
                            </div>
                            
                            <div className="flex items-center gap-2">
                              <div className={`w-3 h-3 rounded-full ${
                                selectedTask?.id === task.id ? 'bg-purple-500' : 'bg-gray-300'
                              }`}></div>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          <Separator />

          {/* Action Buttons */}
          <div className="flex gap-3 justify-end">
            <Button
              variant="outline"
              onClick={onClose}
              disabled={loading}
            >
              Close
            </Button>
            
            {selectedTask && (
              <>
                <Button
                  variant="outline"
                  onClick={handleCancelTask}
                  disabled={loading}
                  className="flex items-center gap-2 text-red-600 hover:text-red-700 border-red-200 hover:border-red-300"
                >
                  <FaStop className="h-4 w-4" />
                  Cancel Task
                </Button>
                <Button
                  onClick={handleRestoreTask}
                  disabled={loading}
                  className="flex items-center gap-2 text-purple-600 hover:text-purple-700 border-purple-200 hover:border-purple-300"
                >
                  <FaPlay className="h-4 w-4" />
                  Restore Task
                </Button>
              </>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
