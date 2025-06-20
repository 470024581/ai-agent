import { useState, useEffect } from 'react'
import { FaPaperPlane, FaBrain, FaComments, FaLightbulb, FaDatabase } from 'react-icons/fa'
import { queryAPI } from '../services/api'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Spinner } from '@/components/ui/spinner'

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

  const handleDataSourceChange = async (value) => {
    const newDataSourceId = parseInt(value)
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
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold flex items-center bg-gradient-to-r from-orange-400 to-pink-400 bg-clip-text text-transparent">
          <FaBrain className="mr-3 text-orange-300" />
          {t('queryPage.title')}
        </h2>
      </div>

      <Card className="shadow-xl border-0 bg-gradient-to-br from-orange-25 to-pink-25 dark:from-orange-950 dark:to-pink-950">
        <CardHeader className="bg-gradient-to-r from-orange-200 to-pink-200 text-gray-700 rounded-t-lg">
          <CardTitle className="flex items-center text-xl">
            <FaBrain className="mr-3 h-7 w-7" />
            {t('queryPage.intelligentQASystem')}
          </CardTitle>
                      <p className="text-gray-600 mt-2 font-medium">
              {t('queryPage.subtitle')} {activeDataSourceInfo.name && `(${t('queryPage.dataSourceDropdownLabel')}: ${activeDataSourceInfo.name})`}
            </p>
        </CardHeader>
        <CardContent className="p-6 space-y-6">
          <Alert className="border-yellow-200 bg-yellow-25 text-yellow-600 dark:border-yellow-800 dark:bg-yellow-950 dark:text-yellow-200">
            <FaLightbulb className="h-5 w-5 text-yellow-400" />
            <AlertDescription className="ml-2">
              <strong>{t('queryPage.devModeInfo.title')}</strong>{' '}
              {t('queryPage.devModeInfo.message')}
            </AlertDescription>
          </Alert>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-3">
              <Label htmlFor="queryTextarea" className="text-base font-semibold flex items-center">
                <FaComments className="mr-2 h-5 w-5 text-pink-300" />
                {t('queryPage.inputLabel')}
              </Label>
              <Textarea
                id="queryTextarea"
                rows={4}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t('queryPage.inputPlaceholder')}
                disabled={loading}
                className="border-orange-200 focus:border-pink-300 focus:ring-pink-300 text-base rounded-lg shadow-sm"
              />
            </div>
            
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-end">
              <div className="lg:col-span-2 space-y-3">
                <Label className="text-base font-semibold flex items-center">
                  <FaDatabase className="mr-2 h-5 w-5 text-purple-300" />
                  {t('queryPage.dataSourceDropdownLabel')}
                </Label>
                <Select 
                  value={activeDataSourceInfo.id?.toString() || ''} 
                  onValueChange={handleDataSourceChange}
                  disabled={loadingDataSources || loading}
                >
                  <SelectTrigger className="border-purple-200 focus:border-purple-300 focus:ring-purple-300 rounded-lg">
                    <SelectValue placeholder={loadingDataSources ? t('loading') : t('selectDataSource')} />
                  </SelectTrigger>
                  <SelectContent>
                    {!loadingDataSources && availableDataSources.map(ds => (
                      <SelectItem key={ds.id} value={ds.id.toString()}>
                        {ds.name} ({t(`dataSourceType.${ds.type}`, ds.type)})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <Button 
                type="submit" 
                disabled={loading || !query.trim() || loadingDataSources}
                className="h-12 bg-gradient-to-r from-orange-300 to-pink-300 hover:from-orange-400 hover:to-pink-400 text-white shadow-lg rounded-lg font-semibold text-base transition-all duration-300 transform hover:scale-105"
                size="lg"
              >
                {loading && !loadingDataSources ? (
                  <>
                    <Spinner className="mr-2 h-5 w-5" />
                    {t('queryPage.buttonProcessing')}
                  </>
                ) : (
                  <>
                    <FaPaperPlane className="mr-2 h-5 w-5" />
                    {t('queryPage.buttonSendQuery')}
                  </>
                )}
              </Button>
            </div>
          </form>

          <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-orange-100 dark:border-gray-700 shadow-md">
            <h6 className="text-gray-800 dark:text-gray-200 text-base font-bold flex items-center mb-4">
              <FaComments className="mr-2 h-5 w-5 text-purple-300" />
              {t('queryPage.exampleQueries.title')}
            </h6>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {exampleQueries.map((example, index) => (
                <Button
                  key={index}
                  variant="outline"
                  size="sm"
                  onClick={() => handleExampleClick(example)}
                  disabled={loading}
                  className="text-left justify-start border-purple-200 hover:border-pink-300 hover:text-pink-500 hover:bg-pink-25 transition-all duration-200 rounded-lg h-auto py-3 text-sm"
                >
                  {example}
                </Button>
              ))}
            </div>
          </div>

          {error && (
            <Alert className="border-red-200 bg-red-25 text-red-600 dark:border-red-800 dark:bg-red-950 dark:text-red-200 rounded-lg">
              <AlertDescription className="font-medium">{error}</AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {response && (
        <Card className="shadow-xl border-0 bg-gradient-to-br from-emerald-25 to-teal-25 dark:from-emerald-950 dark:to-teal-950">
          <CardHeader className="bg-gradient-to-r from-emerald-200 to-teal-200 text-gray-700 rounded-t-lg">
            <CardTitle className="flex items-center text-xl">
              <FaLightbulb className="mr-3 h-7 w-7" />
              {t('queryPage.results.title')}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6 space-y-6">
            <div className="prose prose-lg max-w-none">
              <p className="text-gray-800 dark:text-gray-200 leading-relaxed text-lg font-medium bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-emerald-100">
                {response.answer}
              </p>
            </div>
            
            {response.data && (
              <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-teal-100 dark:border-gray-700 shadow-md">
                <h6 className="font-bold text-gray-800 dark:text-gray-200 mb-4 flex items-center">
                  <FaDatabase className="mr-2 h-5 w-5 text-teal-300" />
                  {t('queryPage.results.dataTitle')}
                </h6>
                <pre className="text-sm bg-gray-50 dark:bg-gray-900 p-4 rounded-lg border overflow-auto font-mono" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                  {JSON.stringify(response.data, null, 2)}
                </pre>
              </div>
            )}
            
            {response.suggestions && response.suggestions.length > 0 && (
              <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-yellow-100 dark:border-gray-700 shadow-md">
                <h6 className="font-bold text-gray-800 dark:text-gray-200 mb-4 flex items-center">
                  <FaLightbulb className="mr-2 h-5 w-5 text-yellow-400" />
                  {t('queryPage.results.suggestionsTitle')}
                </h6>
                <ul className="space-y-3">
                  {response.suggestions.map((s, i) => (
                    <li key={i} className="flex items-start bg-yellow-25 dark:bg-yellow-950 p-3 rounded-lg">
                      <span className="inline-block w-2 h-2 bg-yellow-300 rounded-full mt-2 mr-3 flex-shrink-0"></span>
                      <span className="text-gray-700 dark:text-gray-300">{s}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {queryHistory.length > 0 && (
        <Card className="shadow-xl border-0">
          <CardHeader className="bg-gradient-to-r from-purple-200 to-indigo-200 text-gray-700 rounded-t-lg">
            <CardTitle className="flex items-center text-xl">
              <FaComments className="mr-3 h-7 w-7" />
              {t('queryPage.history.title')}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6 space-y-4">
            {queryHistory.slice().reverse().map((item, index) => (
              <Card key={index} className={`transition-all duration-200 hover:shadow-lg transform hover:scale-[1.02] ${item.type === 'mock' ? 'border-l-4 border-l-yellow-300 bg-gradient-to-r from-yellow-25 to-orange-25 dark:from-yellow-950 dark:to-orange-950' : 'border-l-4 border-l-purple-300 bg-gradient-to-r from-purple-25 to-pink-25 dark:from-purple-950 dark:to-pink-950'}`}>
                <CardHeader className={`py-3 ${item.type === 'mock' ? 'bg-gradient-to-r from-yellow-50 to-orange-50 dark:from-yellow-900 dark:to-orange-900' : 'bg-gradient-to-r from-purple-50 to-pink-50 dark:from-purple-900 dark:to-pink-900'}`}>
                  <div className="text-sm font-medium flex items-center justify-between">
                    <span className={item.type === 'mock' ? 'text-yellow-600 dark:text-yellow-200' : 'text-purple-600 dark:text-purple-200'}>
                      {new Date(item.timestamp).toLocaleString()}
                    </span>
                    <span className={`px-3 py-1 rounded-full text-xs font-bold ${item.type === 'mock' ? 'bg-yellow-200 text-yellow-600' : 'bg-purple-200 text-purple-600'}`}>
                      {item.type === 'mock' ? t('queryPage.history.mockLabel') : t('queryPage.history.apiLabel')}
                    </span>
                  </div>
                </CardHeader>
                <CardContent className="py-4">
                  <div className="space-y-3">
                    <div className="bg-white dark:bg-gray-800 p-3 rounded-lg shadow-sm">
                      <strong className="text-gray-700 dark:text-gray-300">{t('queryPage.history.query')}:</strong>
                      <p className="mt-1 text-gray-800 dark:text-gray-200 font-medium">{item.query}</p>
                    </div>
                    <div className="bg-white dark:bg-gray-800 p-3 rounded-lg shadow-sm">
                      <strong className="text-gray-700 dark:text-gray-300">{t('queryPage.history.answer')}:</strong>
                      <p className="mt-1 text-gray-800 dark:text-gray-200">{item.response.answer}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export default QueryForm 