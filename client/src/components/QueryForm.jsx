import { useState, useEffect } from 'react'
import { Card, Form, Button, Alert, Spinner, Row, Col } from 'react-bootstrap'
import { FaPaperPlane, FaBrain, FaComments, FaLightbulb, FaDatabase } from 'react-icons/fa'
import { queryAPI } from '../services/api'
import { useTranslation } from 'react-i18next'

const API_BASE_URL = '/api/v1'; // Define API_BASE_URL if not already defined elsewhere

function QueryForm() {
  const { t } = useTranslation()
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [response, setResponse] = useState(null)
  const [error, setError] = useState(null)
  const [queryHistory, setQueryHistory] = useState([])

  const [activeDataSourceInfo, setActiveDataSourceInfo] = useState({ id: null, type: 'default', name: 'Default ' })
  const [availableDataSources, setAvailableDataSources] = useState([])
  const [loadingDataSources, setLoadingDataSources] = useState(true) // For loading dropdown

  const fetchActiveDataSource = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/datasources/active`)
      const result = await res.json()
      if (result.success && result.data) {
        setActiveDataSourceInfo({ id: result.data.id, type: result.data.type, name: result.data.name })
        return { id: result.data.id, type: result.data.type } // Return fetched active DS info
      } else {
        // If no active datasource or error, assume default is active (ID 1)
        // Try to fetch details for datasource ID 1 to confirm its type and name
        try {
          const defaultDsRes = await fetch(`${API_BASE_URL}/datasources/1`)
          const defaultDsResult = await defaultDsRes.json()
          if (defaultDsResult.success && defaultDsResult.data) {
            setActiveDataSourceInfo({ id: defaultDsResult.data.id, type: defaultDsResult.data.type, name: defaultDsResult.data.name })
            return { id: defaultDsResult.data.id, type: defaultDsResult.data.type }
          }
        } catch (fetchDefaultErr) {
          console.error("Failed to fetch default data source (ID 1) details:", fetchDefaultErr)
        }
        setActiveDataSourceInfo({ id: 1, type: 'default', name: 'Default ' }) // Fallback hardcoded default
        return { id: 1, type: 'default' }
      }
    } catch (err) {
      console.error("Failed to fetch active data source type:", err)
      setActiveDataSourceInfo({ id: 1, type: 'default', name: 'Default ' }) // Fallback hardcoded default on error
      return { id: 1, type: 'default' }
    }
  }

  const fetchAllDataSources = async () => {
    setLoadingDataSources(true)
    try {
      const res = await fetch(`${API_BASE_URL}/datasources`)
      const result = await res.json()
      if (result.success && result.data) {
        setAvailableDataSources(result.data)
      } else {
        console.error("Failed to fetch available data sources:", result.error)
        setAvailableDataSources([])
      }
    } catch (err) {
      console.error("Failed to fetch available data sources:", err)
      setAvailableDataSources([])
    } finally {
      setLoadingDataSources(false)
    }
  }

  useEffect(() => {
    const initializeDataSources = async () => {
      await fetchAllDataSources() // Fetch all first
      await fetchActiveDataSource() // Then set active, which also updates activeDataSourceInfo.type
    }
    initializeDataSources()
  }, [])

  const handleDataSourceChange = async (event) => {
    const newDataSourceId = parseInt(event.target.value)
    if (!newDataSourceId || newDataSourceId === activeDataSourceInfo.id) return

    setLoading(true) // Use main loading spinner for this action
    setError(null)

    try {
      const res = await fetch(`${API_BASE_URL}/datasources/${newDataSourceId}/activate`, {
        method: 'POST',
      })
      const result = await res.json()
      if (result.success) {
        // Find the newly activated data source details from the availableDataSources list
        const newActiveDs = availableDataSources.find(ds => ds.id === newDataSourceId)
        if (newActiveDs) {
          setActiveDataSourceInfo({ id: newActiveDs.id, type: newActiveDs.type, name: newActiveDs.name })
        }
        // Optionally, you could re-fetch active data source or all data sources to be absolutely sure
        // await fetchActiveDataSource() 
        // await fetchAllDataSources() 
      } else {
        setError(result.error || t('queryPage.activationError'))
        // Revert dropdown to previous active if activation fails? Or just show error.
        // For now, just show error. State `activeDataSourceInfo` won't change unless successful.
      }
    } catch (err) {
      setError(t('networkErrorRetry'))
      console.error("Failed to activate data source:", err)
    } finally {
      setLoading(false)
    }
  }

  // Mock AI response data in English (as a fallback or for dev)
  const generateMockResponse = (queryString) => {
    const responses = {
      'sales trend past 7 days': {
        answer: t('mock.salesTrend7Days.answer'),
        data: {
          totalSales: 24408,
          averageDaily: 3487,
          growth: "+12.5%",
          trend: t('mock.trend.up'),
          dailyData: [
            { date: t('mock.days.mon'), sales: 2400, orders: 24 },
            { date: t('mock.days.tue'), sales: 1398, orders: 18 },
            { date: t('mock.days.wed'), sales: 9800, orders: 45 },
            { date: t('mock.days.thu'), sales: 3908, orders: 32 },
            { date: t('mock.days.fri'), sales: 4800, orders: 38 },
            { date: t('mock.days.sat'), sales: 3800, orders: 28 },
            { date: t('mock.days.sun'), sales: 4300, orders: 35 }
          ]
        },
        suggestions: [
          t('mock.salesTrend7Days.suggestion1'),
          t('mock.salesTrend7Days.suggestion2'),
          t('mock.salesTrend7Days.suggestion3')
        ]
      },
      'this month sales': {
        answer: t('mock.thisMonthSales.answer', { totalSales: "$68,945", growth: "15.2%"}),
        data: {
          monthlySales: 68945,
          lastMonth: 59873,
          growth: 15.2,
          orders: 542,
          avgOrderValue: 127.25
        },
        suggestions: [
          t('mock.thisMonthSales.suggestion1'),
          t('mock.thisMonthSales.suggestion2')
        ]
      },
      'low stock products below 50': {
        answer: t('mock.lowStock50.answer'),
        data: {
          lowStockItems: [
            { name: "Wireless Mouse", stock: 8, minStock: 20, status: "urgent" },
            { name: "4K Monitor", stock: 0, minStock: 8, status: "outOfStock" },
            { name: "USB-C Cable", stock: 5, minStock: 25, status: "urgent" }
          ],
          totalLowStock: 3,
          totalOutOfStock: 1
        },
        suggestions: [
          t('mock.lowStock50.suggestion1'),
          t('mock.lowStock50.suggestion2'),
          t('mock.lowStock50.suggestion3')
        ]
      },
      'top selling products': {
        answer: t('mock.topSelling.answer'),
        data: {
          topProducts: [
            { name: "Laptop Pro 15\"", sales: 4800, percentage: 32.1 },
            { name: "Mechanical Keyboard", sales: 3200, percentage: 21.4 },
            { name: "Wireless Mouse", sales: 2800, percentage: 18.7 },
            { name: "4K Monitor", sales: 2400, percentage: 16.0 },
            { name: "Others", sales: 1800, percentage: 11.8 }
          ]
        },
        suggestions: [
          t('mock.topSelling.suggestion1'),
          t('mock.topSelling.suggestion2'),
          t('mock.topSelling.suggestion3')
        ]
      }
    }

    // Try to find a matching response based on keywords
    const lowerQuery = queryString.toLowerCase()
    for (const [key, value] of Object.entries(responses)) {
      if (lowerQuery.includes(key)) {
        return value
      }
    }

    // Default response if no match
    return {
      answer: t('mock.default.answer', { query: queryString }),
      data: {
        message: t('mock.default.dataMessage'),
        timestamp: new Date().toLocaleString(),
        processed: true
      },
      suggestions: [
        t('mock.default.suggestion1'),
        t('mock.default.suggestion2'),
        t('mock.default.suggestion3')
      ]
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!query.trim()) return

    setLoading(true)
    setError(null)
    setResponse(null) // Clear previous response

    try {
      const result = await queryAPI.sendQuery(query, activeDataSourceInfo.id) // Pass active DS ID
      setResponse(result)
      setQueryHistory(prev => [...prev, { query, response: result, timestamp: new Date(), type: 'api' }])
    } catch (apiError) {
      console.warn(t('queryPage.apiUnavailableMock', { message: apiError.message }))
      
      // Simulate processing time for mock response
      await new Promise(resolve => setTimeout(resolve, 1500))
      
      const mockResponseData = generateMockResponse(query)
      setResponse(mockResponseData)
      setQueryHistory(prev => [...prev, { query, response: mockResponseData, timestamp: new Date(), type: 'mock' }])
    }
    
    setQuery('') // Clear query input after submission
    setLoading(false)
  }

  let exampleQueries = []
  if (activeDataSourceInfo.type === 'knowledge_base') {
    exampleQueries = [
      t('queryPage.exampleQueries.whoAreYou'),
      t('queryPage.exampleQueries.whatDoYouKnow')
    ]
  } else {
    exampleQueries = [
      t('queryPage.exampleQueries.salesMonth'),
      t('queryPage.exampleQueries.lowStock'),
      t('queryPage.exampleQueries.salesTrend7Days'),
      t('queryPage.exampleQueries.topSelling'),
      t('queryPage.exampleQueries.dailySalesReport')
    ]
  }

  const handleExampleClick = (exampleQuery) => {
    setQuery(exampleQuery)
  }

  return (
    <Row>
      <Col lg={8} md={10} className="mx-auto">
        <Card className="shadow-sm mb-4">
          <Card.Header className="bg-primary text-white">
            <h4 className="mb-0">
              <FaBrain className="me-2" />
              {t('queryPage.title')}
            </h4>
            <small>{t('queryPage.subtitle')} {activeDataSourceInfo.name && `(${t('queryPage.dataSourceDropdownLabel')}: ${activeDataSourceInfo.name})`}</small>
          </Card.Header>
          <Card.Body>
            <Alert variant="info" className="mb-3 d-flex align-items-center">
              <FaLightbulb className="me-3 fs-4 text-info" />
              <div>
                <strong>{t('queryPage.devModeInfo.title')}</strong> 
                {t('queryPage.devModeInfo.message')}
              </div>
            </Alert>

            <Form onSubmit={handleSubmit}>
              <Form.Group className="mb-3">
                <Form.Label htmlFor="queryTextarea">{t('queryPage.inputLabel')}</Form.Label>
                <Form.Control
                  as="textarea"
                  id="queryTextarea"
                  rows={3}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={t('queryPage.inputPlaceholder')}
                  disabled={loading}
                />
              </Form.Group>
              <Row className="align-items-center mb-3">
                <Col md={4} className="mb-3 mb-md-0">
                    <Form.Group controlId="dataSourceSelect">
                        <div className="input-group">
                            <span className="input-group-text">
                                <FaDatabase style={{ marginRight: '0.3rem' }} /> 
                                {t('queryPage.dataSourceDropdownLabel')}:
                            </span>
                            <Form.Select 
                                aria-label={t('queryPage.dataSourceDropdownLabel')}
                                value={activeDataSourceInfo.id || ''} 
                                onChange={handleDataSourceChange}
                                disabled={loadingDataSources || loading} 
                            >
                                {loadingDataSources ? (
                                    <option>{t('loading')}</option>
                                ) : (
                                    availableDataSources.map(ds => (
                                        <option key={ds.id} value={ds.id}>
                                            {ds.name} ({t(`dataSourceType.${ds.type}`, ds.type)})
                                        </option>
                                    ))
                                )}
                            </Form.Select>
                        </div>
                    </Form.Group>
                </Col>
                <Col md={2}>
                  <Button 
                    variant="primary" 
                    type="submit" 
                    disabled={loading || !query.trim() || loadingDataSources}
                    className="px-4 py-2 w-100"
                  >
                    {loading && !loadingDataSources ? (
                      <><Spinner size="sm" className="me-2" />{t('queryPage.buttonProcessing')}</>
                    ) : (
                      <><FaPaperPlane className="me-2" />{t('queryPage.buttonSendQuery')}</>
                    )}
                  </Button>
                </Col>
              </Row>
            </Form>

            <div className="mt-4">
              <h6 className="text-muted mb-2">
                <FaComments className="me-1" />
                {t('queryPage.exampleQueries.title')}
              </h6>
              <div className="d-flex flex-wrap gap-2">
                {exampleQueries.map((example, index) => (
                  <Button
                    key={index}
                    variant="outline-secondary"
                    size="sm"
                    onClick={() => handleExampleClick(example)}
                    disabled={loading}
                  >
                    {example}
                  </Button>
                ))}
              </div>
            </div>

            {error && (
              <Alert variant="danger" className="mt-3">
                {error}
              </Alert>
            )}
          </Card.Body>
        </Card>

        {response && (
          <Card className="mt-4 border-primary shadow-sm">
            <Card.Header className="bg-primary text-white">
              <h5 className="mb-0">{t('queryPage.results.title')}</h5>
            </Card.Header>
            <Card.Body>
              <p className="lead">{response.answer}</p>
              {response.data && (
                <div className="mt-3 p-3 bg-light rounded">
                  <h6>{t('queryPage.results.dataTitle')}</h6>
                  <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                    {JSON.stringify(response.data, null, 2)}
                  </pre>
                </div>
              )}
              {response.suggestions && response.suggestions.length > 0 && (
                <div className="mt-3">
                  <h6>{t('queryPage.results.suggestionsTitle')}</h6>
                  <ul>
                    {response.suggestions.map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
              )}
            </Card.Body>
          </Card>
        )}

        {queryHistory.length > 0 && (
          <Card className="mt-4 shadow-sm">
            <Card.Header>
              <h5 className="mb-0">{t('queryPage.history.title')}</h5>
            </Card.Header>
            <Card.Body>
              {queryHistory.slice().reverse().map((item, index) => (
                <Card key={index} className={`mb-3 ${item.type === 'mock' ? 'border-warning' : 'border-info'}`}>
                  <Card.Header className={`small ${item.type === 'mock' ? 'bg-warning text-dark' : 'bg-info text-white'}`}>
                    {new Date(item.timestamp).toLocaleString()} - {item.type === 'mock' ? t('queryPage.history.mockLabel') : t('queryPage.history.apiLabel')}
                  </Card.Header>
                  <Card.Body>
                    <p><strong>{t('queryPage.history.query')}:</strong> {item.query}</p>
                    <p><strong>{t('queryPage.history.answer')}:</strong> {item.response.answer}</p>
                  </Card.Body>
                </Card>
              ))}
            </Card.Body>
          </Card>
        )}
      </Col>
    </Row>
  )
}

export default QueryForm 