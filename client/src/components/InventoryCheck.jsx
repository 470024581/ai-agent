import { useState, useEffect } from 'react'
import { Card, Row, Col, Table, Badge, Button, Alert, ProgressBar } from 'react-bootstrap'
import { FaBoxes, FaExclamationTriangle, FaCheckCircle, FaTimesCircle, FaSyncAlt } from 'react-icons/fa'

function InventoryCheck() {
  const [inventoryData, setInventoryData] = useState([])
  const [loading, setLoading] = useState(false)
  const [summary, setSummary] = useState({
    total: 0,
    lowStock: 0,
    outOfStock: 0,
    healthy: 0
  })

  // 模拟库存数据
  const mockInventoryData = [
    {
      id: 1,
      name: 'Laptop Pro 15"',
      category: '电脑',
      currentStock: 45,
      minStock: 10,
      maxStock: 100,
      lastRestock: '2024-01-15',
      supplier: 'Tech Corp',
      price: 1299.99,
      status: 'healthy'
    },
    {
      id: 2,
      name: 'Wireless Mouse',
      category: '配件',
      currentStock: 8,
      minStock: 20,
      maxStock: 150,
      lastRestock: '2024-01-10',
      supplier: 'AccessoryCo',
      price: 29.99,
      status: 'low'
    },
    {
      id: 3,
      name: 'Mechanical Keyboard',
      category: '配件',
      currentStock: 32,
      minStock: 15,
      maxStock: 80,
      lastRestock: '2024-01-20',
      supplier: 'KeyTech',
      price: 89.99,
      status: 'healthy'
    },
    {
      id: 4,
      name: '4K Monitor',
      category: '显示器',
      currentStock: 0,
      minStock: 8,
      maxStock: 50,
      lastRestock: '2024-01-05',
      supplier: 'DisplayTech',
      price: 399.99,
      status: 'out'
    },
    {
      id: 5,
      name: 'USB-C Cable',
      category: '线缆',
      currentStock: 5,
      minStock: 25,
      maxStock: 200,
      lastRestock: '2024-01-08',
      supplier: 'CableCorp',
      price: 15.99,
      status: 'low'
    },
    {
      id: 6,
      name: 'USB Hub 4-Port',
      category: '配件',
      currentStock: 12,
      minStock: 10,
      maxStock: 60,
      lastRestock: '2024-01-18',
      supplier: 'HubTech',
      price: 24.99,
      status: 'healthy'
    }
  ]

  useEffect(() => {
    loadInventoryData()
  }, [])

  const loadInventoryData = () => {
    setLoading(true)
    // 模拟API调用
    setTimeout(() => {
      const processedData = mockInventoryData.map(item => ({
        ...item,
        status: getStockStatus(item.currentStock, item.minStock),
        stockPercentage: (item.currentStock / item.maxStock) * 100
      }))
      
      setInventoryData(processedData)
      updateSummary(processedData)
      setLoading(false)
    }, 1000)
  }

  const getStockStatus = (current, min) => {
    if (current === 0) return 'out'
    if (current < min) return 'low'
    return 'healthy'
  }

  const updateSummary = (data) => {
    const summary = data.reduce((acc, item) => {
      acc.total++
      if (item.status === 'out') acc.outOfStock++
      else if (item.status === 'low') acc.lowStock++
      else acc.healthy++
      return acc
    }, { total: 0, lowStock: 0, outOfStock: 0, healthy: 0 })

    setSummary(summary)
  }

  const getStatusBadge = (status) => {
    switch (status) {
      case 'healthy':
        return <Badge bg="success"><FaCheckCircle className="me-1" />正常</Badge>
      case 'low':
        return <Badge bg="warning"><FaExclamationTriangle className="me-1" />库存不足</Badge>
      case 'out':
        return <Badge bg="danger"><FaTimesCircle className="me-1" />缺货</Badge>
      default:
        return <Badge bg="secondary">未知</Badge>
    }
  }

  const getProgressVariant = (status) => {
    switch (status) {
      case 'healthy': return 'success'
      case 'low': return 'warning'
      case 'out': return 'danger'
      default: return 'info'
    }
  }

  const alertItems = inventoryData.filter(item => item.status !== 'healthy')

  return (
    <div>
      {/* 警告面板 */}
      {alertItems.length > 0 && (
        <Alert variant="warning" className="mb-4">
          <FaExclamationTriangle className="me-2" />
          <strong>库存警告：</strong> 发现 {alertItems.length} 个产品需要关注
        </Alert>
      )}

      {/* 汇总统计 */}
      <Row className="mb-4">
        <Col md={3}>
          <Card className="text-center h-100">
            <Card.Body>
              <h3 className="text-primary">{summary.total}</h3>
              <small className="text-muted">总产品数</small>
            </Card.Body>
          </Card>
        </Col>
        <Col md={3}>
          <Card className="text-center h-100">
            <Card.Body>
              <h3 className="text-success">{summary.healthy}</h3>
              <small className="text-muted">库存健康</small>
            </Card.Body>
          </Card>
        </Col>
        <Col md={3}>
          <Card className="text-center h-100">
            <Card.Body>
              <h3 className="text-warning">{summary.lowStock}</h3>
              <small className="text-muted">库存不足</small>
            </Card.Body>
          </Card>
        </Col>
        <Col md={3}>
          <Card className="text-center h-100">
            <Card.Body>
              <h3 className="text-danger">{summary.outOfStock}</h3>
              <small className="text-muted">缺货</small>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* 库存详情表格 */}
      <Card className="shadow-sm">
        <Card.Header className="bg-warning text-dark d-flex justify-content-between align-items-center">
          <div>
            <h4 className="mb-0">
              <FaBoxes className="me-2" />
              智能库存检查
            </h4>
            <small>实时库存状态监控与预警</small>
          </div>
          <Button variant="dark" size="sm" onClick={loadInventoryData} disabled={loading}>
            <FaSyncAlt className={loading ? 'fa-spin' : ''} />
          </Button>
        </Card.Header>
        <Card.Body className="p-0">
          {loading ? (
            <div className="text-center p-4">
              <div className="spinner-border text-primary" role="status">
                <span className="visually-hidden">加载中...</span>
              </div>
            </div>
          ) : (
            <Table responsive hover className="mb-0">
              <thead className="table-light">
                <tr>
                  <th>产品名称</th>
                  <th>类别</th>
                  <th>当前库存</th>
                  <th>库存进度</th>
                  <th>状态</th>
                  <th>最小库存</th>
                  <th>最后补货</th>
                  <th>供应商</th>
                  <th>单价</th>
                </tr>
              </thead>
              <tbody>
                {inventoryData.map(item => (
                  <tr key={item.id} className={item.status === 'out' ? 'table-danger' : item.status === 'low' ? 'table-warning' : ''}>
                    <td>
                      <strong>{item.name}</strong>
                    </td>
                    <td>{item.category}</td>
                    <td>
                      <strong className={`text-${item.status === 'healthy' ? 'success' : item.status === 'low' ? 'warning' : 'danger'}`}>
                        {item.currentStock}
                      </strong>
                    </td>
                    <td style={{ width: '150px' }}>
                      <ProgressBar 
                        now={item.stockPercentage} 
                        variant={getProgressVariant(item.status)}
                        size="sm"
                        label={`${Math.round(item.stockPercentage)}%`}
                      />
                    </td>
                    <td>{getStatusBadge(item.status)}</td>
                    <td>{item.minStock}</td>
                    <td>{item.lastRestock}</td>
                    <td>{item.supplier}</td>
                    <td>${item.price}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card.Body>
      </Card>

      {/* 建议行动 */}
      {alertItems.length > 0 && (
        <Card className="mt-4">
          <Card.Header className="bg-info text-white">
            <h5 className="mb-0">🤖 AI 智能建议</h5>
          </Card.Header>
          <Card.Body>
            <h6>基于当前库存状况的建议：</h6>
            <ul className="mb-0">
              {alertItems.map(item => (
                <li key={item.id} className="mb-2">
                  <strong>{item.name}</strong>: 
                  {item.status === 'out' 
                    ? ` 立即补货！建议订购 ${item.maxStock - item.currentStock} 件`
                    : ` 库存偏低，建议补货 ${Math.max(item.minStock * 2 - item.currentStock, 0)} 件`
                  }
                  <small className="text-muted"> (供应商: {item.supplier})</small>
                </li>
              ))}
            </ul>
          </Card.Body>
        </Card>
      )}
    </div>
  )
}

export default InventoryCheck 