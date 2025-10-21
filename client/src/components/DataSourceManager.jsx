import { useState, useEffect } from 'react';
import { FaDatabase, FaPlus, FaEdit, FaTrash, FaCheck, FaUpload, FaFile, FaExclamationTriangle, FaTimes, FaLightbulb } from 'react-icons/fa';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogOverlay, DialogPortal } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';

const API_BASE_URL = '/api/v1';

function DataSourceManager() {
  const { t } = useTranslation();
  const [datasources, setDatasources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showFilesModal, setShowFilesModal] = useState(false);
  const [selectedDatasource, setSelectedDatasource] = useState(null);
  const [files, setFiles] = useState([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [alert, setAlertMessage] = useState(null);
  const [pollingFileId, setPollingFileId] = useState(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);

  const [newDatasource, setNewDatasource] = useState({ 
    name: '', 
    description: '', 
    type: 'knowledge_base' 
  });

  const dismissAlert = () => setAlertMessage(null);

  useEffect(() => {
    loadDatasources();
  }, []);

  const loadDatasources = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE_URL}/datasources`);
      const response = await res.json();
      
      if (response.success) {
        const filteredDatasources = response.data.filter(ds => ds.type !== 'default');
        setDatasources(filteredDatasources);
      } else {
        setAlertMessage({ type: 'danger', message: response.error || t('fetchingDataSourcesFailed') });
      }
    } catch (error) {
      setAlertMessage({ type: 'danger', message: t('networkErrorRetry') });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateDatasource = async (e) => {
    e.preventDefault();
    dismissAlert();
    
    if (!newDatasource.name.trim()) {
      setAlertMessage({ type: 'warning', message: t('dataSource.enterName') });
      return;
    }

    try {
      const res = await fetch(`${API_BASE_URL}/datasources`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(newDatasource)
      });
      const response = await res.json();
      
      if (response.success) {
        await loadDatasources();
        setShowCreateModal(false);
        setNewDatasource({ name: '', description: '', type: 'hybrid' });
        setAlertMessage({ type: 'success', message: response.message || t('dataSource.createSuccess', { name: newDatasource.name }) });
      } else {
        setAlertMessage({ type: 'danger', message: response.error || t('creatingDataSourceFailed') });
      }
    } catch (error) {
      setAlertMessage({ type: 'danger', message: t('networkErrorRetry') });
    }
  };

  const handleActivateDatasource = async (id) => {
    dismissAlert();
    try {
      const res = await fetch(`${API_BASE_URL}/datasources/${id}/activate`, {
        method: 'POST'
      });
      const response = await res.json();
      
      if (response.success) {
        await loadDatasources();
        setAlertMessage({ type: 'success', message: response.message || t('dataSource.activateSuccess') });
      } else {
        setAlertMessage({ type: 'danger', message: response.error || t('activatingDataSourceFailed') });
      }
    } catch (error) {
      setAlertMessage({ type: 'danger', message: t('networkErrorRetry') });
    }
  };

  const handleDeleteDatasource = (id, name, isActive) => {
    dismissAlert();
    if (isActive) {
      setAlertMessage({ type: 'warning', message: t('dataSource.cannotDeleteActive') });
      return;
    }
    setDeleteTarget({ id, name, type: 'datasource' });
    setShowDeleteModal(true);
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    
    try {
      const res = await fetch(`${API_BASE_URL}/datasources/${deleteTarget.id}`, {
        method: 'DELETE'
      });
      const response = await res.json();
      
      if (response.success) {
        await loadDatasources();
        setAlertMessage({ type: 'success', message: response.message || t('dataSource.deleteSuccess') });
      } else {
        setAlertMessage({ type: 'danger', message: response.error || t('deletingDataSourceFailed') });
      }
    } catch (error) {
      setAlertMessage({ type: 'danger', message: t('networkErrorRetry') });
    } finally {
      setShowDeleteModal(false);
      setDeleteTarget(null);
    }
  };

  const handleShowFiles = async (datasource, isPollingRefresh = false) => {
    if (!isPollingRefresh) {
        dismissAlert();
        setSelectedDatasource(datasource);
        setShowFilesModal(true);
        setFilesLoading(true);
        setFiles([]);
    } else if (!selectedDatasource || selectedDatasource.id !== datasource.id) {
        return; 
    }

    if (!datasource || datasource.id === undefined) {
        if (!isPollingRefresh) setAlertMessage({ type: 'warning', message: t('invalidDataSourceSelection') });
        if (!isPollingRefresh) setFilesLoading(false);
        return;
    }

    try {
      if (!isPollingRefresh || files.length === 0) {
        setFilesLoading(true);
      }
      const res = await fetch(`${API_BASE_URL}/datasources/${datasource.id}/files`);
      const response = await res.json();
      
      if (response.success) {
        setFiles(response.data || []);
      } else {
        if (!isPollingRefresh) setAlertMessage({ type: 'danger', message: response.error || t('fetchingFilesFailed') });
        if (!isPollingRefresh) setFiles([]);
      }
    } catch (error) {
      if (!isPollingRefresh) setAlertMessage({ type: 'danger', message: t('networkErrorRetry') });
      if (!isPollingRefresh) setFiles([]);
    } finally {
       if (!isPollingRefresh || (isPollingRefresh && files.length === 0 && !response?.success)) {
         setFilesLoading(false);
       }
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    dismissAlert();
    if (!file) return;

    if (!selectedDatasource || selectedDatasource.id === undefined) {
        setAlertMessage({ type: 'warning', message: t('noDataSourceSelectedForUpload')});
        return;
    }
    if (selectedDatasource.type === 'default') {
        setAlertMessage({ type: 'error', message: t('defaultDSNoFileManagement') });
        return;
    }

    const fileExtension = file.name.split('.').pop().toLowerCase();
    
    // Only document types are supported now
    const allowedTypes = ['pdf', 'txt', 'docx', 'md'];
    const typeErrorMessage = t('unsupportedFileTypeDoc', { allowedTypes: allowedTypes.join(', ') });
    
    if (!allowedTypes.includes(fileExtension)) {
      setAlertMessage({ 
        type: 'warning', 
        message: typeErrorMessage
      });
      return;
    }

    // Max 100MB
    const maxSizeMB = 100;
    if (file.size > maxSizeMB * 1024 * 1024) { 
      setAlertMessage({ type: 'warning', message: t('fileTooLarge', {maxSize: maxSizeMB}) });
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
      setUploadLoading(true);
      const res = await fetch(`${API_BASE_URL}/datasources/${selectedDatasource.id}/files/upload`, {
        method: 'POST',
        body: formData
      });
      const response = await res.json();
      
      if (response.success && response.file_id) {
        setAlertMessage({ type: 'success', message: response.message || t('file.uploadSuccess') });
        
        if (selectedDatasource) {
            await handleShowFiles(selectedDatasource); 
        }
        await loadDatasources();

        setPollingFileId(response.file_id);

      } else {
        setAlertMessage({ type: 'danger', message: response.error || t('uploadingFileFailed') });
      }
    } catch (error) {
      setAlertMessage({ type: 'danger', message: t('networkErrorRetry') });
    } finally {
      setUploadLoading(false);
      e.target.value = '';
      const fileNameDisplay = document.getElementById('fileNameDisplay');
      if (fileNameDisplay) {
        fileNameDisplay.textContent = t('file.modal.noFileChosen');
      }
    }
  };

  useEffect(() => {
    if (!pollingFileId || !showFilesModal || !selectedDatasource) {
      return;
    }

    let attempts = 0;
    const maxAttempts = 10;
    const pollInterval = 3000;

    const intervalId = setInterval(async () => {
      attempts++;
      if (!showFilesModal || !selectedDatasource) {
        clearInterval(intervalId);
        setPollingFileId(null);
        return;
      }
      
      await handleShowFiles(selectedDatasource, true);

      const currentFile = files.find(f => f.id === pollingFileId);

      if (currentFile && (currentFile.processing_status === 'completed' || currentFile.processing_status === 'failed')) {
        clearInterval(intervalId);
        setPollingFileId(null);
        if (currentFile.processing_status === 'failed') {
            setAlertMessage({ type: 'warning', message: t('fileProcessingFailedError', {fileName: currentFile.original_filename, error: currentFile.error_message || t('unknownError')}) });
        }
      } else if (attempts >= maxAttempts) {
        clearInterval(intervalId);
        setPollingFileId(null);
        setAlertMessage({ type: 'info', message: t('fileProcessingDelayed') });

      }
    }, pollInterval);

    return () => {
      clearInterval(intervalId);
    };
  }, [pollingFileId, showFilesModal, selectedDatasource, files]);

  const handleDeleteFile = (datasourceId, fileId, fileName) => {
    dismissAlert();
    setDeleteTarget({ id: fileId, name: fileName, type: 'file', datasourceId });
    setShowDeleteModal(true);
  };

  const confirmDeleteFile = async () => {
    if (!deleteTarget || deleteTarget.type !== 'file') return;
    
    try {
      setFilesLoading(true);
      const res = await fetch(`${API_BASE_URL}/datasources/${deleteTarget.datasourceId}/files/${deleteTarget.id}`, {
        method: 'DELETE'
      });
      const response = await res.json();

      if (response.success) {
        setAlertMessage({ type: 'success', message: response.message || t('file.deleteSuccess') });
        if (selectedDatasource && selectedDatasource.id === deleteTarget.datasourceId) {
          await handleShowFiles(selectedDatasource);
        }
        await loadDatasources();
      } else {
        setAlertMessage({ type: 'danger', message: response.error || t('deletingFileFailed') });
        if (selectedDatasource && selectedDatasource.id === deleteTarget.datasourceId) {
            await handleShowFiles(selectedDatasource);
        }
      }
    } catch (error) {
      setAlertMessage({ type: 'danger', message: t('networkErrorRetry') });
    } finally {
      if (!(selectedDatasource && selectedDatasource.id === deleteTarget.datasourceId)) {
          setFilesLoading(false);
      }
      setShowDeleteModal(false);
      setDeleteTarget(null);
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getStatusBadge = (status) => {
    const statusKey = `status${status.charAt(0).toUpperCase() + status.slice(1)}`;
    const statusText = t(statusKey, status);
    
    let className = 'bg-gray-500';
    if (status === 'completed') className = 'bg-green-500';
    else if (status === 'processing') className = 'bg-yellow-500';
    else if (status === 'failed') className = 'bg-red-500';
    
    return <Badge className={className}>{statusText}</Badge>;
  };
  
  const getTypeLabel = (type) => {
    switch (type) {
      case 'knowledge_base':
        return t('dataSourceType.knowledgeBase');
      case 'hybrid':
        return t('dataSourceType.hybrid');
      case 'default':
        return t('dataSourceType.default');
      default:
        return t('unknownType');
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-[80vh]">
        <Spinner className="mr-2" />
        <p className="ml-2">{t('loadingDataSources')}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold flex items-center text-gray-800">
          <FaDatabase className="mr-3 text-indigo-500" />
          {t('dataSourceManagement')}
        </h2>
        <Button 
          onClick={() => { dismissAlert(); setShowCreateModal(true); }}
          className="bg-indigo-600 hover:bg-indigo-700 text-white shadow-md transition-colors duration-200"
        >
          <FaPlus className="mr-2 h-4 w-4" />
          {t('createDataSource')}
        </Button>
      </div>

      {alert && (
        <Alert className={`${alert.type === 'danger' ? 'border-red-200 bg-red-50 text-red-600' : alert.type === 'success' ? 'border-green-200 bg-green-50 text-green-600' : alert.type === 'warning' ? 'border-yellow-200 bg-yellow-50 text-yellow-600' : 'border-blue-200 bg-blue-50 text-blue-600'} relative rounded-lg shadow-sm`}>
          <AlertDescription>
            {alert.message}
          </AlertDescription>
          <button
            onClick={dismissAlert}
            className="absolute top-2 right-2 text-gray-500 hover:text-gray-700 transition-colors"
          >
            <FaTimes className="h-4 w-4" />
          </button>
        </Alert>
      )}

      <Card className="shadow-xl border border-gray-100 bg-white/70">
        <CardHeader className="bg-white/80 text-gray-700 rounded-t-lg border-b border-gray-100">
          <CardTitle className="flex items-center text-xl">
            <FaDatabase className="mr-3 h-7 w-7" />
            {t('dataSourceList')}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <Table>
            <TableHeader>
              <TableRow className="border-purple-100">
                <TableHead className="font-semibold text-purple-600">{t('name')}</TableHead>
                <TableHead className="font-semibold text-purple-600">{t('description')}</TableHead>
                <TableHead className="font-semibold text-purple-600">{t('type')}</TableHead>
                <TableHead className="font-semibold text-purple-600">{t('fileCount')}</TableHead>
                <TableHead className="font-semibold text-purple-600">{t('status')}</TableHead>
                <TableHead className="font-semibold text-purple-600">{t('createdAt')}</TableHead>
                <TableHead className="font-semibold text-purple-600">{t('actions')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {datasources.length > 0 ? datasources.map((datasource) => (
                <TableRow key={datasource.id} className="hover:bg-purple-50 transition-colors">
                  <TableCell>
                    <div className="flex items-center space-x-2">
                      <span className="font-medium">{datasource.name}</span>
                      {datasource.is_active && <Badge className="bg-green-200 text-green-600">{t('currentActive')}</Badge>}
                    </div>
                  </TableCell>
                  <TableCell className="text-gray-600">{datasource.description || t('text.empty')}</TableCell>
                  <TableCell>
                    <Badge className="bg-blue-50 text-blue-600">{getTypeLabel(datasource.type)}</Badge>
                  </TableCell>
                  <TableCell className="font-medium">{datasource.file_count}</TableCell>
                  <TableCell>
                    {datasource.is_active ? (
                      <Badge className="bg-green-200 text-green-600">{t('active')}</Badge>
                    ) : (
                      <Badge variant="secondary" className="bg-gray-50 text-gray-500">{t('inactive')}</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-gray-600">{new Date(datasource.created_at).toLocaleDateString()}</TableCell>
                  <TableCell>
                    <div className="flex space-x-2">
                      {!datasource.is_active && (
                        <Button 
                          variant="outline" 
                          size="sm" 
                          onClick={() => handleActivateDatasource(datasource.id)} 
                          title={t('activate')}
                          className="border-green-200 text-green-500 hover:bg-green-50"
                        >
                          <FaCheck className="h-4 w-4" />
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleShowFiles(datasource)}
                        title={t('dataSource.viewFiles')}
                      >
                        <FaFile className="h-4 w-4 text-blue-500" />
                      </Button>
                      {!datasource.is_active && (
                        <Button 
                          variant="outline" 
                          size="sm" 
                          onClick={() => handleDeleteDatasource(datasource.id, datasource.name, datasource.is_active)} 
                          title={t('delete')}
                          className="border-red-200 text-red-500 hover:bg-red-50"
                        >
                          <FaTrash className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              )) : (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-gray-500 py-8">{t('noDataSourcesFound')}</TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Sample Data Files Section */}
      <Dialog open={showCreateModal} onOpenChange={(open) => { if (!open) { setShowCreateModal(false); dismissAlert(); } }}>
        <DialogPortal>
          <DialogOverlay className="bg-black/50 backdrop-blur-sm" />
          <DialogContent className="sm:max-w-[600px] bg-white/90">
            <DialogHeader className="border-b border-purple-200 pb-6">
              <DialogTitle className="text-2xl font-bold flex items-center text-gray-800">
                <div className="w-8 h-8 bg-gray-200 rounded-lg flex items-center justify-center mr-3">
                  <FaPlus className="h-4 w-4 text-white" />
                </div>
                {t('createNewDataSource')}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-6 pt-4">
              {alert && showCreateModal && (
                <Alert className={`${alert.type === 'danger' ? 'border-red-200 bg-red-50 text-red-600' : alert.type === 'success' ? 'border-green-200 bg-green-50 text-green-600' : alert.type === 'warning' ? 'border-yellow-200 bg-yellow-50 text-yellow-600' : 'border-blue-200 bg-blue-50 text-blue-600'} relative rounded-lg`}>
                  <AlertDescription>
                    {alert.message}
                  </AlertDescription>
                  <button
                    onClick={dismissAlert}
                    className="absolute top-2 right-2 text-gray-500 hover:text-gray-700 transition-colors"
                  >
                    <FaTimes className="h-4 w-4" />
                  </button>
                </Alert>
              )}
              <form onSubmit={handleCreateDatasource} className="space-y-8">
                <div className="space-y-4">
                  <div className="flex items-center space-x-2">
                    <FaDatabase className="h-4 w-4 text-purple-500" />
                    <Label htmlFor="datasourceName" className="text-base font-semibold text-gray-700">{t('dataSourceName')}</Label>
                    <span className="text-red-500">*</span>
                  </div>
                  <Input
                    id="datasourceName"
                    type="text"
                    placeholder={t('enterDataSourceName')}
                    value={newDatasource.name}
                    onChange={(e) => setNewDatasource({ ...newDatasource, name: e.target.value })}
                    required
                    className="border-2 border-purple-200 focus:border-purple-400 focus:ring-purple-300 rounded-xl h-12 text-base transition-all duration-200"
                  />
                </div>
                <div className="space-y-4">
                  <div className="flex items-center space-x-2">
                    <FaEdit className="h-4 w-4 text-purple-500" />
                    <Label htmlFor="datasourceDescription" className="text-base font-semibold text-gray-700">{t('dataSourceDescriptionOptional')}</Label>
                  </div>
                  <Textarea
                    id="datasourceDescription"
                    rows={3}
                    placeholder={t('enterDataSourceDescription')}
                    value={newDatasource.description}
                    onChange={(e) => setNewDatasource({ ...newDatasource, description: e.target.value })}
                    className="border-2 border-purple-200 focus:border-purple-400 focus:ring-purple-300 rounded-xl text-base transition-all duration-200"
                  />
                </div>
                {/* RAG only: hide type selection and intro */}
                <input type="hidden" value={newDatasource.type} />
                <DialogFooter className="pt-6 border-t border-purple-200 space-x-3">
                  <Button 
                    variant="outline" 
                    onClick={() => { setShowCreateModal(false); dismissAlert(); }}
                    className="border-2 border-gray-300 text-gray-700 hover:bg-gray-50 px-6 py-2 rounded-xl transition-all duration-200"
                  >
                    {t('close')}
                  </Button>
                  <Button 
                    type="submit"
                    className="bg-indigo-600 hover:bg-indigo-700 text-white px-8 py-2 rounded-xl shadow-lg transition-all duration-200"
                  >
                    <FaPlus className="mr-2 h-4 w-4" />
                    {t('createDataSource')}
                  </Button>
                </DialogFooter>
                <div className="mt-4 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700">
                  {t('dataSource.ragHintShort') || 'Document RAG data source. Upload PDF/DOCX/TXT and query via RAG.'}
                </div>
              </form>
            </div>
          </DialogContent>
        </DialogPortal>
      </Dialog>

      <Dialog open={showFilesModal} onOpenChange={(open) => { if (!open) { setShowFilesModal(false); setSelectedDatasource(null); dismissAlert(); } }}>
        <DialogPortal>
          <DialogOverlay className="bg-black/50 backdrop-blur-sm" />
          <DialogContent 
            className="!max-w-none w-[60vw] h-[80vh] flex flex-col bg-white p-0 border border-gray-100" 
            style={{ width: '60vw', maxWidth: 'none', height: '80vh' }}
          >
            <DialogHeader className="flex-shrink-0 border-b border-gray-100 pb-4 px-6 pt-6 bg-white/80">
              <DialogTitle className="text-xl font-bold flex items-center text-gray-800">
                <div className="w-6 h-6 bg-gray-200 rounded-lg flex items-center justify-center mr-3">
                  <FaFile className="h-4 w-4 text-white" />
                </div>
                {t('manageFilesFor')} {selectedDatasource ? `"${selectedDatasource.name}"` : ''}
              </DialogTitle>
              <p className="text-gray-600 mt-2 text-sm">{t('file.modal.description') || 'Manage and view files in the data source'}</p>
            </DialogHeader>
            <div className="flex flex-col flex-1 min-h-0 overflow-hidden px-6">
              <div className="flex-shrink-0 pt-4">
                {alert && showFilesModal && (
                  <Alert className={`${alert.type === 'danger' ? 'border-red-300 bg-red-50 text-red-800' : alert.type === 'success' ? 'border-green-300 bg-green-50 text-green-800' : alert.type === 'warning' ? 'border-yellow-300 bg-yellow-50 text-yellow-800' : 'border-blue-300 bg-blue-50 text-blue-800'} relative rounded-lg`}>
                    <AlertDescription>
                      {alert.message}
                    </AlertDescription>
                    <button
                      onClick={dismissAlert}
                      className="absolute top-2 right-2 text-gray-500 hover:text-gray-700 transition-colors"
                    >
                      <FaTimes className="h-4 w-4" />
                    </button>
                  </Alert>
                )}
                {selectedDatasource && (
                  <div className="flex items-center justify-between py-3 border-b border-gray-200 mb-3">
                    <p className="text-gray-600 text-sm">{t('file.modal.currentDS', { name: selectedDatasource?.name || t('unknown') })}</p>
                    <div className="flex items-center space-x-2">
                      <Button variant="outline" size="sm" className="relative h-8 text-sm px-4" disabled={uploadLoading || filesLoading}>
                        <FaUpload className="mr-2 h-4 w-4" />
                        {t('file.modal.chooseFileButton')}
                        <input 
                          id="fileUploadInput" 
                          type="file" 
                          onChange={(e) => {
                            handleFileUpload(e);
                          }}
                          disabled={uploadLoading || filesLoading}
                          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                        />
                      </Button>
                      {uploadLoading && <Spinner className="h-4 w-4" />}
                    </div>
                  </div>
                )}
              </div>
              
              <div className="flex-1 min-h-0 mt-2 overflow-hidden">
                {filesLoading ? (
                  <div className="flex justify-center items-center py-8">
                    <Spinner className="mr-2" />
                    <p>{t('fetchingFiles')}</p>
                  </div>
                ) : (
                  selectedDatasource ? (
                    files.length > 0 ? (
                      <div className="h-full overflow-y-auto border border-gray-200 rounded-lg bg-white">
                        <Table>
                          <TableHeader className="sticky top-0 bg-gray-50 z-10">
                            <TableRow className="border-b border-gray-200">
                              <TableHead className="py-3 px-3 font-semibold text-gray-700 text-sm">{t('fileName')}</TableHead>
                              <TableHead className="py-3 px-3 font-semibold text-gray-700 text-sm w-20 text-center">{t('fileType')}</TableHead>
                              <TableHead className="py-3 px-3 font-semibold text-gray-700 text-sm w-24 text-center">{t('fileSize')}</TableHead>
                              <TableHead className="py-3 px-3 font-semibold text-gray-700 text-sm w-32 text-center">{t('processingStatus')}</TableHead>
                              <TableHead className="py-3 px-3 font-semibold text-gray-700 text-sm w-40 text-center">{t('uploadedAt')}</TableHead>
                              <TableHead className="py-3 px-3 font-semibold text-gray-700 text-sm w-20 text-center">{t('actions')}</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {files.map(file => (
                              <TableRow key={file.id} className="hover:bg-orange-50 border-b border-gray-100">
                                <TableCell className="py-2 px-3 font-medium text-gray-900 text-sm break-all" title={file.original_filename}>
                                  {file.original_filename}
                                </TableCell>
                                <TableCell className="py-2 px-3 text-center">
                                  <Badge className="bg-blue-500 text-xs px-2 py-1">{file.file_type.toUpperCase()}</Badge>
                                </TableCell>
                                <TableCell className="py-2 px-3 text-gray-600 text-sm text-center">{formatFileSize(file.file_size)}</TableCell>
                                <TableCell className="py-2 px-3 text-center">{getStatusBadge(file.processing_status)}</TableCell>
                                <TableCell className="py-2 px-3 text-gray-600 text-xs text-center">{new Date(file.uploaded_at).toLocaleString()}</TableCell>
                                <TableCell className="py-2 px-3 text-center">
                                  <Button 
                                    variant="outline" 
                                    size="sm" 
                                    onClick={() => handleDeleteFile(selectedDatasource.id, file.id, file.original_filename)}
                                    title={`${t('deleteFile')}: ${file.original_filename}`}
                                    className="border-red-200 text-red-500 hover:bg-red-50 hover:border-red-300 h-8 w-8 p-0"
                                  >
                                    <FaTrash className="h-3 w-3" />
                                  </Button>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    ) : (
                      <div className="flex items-center justify-center h-32">
                        <Alert className="max-w-md">
                          <AlertDescription className="text-center">{t('noFilesToDisplay')}</AlertDescription>
                        </Alert>
                      </div>
                    )
                  ) : (
                    <div className="flex items-center justify-center h-32">
                      <Alert className="max-w-md">
                        <AlertDescription className="text-center">{t('noDataSourceSelected')}</AlertDescription>
                      </Alert>
                    </div>
                  )
                )}
              </div>
            </div>
            <DialogFooter className="flex-shrink-0 pt-4 border-t border-orange-200 px-6 pb-6">
              <Button 
                variant="outline" 
                onClick={() => { setShowFilesModal(false); setSelectedDatasource(null); dismissAlert(); }}
                className="border-2 border-gray-300 text-gray-700 hover:bg-gray-50 px-6 py-2 text-sm rounded-lg transition-all duration-200"
              >
                {t('close')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </DialogPortal>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteModal} onOpenChange={setShowDeleteModal}>
        <DialogPortal>
          <DialogOverlay className="bg-black/50 backdrop-blur-sm" />
          <DialogContent className="sm:max-w-[500px] bg-white/90">
            <DialogHeader className="border-b border-red-200 pb-6">
              <DialogTitle className="text-xl font-bold flex items-center text-red-600">
                <div className="w-8 h-8 bg-gray-200 rounded-lg flex items-center justify-center mr-3">
                  <FaExclamationTriangle className="h-4 w-4 text-white" />
                </div>
                {deleteTarget?.type === 'datasource' ? t('deleteConfirmation.datasourceTitle') : t('deleteConfirmation.fileTitle')}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-6 pt-4">
              <div className="flex items-start space-x-4">
                <div className="flex-shrink-0">
                  <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center">
                    <FaExclamationTriangle className="h-6 w-6 text-red-500" />
                  </div>
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-gray-900 mb-3">
                    {t('deleteConfirmation.title')}
                  </h3>
                  <p className="text-gray-600 leading-relaxed mb-4">
                    {deleteTarget?.type === 'datasource' 
                      ? t('deleteConfirmation.datasourceMessage', { name: deleteTarget?.name })
                      : t('deleteConfirmation.fileMessage', { name: deleteTarget?.name })
                    }
                  </p>
                  <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-xl">
                    <div className="flex items-center">
                      <FaExclamationTriangle className="h-5 w-5 text-yellow-600 mr-3" />
                      <span className="text-sm text-yellow-800 font-medium">
                        {t('deleteConfirmation.warning')}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <DialogFooter className="pt-6 border-t border-red-200 space-x-3">
              <Button 
                variant="outline" 
                onClick={() => { setShowDeleteModal(false); setDeleteTarget(null); }}
                className="border-2 border-gray-300 text-gray-700 hover:bg-gray-50 px-6 py-2 rounded-xl transition-all duration-200"
              >
                {t('deleteConfirmation.cancel')}
              </Button>
              <Button 
                onClick={deleteTarget?.type === 'datasource' ? confirmDelete : confirmDeleteFile}
                className="bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 text-white px-8 py-2 rounded-xl shadow-lg transition-all duration-200 transform hover:scale-105"
              >
                <FaTrash className="mr-2 h-4 w-4" />
                {t('deleteConfirmation.confirm')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </DialogPortal>
      </Dialog>
    </div>
  );
}

export default DataSourceManager; 