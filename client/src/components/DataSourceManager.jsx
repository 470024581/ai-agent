import { useState, useEffect } from 'react';
import { FaDatabase, FaPlus, FaEdit, FaTrash, FaCheck, FaUpload, FaFile, FaExclamationTriangle, FaTimes } from 'react-icons/fa';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '@/components/ui/dialog';
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
  const [sampleFiles, setSampleFiles] = useState([]);

  const [newDatasource, setNewDatasource] = useState({
    name: '',
    description: '',
    type: 'sql_table_from_file'
  });

  const dismissAlert = () => setAlertMessage(null);

  useEffect(() => {
    loadDatasources();
    loadSampleFiles();
  }, []);

  const loadDatasources = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE_URL}/datasources`);
      const response = await res.json();
      
      if (response.success) {
        setDatasources(response.data);
      } else {
        setAlertMessage({ type: 'danger', message: response.error || t('fetchingDataSourcesFailed') });
      }
    } catch (error) {
      setAlertMessage({ type: 'danger', message: t('networkErrorRetry') });
    } finally {
      setLoading(false);
    }
  };

  const loadSampleFiles = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/sample-data-files`);
      const response = await res.json();
      if (response.success) {
        setSampleFiles(response.data || []);
      } else {
        console.error("Failed to load sample files:", response.error);
        setAlertMessage({ type: 'warning', message: t('sampleFiles.loadFailed') });
      }
    } catch (error) {
      console.error("Network error loading sample files:", error);
      setAlertMessage({ type: 'warning', message: t('sampleFiles.networkError') });
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
        setNewDatasource({ name: '', description: '', type: 'sql_table_from_file' });
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

  const handleDeleteDatasource = async (id, name) => {
    dismissAlert();
    if (!window.confirm(t('confirmDeleteDataSource', { name }))) {
      return;
    }

    try {
      const res = await fetch(`${API_BASE_URL}/datasources/${id}`, {
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
     if (datasource.type === 'default') {
        if (!isPollingRefresh) setAlertMessage({ type: 'info', message: t('defaultDSNoFileManagement') });
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
       } else if (isPollingRefresh) {
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
    let allowedTypes = [];
    let typeErrorMessage = '';

    if (selectedDatasource.type === 'sql_table_from_file') {
        allowedTypes = ['csv', 'xlsx'];
        typeErrorMessage = t('unsupportedFileTypeSQL', { allowedTypes: allowedTypes.join(', ') });
    } else { // For knowledge_base and other potential future types that allow uploads
        allowedTypes = ['pdf', 'txt', 'docx', 'csv', 'xlsx'];
        typeErrorMessage = t('unsupportedFileType', { allowedTypes: allowedTypes.join(', ') });
    }
    
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

  const handleDeleteFile = async (datasourceId, fileId, fileName) => {
    dismissAlert();
    if (!window.confirm(t('confirmDeleteFile', { fileName }))) {
      return;
    }

    try {
      setFilesLoading(true);
      const res = await fetch(`${API_BASE_URL}/datasources/${datasourceId}/files/${fileId}`, {
        method: 'DELETE'
      });
      const response = await res.json();

      if (response.success) {
        setAlertMessage({ type: 'success', message: response.message || t('file.deleteSuccess') });
        if (selectedDatasource && selectedDatasource.id === datasourceId) {
          await handleShowFiles(selectedDatasource);
        }
        await loadDatasources();
      } else {
        setAlertMessage({ type: 'danger', message: response.error || t('deletingFileFailed') });
        if (selectedDatasource && selectedDatasource.id === datasourceId) {
            await handleShowFiles(selectedDatasource);
        }
      }
    } catch (error) {
      setAlertMessage({ type: 'danger', message: t('networkErrorRetry') });
    } finally {
      if (!(selectedDatasource && selectedDatasource.id === datasourceId)) {
          setFilesLoading(false);
      }
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
      case 'default':
        return t('defaultERFormatted');
      case 'knowledge_base':
        return t('knowledgeBaseDocsRAG');
      case 'sql_table_from_file':
        return t('formattedDataTableSQL');
      default:
        return t('unknownType');
    }
  };

  const handleDownloadSampleFile = (filename) => {
    window.location.href = `${API_BASE_URL}/sample-data-files/${filename}`;
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
        <h2 className="text-3xl font-bold flex items-center bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
          <FaDatabase className="mr-3 text-purple-300" />
          {t('dataSourceManagement')}
        </h2>
        <Button 
          onClick={() => { dismissAlert(); setShowCreateModal(true); }}
          className="bg-gradient-to-r from-purple-300 to-pink-300 hover:from-purple-400 hover:to-pink-400 text-white shadow-lg transition-all duration-300 transform hover:scale-105"
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

      <Card className="shadow-xl border-0 bg-gradient-to-br from-purple-50 to-pink-50">
        <CardHeader className="bg-gradient-to-r from-purple-200 to-pink-200 text-gray-700 rounded-t-lg">
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
              {datasources.length > 0 ? datasources.map(ds => (
                <TableRow key={ds.id} className="hover:bg-purple-50 transition-colors">
                  <TableCell>
                    <div className="flex items-center space-x-2">
                      <span className="font-medium">{ds.name}</span>
                      {ds.is_active && <Badge className="bg-green-200 text-green-600">{t('currentActive')}</Badge>}
                    </div>
                  </TableCell>
                  <TableCell className="text-gray-600">{ds.description || t('text.empty')}</TableCell>
                  <TableCell>
                    <Badge className="bg-blue-50 text-blue-600">{getTypeLabel(ds.type)}</Badge>
                  </TableCell>
                  <TableCell className="font-medium">{ds.file_count}</TableCell>
                  <TableCell>
                    {ds.is_active ? (
                      <Badge className="bg-green-200 text-green-600">{t('active')}</Badge>
                    ) : (
                      <Badge variant="secondary" className="bg-gray-50 text-gray-500">{t('inactive')}</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-gray-600">{new Date(ds.created_at).toLocaleDateString()}</TableCell>
                  <TableCell>
                    <div className="flex space-x-2">
                      {!ds.is_active && (
                        <Button 
                          variant="outline" 
                          size="sm" 
                          onClick={() => handleActivateDatasource(ds.id)} 
                          title={t('activate')}
                          className="border-green-200 text-green-500 hover:bg-green-50"
                        >
                          <FaCheck className="h-4 w-4" />
                        </Button>
                      )}
                      <Button 
                        variant="outline" 
                        size="sm" 
                        onClick={() => handleShowFiles(ds)} 
                        title={t('manageFiles')}
                        className="border-orange-200 text-orange-500 hover:bg-orange-50"
                      >
                        <FaFile className="h-4 w-4" />
                      </Button>
                      {ds.id !== 1 && (
                        <Button 
                          variant="outline" 
                          size="sm" 
                          onClick={() => handleDeleteDatasource(ds.id, ds.name)} 
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
      {sampleFiles.length > 0 && (
        <Card className="shadow-xl border-0 bg-gradient-to-br from-orange-50 to-yellow-50">
          <CardHeader className="bg-gradient-to-r from-orange-200 to-yellow-200 text-gray-700 rounded-t-lg">
            <CardTitle className="flex items-center text-xl">
              <FaFile className="mr-3 h-7 w-7" />
              {t('sampleFiles.title')}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            <p className="text-gray-600 mb-4 text-base">{t('sampleFiles.description')}</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
              {sampleFiles.map(file => (
                <Button 
                  key={file.filename}
                  variant="outline" 
                  className="w-full border-orange-200 text-orange-500 hover:bg-orange-50 hover:border-orange-300 transition-all" 
                  onClick={() => handleDownloadSampleFile(file.filename)}
                >
                  <FaFile className="mr-2 h-4 w-4" />
                  {t('sampleFiles.downloadButton', { year: file.year })}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Dialog open={showCreateModal} onOpenChange={(open) => { if (!open) { setShowCreateModal(false); dismissAlert(); } }}>
        <DialogContent className="sm:max-w-[500px] bg-gradient-to-br from-purple-50 to-pink-50">
          <DialogHeader className="border-b border-purple-100 pb-4">
            <DialogTitle className="text-xl font-bold flex items-center text-purple-600">
              <FaPlus className="mr-2 h-5 w-5" />
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
            <form onSubmit={handleCreateDatasource} className="space-y-6">
              <div className="space-y-3">
                <Label htmlFor="datasourceName" className="text-base font-semibold text-purple-600">{t('dataSourceName')}</Label>
                <Input
                  id="datasourceName"
                  type="text"
                  placeholder={t('enterDataSourceName')}
                  value={newDatasource.name}
                  onChange={(e) => setNewDatasource({ ...newDatasource, name: e.target.value })}
                  required
                  className="border-purple-200 focus:border-purple-300 focus:ring-purple-300 rounded-lg"
                />
              </div>
              <div className="space-y-3">
                <Label htmlFor="datasourceDescription" className="text-base font-semibold text-purple-600">{t('dataSourceDescriptionOptional')}</Label>
                <Textarea
                  id="datasourceDescription"
                  rows={3}
                  placeholder={t('enterDataSourceDescription')}
                  value={newDatasource.description}
                  onChange={(e) => setNewDatasource({ ...newDatasource, description: e.target.value })}
                  className="border-purple-200 focus:border-purple-300 focus:ring-purple-300 rounded-lg"
                />
              </div>
              <div className="space-y-3">
                <Label htmlFor="datasourceType" className="text-base font-semibold text-purple-800">{t('type')}</Label>
                <Select value={newDatasource.type} onValueChange={(value) => setNewDatasource({ ...newDatasource, type: value })}>
                  <SelectTrigger className="border-purple-300 focus:border-purple-500 focus:ring-purple-500 rounded-lg">
                    <SelectValue placeholder={t('selectType')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="sql_table_from_file">{t('formattedDataTableSQL')}</SelectItem>
                    <SelectItem value="knowledge_base">{t('knowledgeBaseDocsRAG')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <DialogFooter className="pt-4 border-t border-purple-200">
                <Button 
                  variant="outline" 
                  onClick={() => { setShowCreateModal(false); dismissAlert(); }}
                  className="border-gray-300 text-gray-700 hover:bg-gray-50"
                >
                  {t('close')}
                </Button>
                <Button 
                  type="submit"
                  className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white"
                >
                  {t('createDataSource')}
                </Button>
              </DialogFooter>
            </form>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={showFilesModal} onOpenChange={(open) => { if (!open) { setShowFilesModal(false); setSelectedDatasource(null); dismissAlert(); } }}>
        <DialogContent className="max-w-5xl max-h-[85vh] overflow-y-auto bg-gradient-to-br from-orange-50 to-yellow-50">
          <DialogHeader className="border-b border-orange-200 pb-4">
            <DialogTitle className="text-xl font-bold flex items-center text-orange-800">
              <FaFile className="mr-2 h-5 w-5" />
              {t('manageFilesFor')} {selectedDatasource ? `"${selectedDatasource.name}"` : ''}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-6 pt-4">
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
            <p>{t('file.modal.currentDS', { name: selectedDatasource?.name || t('unknown') })}</p>
            {selectedDatasource && selectedDatasource.type !== 'default' && (
              <div className="space-y-2">
                <Label htmlFor="fileUploadInput">{t('file.modal.chooseFileButton')}</Label>
                <div className="flex items-center space-x-2">
                  <Button variant="outline" className="relative" disabled={uploadLoading || filesLoading}>
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
            
            {filesLoading ? (
              <div className="flex justify-center items-center py-8">
                <Spinner className="mr-2" />
                <p>{t('fetchingFiles')}</p>
              </div>
            ) : (
              selectedDatasource && selectedDatasource.type !== 'default' ? (
                files.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('fileName')}</TableHead>
                        <TableHead>{t('fileType')}</TableHead>
                        <TableHead>{t('fileSize')}</TableHead>
                        <TableHead>{t('processingStatus')}</TableHead>
                        <TableHead>{t('uploadedAt')}</TableHead>
                        <TableHead>{t('actions')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {files.map(file => (
                        <TableRow key={file.id}>
                          <TableCell>{file.original_filename}</TableCell>
                          <TableCell><Badge className="bg-blue-500">{file.file_type.toUpperCase()}</Badge></TableCell>
                          <TableCell>{formatFileSize(file.file_size)}</TableCell>
                          <TableCell>{getStatusBadge(file.processing_status)}</TableCell>
                          <TableCell>{new Date(file.uploaded_at).toLocaleString()}</TableCell>
                          <TableCell>
                            <Button 
                              variant="outline" 
                              size="sm" 
                              onClick={() => handleDeleteFile(selectedDatasource.id, file.id, file.original_filename)}
                              title={t('deleteFile')}
                            >
                              <FaTrash className="h-4 w-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <Alert>
                    <AlertDescription>{t('noFilesToDisplay')}</AlertDescription>
                  </Alert>
                )
              ) : (
                <Alert>
                  <AlertDescription>{t('defaultDSNoFileManagement')}</AlertDescription>
                </Alert>
              )
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setShowFilesModal(false); setSelectedDatasource(null); dismissAlert(); }}>
              {t('close')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default DataSourceManager; 