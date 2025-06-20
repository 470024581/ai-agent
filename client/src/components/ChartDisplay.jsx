import { useState, useEffect } from 'react'
import { Card, Row, Col, Button, ButtonGroup } from 'react-bootstrap'
import { FaChartBar, FaChartLine, FaChartPie, FaSyncAlt } from 'react-icons/fa'
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts'

function ChartDisplay() {
  const [chartType, setChartType] = useState('line')
  const [dataType, setDataType] = useState('sales')
  const [loading, setLoading] = useState(false)

  // 模拟销售数据
  const salesData = [
    { name: '周一', sales: 2400, orders: 24 },
    { name: '周二', sales: 1398, orders: 18 },
    { name: '周三', sales: 9800, orders: 45 },
    { name: '周四', sales: 3908, orders: 32 },
    { name: '周五', sales: 4800, orders: 38 },
    { name: '周六', sales: 3800, orders: 28 },
    { name: '周日', sales: 4300, orders: 35 }
  ]

  // 模拟库存数据
  const inventoryData = [
    { name: 'Laptop', stock: 45, minStock: 10 },
    { name: 'Mouse', stock: 8, minStock: 20 },
    { name: 'Keyboard', stock: 32, minStock: 15 },
    { name: 'Monitor', stock: 15, minStock: 8 },
    { name: 'Cable', stock: 5, minStock: 25 },
    { name: 'USB Hub', stock: 12, minStock: 10 }
  ]

  // 模拟产品销量数据
  const productSalesData = [
    { name: 'Laptop', value: 4800, color: '#0088FE' },
    { name: 'Mouse', value: 2800, color: '#00C49F' },
    { name: 'Keyboard', value: 3200, color: '#FFBB28' },
    { name: 'Monitor', value: 2400, color: '#FF8042' },
    { name: 'Others', value: 1800, color: '#8884D8' }
  ]

  const refreshData = () => {
    setLoading(true)
    // 模拟API调用
    setTimeout(() => {
      setLoading(false)
    }, 1000)
  }

  const renderChart = () => {
    const currentData = dataType === 'sales' ? salesData : inventoryData

    switch (chartType) {
      case 'line':
        return (
          <LineChart data={currentData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Legend />
            {dataType === 'sales' ? (
              <>
                <Line type="monotone" dataKey="sales" stroke="#8884d8" strokeWidth={2} />
                <Line type="monotone" dataKey="orders" stroke="#82ca9d" strokeWidth={2} />
              </>
            ) : (
              <>
                <Line type="monotone" dataKey="stock" stroke="#8884d8" strokeWidth={2} />
                <Line type="monotone" dataKey="minStock" stroke="#ff7300" strokeWidth={2} />
              </>
            )}
          </LineChart>
        )

      case 'bar':
        return (
          <BarChart data={currentData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Legend />
            {dataType === 'sales' ? (
              <>
                <Bar dataKey="sales" fill="#8884d8" />
                <Bar dataKey="orders" fill="#82ca9d" />
              </>
            ) : (
              <>
                <Bar dataKey="stock" fill="#8884d8" />
                <Bar dataKey="minStock" fill="#ff7300" />
              </>
            )}
          </BarChart>
        )

      case 'area':
        return (
          <AreaChart data={currentData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Legend />
            {dataType === 'sales' ? (
              <>
                <Area type="monotone" dataKey="sales" stackId="1" stroke="#8884d8" fill="#8884d8" />
                <Area type="monotone" dataKey="orders" stackId="1" stroke="#82ca9d" fill="#82ca9d" />
              </>
            ) : (
              <>
                <Area type="monotone" dataKey="stock" stackId="1" stroke="#8884d8" fill="#8884d8" />
                <Area type="monotone" dataKey="minStock" stackId="1" stroke="#ff7300" fill="#ff7300" />
              </>
            )}
          </AreaChart>
        )

      case 'pie':
        return (
          <PieChart>
            <Pie
              data={productSalesData}
              cx="50%"
              cy="50%"
              labelLine={false}
              label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
              outerRadius={80}
              fill="#8884d8"
              dataKey="value"
            >
              {productSalesData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        )

      default:
        return null
    }
  }

  return (
    <div>
      <Row>
        <Col>
          <Card className="shadow-sm">
            <Card.Header className="bg-info text-white d-flex justify-content-between align-items-center">
              <div>
                <h4 className="mb-0">
                  <FaChartBar className="me-2" />
                  数据可视化面板
                </h4>
                <small>实时数据图表展示</small>
              </div>
              <Button variant="light" size="sm" onClick={refreshData} disabled={loading}>
                <FaSyncAlt className={loading ? 'fa-spin' : ''} />
              </Button>
            </Card.Header>
            <Card.Body>
              {/* 控制面板 */}
              <Row className="mb-4">
                <Col md={6}>
                  <h6>数据类型:</h6>
                  <ButtonGroup>
                    <Button 
                      variant={dataType === 'sales' ? 'primary' : 'outline-primary'}
                      onClick={() => setDataType('sales')}
                      size="sm"
                    >
                      销售数据
                    </Button>
                    <Button 
                      variant={dataType === 'inventory' ? 'primary' : 'outline-primary'}
                      onClick={() => setDataType('inventory')}
                      size="sm"
                    >
                      库存数据
                    </Button>
                  </ButtonGroup>
                </Col>
                <Col md={6}>
                  <h6>图表类型:</h6>
                  <ButtonGroup>
                    <Button 
                      variant={chartType === 'line' ? 'success' : 'outline-success'}
                      onClick={() => setChartType('line')}
                      size="sm"
                    >
                      <FaChartLine /> 折线图
                    </Button>
                    <Button 
                      variant={chartType === 'bar' ? 'success' : 'outline-success'}
                      onClick={() => setChartType('bar')}
                      size="sm"
                    >
                      <FaChartBar /> 柱状图
                    </Button>
                    <Button 
                      variant={chartType === 'area' ? 'success' : 'outline-success'}
                      onClick={() => setChartType('area')}
                      size="sm"
                    >
                      区域图
                    </Button>
                    <Button 
                      variant={chartType === 'pie' ? 'success' : 'outline-success'}
                      onClick={() => setChartType('pie')}
                      size="sm"
                      disabled={dataType !== 'sales'}
                    >
                      <FaChartPie /> 饼图
                    </Button>
                  </ButtonGroup>
                </Col>
              </Row>

              {/* 图表区域 */}
              <div style={{ width: '100%', height: 400 }}>
                <ResponsiveContainer>
                  {renderChart()}
                </ResponsiveContainer>
              </div>

              {/* 数据摘要 */}
              <Row className="mt-4">
                <Col md={4}>
                  <Card className="bg-light">
                    <Card.Body className="text-center">
                      <h5 className="text-primary">
                        {dataType === 'sales' ? '$24,408' : '117'}
                      </h5>
                      <small className="text-muted">
                        {dataType === 'sales' ? '本周总销售额' : '总库存数量'}
                      </small>
                    </Card.Body>
                  </Card>
                </Col>
                <Col md={4}>
                  <Card className="bg-light">
                    <Card.Body className="text-center">
                      <h5 className="text-success">
                        {dataType === 'sales' ? '220' : '3'}
                      </h5>
                      <small className="text-muted">
                        {dataType === 'sales' ? '总订单数' : '低库存警告'}
                      </small>
                    </Card.Body>
                  </Card>
                </Col>
                <Col md={4}>
                  <Card className="bg-light">
                    <Card.Body className="text-center">
                      <h5 className="text-info">
                        {dataType === 'sales' ? '$3,487' : '19.5'}
                      </h5>
                      <small className="text-muted">
                        {dataType === 'sales' ? '日均销售额' : '平均库存'}
                      </small>
                    </Card.Body>
                  </Card>
                </Col>
              </Row>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default ChartDisplay 