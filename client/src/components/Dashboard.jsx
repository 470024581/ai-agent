import { Card, Row, Col, Alert, Badge } from 'react-bootstrap'
import { FaBrain, FaChartBar, FaBoxes, FaFileAlt, FaRocket, FaLightbulb } from 'react-icons/fa'

function Dashboard() {
  const features = [
    {
      icon: FaBrain,
      title: '智能问答',
      description: '使用自然语言查询数据，如"本月销售额多少？"',
      color: 'primary',
      status: '可用'
    },
    {
      icon: FaBoxes,
      title: '库存检查',
      description: '实时监控库存状态，智能预警低库存商品',
      color: 'warning',
      status: '可用'
    },
    {
      icon: FaChartBar,
      title: '数据图表',
      description: '可视化销售和库存数据，支持多种图表类型',
      color: 'info',
      status: '可用'
    },
    {
      icon: FaFileAlt,
      title: '报表生成',
      description: 'AI自动生成各类业务报表，支持下载和打印',
      color: 'success',
      status: '可用'
    }
  ]

  const stats = [
    { label: '总产品数', value: '6', color: 'primary' },
    { label: '库存警告', value: '3', color: 'warning' },
    { label: '本周销售', value: '$15,847', color: 'success' },
    { label: '生成报表', value: '12', color: 'info' }
  ]

  return (
    <div>
      {/* 欢迎横幅 */}
      <Alert variant="info" className="mb-4">
        <h4 className="alert-heading">
          <FaRocket className="me-2" />
          欢迎使用 Smart AI Assistant
        </h4>
        <p className="mb-2">
          一个结合自然语言理解与业务数据的智能问答与自动化建议平台
        </p>
        <hr />
        <p className="mb-0">
          <FaLightbulb className="me-1" />
          基于 <strong>LangChain + 数据 + FastAPI + React</strong> 构建的演示项目
        </p>
      </Alert>

      {/* 统计卡片 */}
      <Row className="mb-4">
        {stats.map((stat, index) => (
          <Col md={3} key={index} className="mb-3">
            <Card className="text-center h-100">
              <Card.Body>
                <h3 className={`text-${stat.color}`}>{stat.value}</h3>
                <small className="text-muted">{stat.label}</small>
              </Card.Body>
            </Card>
          </Col>
        ))}
      </Row>

      {/* 功能介绍 */}
      <Row>
        <Col>
          <Card className="shadow-sm">
            <Card.Header className="bg-dark text-white">
              <h5 className="mb-0">🚀 核心功能</h5>
            </Card.Header>
            <Card.Body>
              <Row>
                {features.map((feature, index) => {
                  const IconComponent = feature.icon
                  return (
                    <Col md={6} key={index} className="mb-4">
                      <Card className="h-100 border-0 bg-light">
                        <Card.Body>
                          <div className="d-flex align-items-start">
                            <div className={`me-3 text-${feature.color}`}>
                              <IconComponent size={24} />
                            </div>
                            <div className="flex-grow-1">
                              <div className="d-flex justify-content-between align-items-center mb-2">
                                <h6 className="card-title mb-0">{feature.title}</h6>
                                <Badge bg={feature.color}>{feature.status}</Badge>
                              </div>
                              <p className="card-text text-muted small mb-0">
                                {feature.description}
                              </p>
                            </div>
                          </div>
                        </Card.Body>
                      </Card>
                    </Col>
                  )
                })}
              </Row>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* 使用指南 */}
      <Row className="mt-4">
        <Col>
          <Card>
            <Card.Header className="bg-secondary text-white">
              <h5 className="mb-0">📖 快速开始</h5>
            </Card.Header>
            <Card.Body>
              <Row>
                <Col md={6}>
                  <h6>🎯 演示场景</h6>
                  <ul className="list-unstyled">
                    <li className="mb-2">
                      <FaBrain className="text-primary me-2" />
                      <strong>智能问答:</strong> "本月销售额多少？"
                    </li>
                    <li className="mb-2">
                      <FaBoxes className="text-warning me-2" />
                      <strong>库存检查:</strong> "库存低于50的产品有哪些？"
                    </li>
                    <li className="mb-2">
                      <FaChartBar className="text-info me-2" />
                      <strong>数据图表:</strong> 查看销售趋势可视化
                    </li>
                    <li className="mb-2">
                      <FaFileAlt className="text-success me-2" />
                      <strong>报表生成:</strong> 生成日报、周报、月报
                    </li>
                  </ul>
                </Col>
                <Col md={6}>
                  <h6>🔧 技术栈</h6>
                  <div className="d-flex flex-wrap gap-2">
                    <Badge bg="primary">React 18</Badge>
                    <Badge bg="success">Bootstrap 5</Badge>
                    <Badge bg="info">Recharts</Badge>
                    <Badge bg="warning">React Icons</Badge>
                    <Badge bg="secondary">Axios</Badge>
                    <Badge bg="dark">Vite</Badge>
                  </div>
                  <hr />
                  <h6 className="mt-3">🎨 设计特点</h6>
                  <ul className="list-unstyled small">
                    <li>✅ 响应式设计</li>
                    <li>✅ 现代化UI界面</li>
                    <li>✅ 组件化架构</li>
                    <li>✅ 模拟真实数据</li>
                  </ul>
                </Col>
              </Row>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* 项目信息 */}
      <Row className="mt-4">
        <Col>
          <Card className="border-primary">
            <Card.Body className="text-center">
              <h6 className="text-primary mb-3">
                <FaLightbulb className="me-2" />
                项目演示说明
              </h6>
              <p className="text-muted mb-0">
                这是一个基于产品方案构建的Smart AI Assistant前端演示项目。
                所有数据均为模拟数据，用于展示功能和界面设计。
                在实际部署时，需要连接到相应的后端API。
              </p>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default Dashboard 