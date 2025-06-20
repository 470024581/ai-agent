import { useState, useEffect } from 'react';
import { Card, Button, Modal, Form, Alert, Table, Badge, Spinner, Row, Col } from 'react-bootstrap';
import { FaDatabase, FaPlus, FaEdit, FaTrash, FaCheck, FaUpload, FaFile, FaExclamationTriangle, FaTimes } from 'react-icons/fa';
import { useTranslation } from 'react-i18next';

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
    
    let variant = 'secondary';
    if (status === 'completed') variant = 'success';
    else if (status === 'processing') variant = 'warning';
    else if (status === 'failed') variant = 'danger';
    
    return <Badge bg={variant}>{statusText}</Badge>;
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
      <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '80vh' }}>
        <Spinner animation="border" role="status">
          <span className="visually-hidden">{t('loading')}</span>
        </Spinner>
        <p className="ms-2 mb-0">{t('loadingDataSources')}</p>
      </div>
    );
  }

  return (
    <>
      <Row className="mb-3">
        <Col>
          <h2><FaDatabase className="me-2" />{t('dataSourceManagement')}</h2>
        </Col>
        <Col className="text-end">
          <Button variant="primary" onClick={() => { dismissAlert(); setShowCreateModal(true); }}>
            <FaPlus className="me-2" />{t('createDataSource')}
          </Button>
        </Col>
      </Row>

      {alert && (
        <Alert variant={alert.type} onClose={dismissAlert} dismissible>
          {alert.message}
        </Alert>
      )}

      <Card>
        <Card.Header>{t('dataSourceList')}</Card.Header>
        <Card.Body>
          <Table striped bordered hover responsive>
            <thead>
              <tr>
                <th>{t('name')}</th>
                <th>{t('description')}</th>
                <th>{t('type')}</th>
                <th>{t('fileCount')}</th>
                <th>{t('status')}</th>
                <th>{t('createdAt')}</th>
                <th>{t('actions')}</th>
              </tr>
            </thead>
            <tbody>
              {datasources.length > 0 ? datasources.map(ds => (
                <tr key={ds.id}>
                  <td>{ds.name} {ds.is_active && <Badge bg="success" pill>{t('currentActive')}</Badge>}</td>
                  <td>{ds.description || t('text.empty')}</td>
                  <td>{getTypeLabel(ds.type)}</td>
                  <td>{ds.file_count}</td>
                  <td>
                    {ds.is_active ? (
                      <Badge bg="success">{t('active')}</Badge>
                    ) : (
                      <Badge bg="secondary">{t('inactive')}</Badge>
                    )}
                  </td>
                  <td>{new Date(ds.created_at).toLocaleDateString()}</td>
                  <td>
                    {!ds.is_active && (
                      <Button variant="outline-success" size="sm" className="me-2 mb-1" onClick={() => handleActivateDatasource(ds.id)} title={t('activate')}>
                        <FaCheck />
                      </Button>
                    )}
                    <Button variant="outline-primary" size="sm" className="me-2 mb-1" onClick={() => handleShowFiles(ds)} title={t('manageFiles')}>
                      <FaFile />
                    </Button>
                    {ds.id !== 1 && (
                      <Button variant="outline-danger" size="sm" className="mb-1" onClick={() => handleDeleteDatasource(ds.id, ds.name)} title={t('delete')}>
                        <FaTrash />
                      </Button>
                    )}
                  </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan="7" className="text-center">{t('noDataSourcesFound')}</td>
                </tr>
              )}
            </tbody>
          </Table>
        </Card.Body>
      </Card>

      {/* Sample Data Files Section */}
      {sampleFiles.length > 0 && (
        <Card className="mt-4">
          <Card.Header>{t('sampleFiles.title')}</Card.Header>
          <Card.Body>
            <p>{t('sampleFiles.description')}</p>
            <Row xs={1} sm={2} md={3} lg={4} xl={5} className="g-2">
              {sampleFiles.map(file => (
                <Col key={file.filename}>
                  <Button 
                    variant="outline-secondary" 
                    className="w-100 mb-2" 
                    onClick={() => handleDownloadSampleFile(file.filename)}
                  >
                    <FaFile className="me-2" />
                    {t('sampleFiles.downloadButton', { year: file.year })}
                  </Button>
                </Col>
              ))}
            </Row>
          </Card.Body>
        </Card>
      )}

      <Modal show={showCreateModal} onHide={() => { setShowCreateModal(false); dismissAlert(); }} centered>
        <Modal.Header closeButton>
          <Modal.Title>{t('createNewDataSource')}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {alert && showCreateModal && (
            <Alert variant={alert.type} onClose={dismissAlert} dismissible>
              {alert.message}
            </Alert>
          )}
          <Form onSubmit={handleCreateDatasource}>
            <Form.Group className="mb-3" controlId="formDatasourceName">
              <Form.Label>{t('dataSourceName')}</Form.Label>
              <Form.Control
                type="text"
                placeholder={t('enterDataSourceName')}
                value={newDatasource.name}
                onChange={(e) => setNewDatasource({ ...newDatasource, name: e.target.value })}
                required
              />
            </Form.Group>
            <Form.Group className="mb-3" controlId="formDatasourceDescription">
              <Form.Label>{t('dataSourceDescriptionOptional')}</Form.Label>
              <Form.Control
                as="textarea"
                rows={3}
                placeholder={t('enterDataSourceDescription')}
                value={newDatasource.description}
                onChange={(e) => setNewDatasource({ ...newDatasource, description: e.target.value })}
              />
            </Form.Group>
            <Form.Group className="mb-3" controlId="formDatasourceType">
              <Form.Label>{t('type')}</Form.Label>
              <Form.Select
                value={newDatasource.type}
                onChange={(e) => setNewDatasource({ ...newDatasource, type: e.target.value })}
              >
                <option value="sql_table_from_file">{t('formattedDataTableSQL')}</option>
                <option value="knowledge_base">{t('knowledgeBaseDocsRAG')}</option>
                
              </Form.Select>
            </Form.Group>
            <Button variant="secondary" onClick={() => { setShowCreateModal(false); dismissAlert(); }} className="me-2">
              {t('close')}
            </Button>
            <Button variant="primary" type="submit">
              {t('createDataSource')}
            </Button>
          </Form>
        </Modal.Body>
      </Modal>

      <Modal show={showFilesModal} onHide={() => { setShowFilesModal(false); setSelectedDatasource(null); dismissAlert(); }} size="lg" centered>
        <Modal.Header closeButton>
          <Modal.Title>
            {t('manageFilesFor')} {selectedDatasource ? `"${selectedDatasource.name}"` : ''}
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {alert && showFilesModal && (
             <Alert variant={alert.type} onClose={dismissAlert} dismissible>
               {alert.message}
             </Alert>
          )}
          <p>{t('file.modal.currentDS', { name: selectedDatasource?.name || t('unknown') })}</p>
          {selectedDatasource && selectedDatasource.type !== 'default' && (
            <Form.Group className="mb-3">
              <Form.Label htmlFor="fileUploadInput" className="btn btn-outline-primary me-2">
                <FaUpload className="me-2" />
                {t('file.modal.chooseFileButton')}
              </Form.Label>
              <input 
                id="fileUploadInput" 
                type="file" 
                onChange={(e) => {
                  handleFileUpload(e);
                  const fileInput = document.getElementById('fileUploadInput');
                  const fileNameDisplay = document.getElementById('fileNameDisplay');
                  if (fileInput && fileInput.files.length > 0) {
                    fileNameDisplay.textContent = fileInput.files[0].name;
                  } else {
                    fileNameDisplay.textContent = t('file.modal.noFileChosen');
                  }
                }}
                disabled={uploadLoading || filesLoading}
                style={{ display: 'none' }}
              />
              <span id="fileNameDisplay" className="ms-2">{t('file.modal.noFileChosen')}</span> 
              {uploadLoading && <Spinner animation="border" size="sm" className="ms-2" />}
            </Form.Group>
          )}
          
          {filesLoading ? (
            <div className="text-center">
              <Spinner animation="border" role="status">
                <span className="visually-hidden">{t('loading')}</span>
              </Spinner>
              <p>{t('fetchingFiles')}</p>
            </div>
          ) : (
            selectedDatasource && selectedDatasource.type !== 'default' ? (
              files.length > 0 ? (
                <Table striped bordered hover responsive size="sm">
                  <thead>
                    <tr>
                      <th>{t('fileName')}</th>
                      <th>{t('fileType')}</th>
                      <th>{t('fileSize')}</th>
                      <th>{t('processingStatus')}</th>
                      <th>{t('uploadedAt')}</th>
                      <th>{t('actions')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {files.map(file => (
                      <tr key={file.id}>
                        <td>{file.original_filename}</td>
                        <td><Badge bg="info">{file.file_type.toUpperCase()}</Badge></td>
                        <td>{formatFileSize(file.file_size)}</td>
                        <td>{getStatusBadge(file.processing_status)}</td>
                        <td>{new Date(file.uploaded_at).toLocaleString()}</td>
                        <td>
                          <Button 
                            variant="outline-danger" 
                            size="sm" 
                            onClick={() => handleDeleteFile(selectedDatasource.id, file.id, file.original_filename)}
                            title={t('deleteFile')}
                          >
                            <FaTrash />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              ) : (
                <Alert variant="info">{t('noFilesToDisplay')}</Alert>
              )
            ) : (
               <Alert variant="info">{t('defaultDSNoFileManagement')}</Alert>
            )
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => { setShowFilesModal(false); setSelectedDatasource(null); dismissAlert(); }}>
            {t('close')}
          </Button>
        </Modal.Footer>
      </Modal>
    </>
  );
}

export default DataSourceManager; 