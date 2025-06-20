import { useState } from 'react'
import { Card, Row, Col, Form, Button, Alert, Modal } from 'react-bootstrap'
import { FaFileAlt, FaDownload, FaPrint, FaCalendarAlt, FaChartBar } from 'react-icons/fa'

function ReportGenerator() {
  const [selectedReport, setSelectedReport] = useState('')
  const [dateRange, setDateRange] = useState({
    startDate: '',
    endDate: ''
  })
  const [loading, setLoading] = useState(false)
  const [generatedReport, setGeneratedReport] = useState(null)
  const [showModal, setShowModal] = useState(false)

  const reportTypes = [
    {
      id: 'daily_sales',
      name: '日销售报表',
      description: '包含当日销售总额、订单数量、热销产品等信息',
      icon: FaCalendarAlt,
      color: 'primary'
    },
    {
      id: 'weekly_sales',
      name: '周销售报表',
      description: '显示一周内的销售趋势、对比分析和预测',
      icon: FaChartBar,
      color: 'success'
    },
    {
      id: 'inventory_status',
      name: '库存状态报表',
      description: '当前库存状况、库存预警、补货建议',
      icon: FaFileAlt,
      color: 'warning'
    },
    {
      id: 'monthly_summary',
      name: '月度总结报表',
      description: '月度销售汇总、利润分析、客户统计',
      icon: FaChartBar,
      color: 'info'
    }
  ]

  const handleGenerateReport = async () => {
    if (!selectedReport) {
      alert('请选择报表类型')
      return
    }

    setLoading(true)
    
    // 模拟API调用生成报表
    try {
      setTimeout(() => {
        const mockReport = generateMockReport(selectedReport)
        setGeneratedReport(mockReport)
        setShowModal(true)
        setLoading(false)
      }, 2000)
    } catch (error) {
      console.error('生成报表失败:', error)
      setLoading(false)
    }
  }

  const generateMockReport = (reportType) => {
    const currentDate = new Date().toLocaleDateString('zh-CN')
    
    switch (reportType) {
      case 'daily_sales':
        return {
          title: '日销售报表',
          date: currentDate,
          content: `
📊 销售概览
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 销售总额: $2,130
• 订单数量: 28 笔
• 平均订单价值: $76.07
• 同比增长: +12.5%

🏆 热销产品 TOP 3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Laptop Pro 15" - 5台 ($6,499)
2. Wireless Mouse - 12件 ($359.88)
3. Mechanical Keyboard - 8件 ($719.92)

📈 小时销售趋势
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
09:00-12:00  $580  (27.2%)
12:00-15:00  $720  (33.8%)
15:00-18:00  $530  (24.9%)
18:00-21:00  $300  (14.1%)

🎯 AI 洞察
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 下午时段销售表现最佳
• 电脑类产品需求稳定
• 建议增加配件类产品库存`
        }
        
      case 'weekly_sales':
        return {
          title: '周销售报表',
          date: `${currentDate} (本周)`,
          content: `
📊 本周销售汇总
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 总销售额: $15,847
• 总订单数: 156 笔
• 日均销售: $2,264
• 周环比: +8.3%

📅 每日明细
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
周一: $1,895 (22订单)
周二: $2,340 (28订单) ⭐
周三: $2,156 (24订单)
周四: $1,987 (19订单)
周五: $2,789 (31订单) ⭐
周六: $2,456 (18订单)
周日: $2,224 (14订单)

📈 趋势分析
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 周二和周五是销售高峰
• 周末销售有所回落
• 工作日平均销售较稳定

🎯 下周预测
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
预计销售额: $16,500 - $17,200
建议关注库存：Mouse, Cable`
        }

      case 'inventory_status':
        return {
          title: '库存状态报表',
          date: currentDate,
          content: `
📦 库存概况
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 总产品数: 6 种
• 库存健康: 3 种 ✅
• 库存不足: 2 种 ⚠️
• 缺货商品: 1 种 ❌

⚠️ 紧急关注
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 4K Monitor: 缺货 (0件)
• Wireless Mouse: 库存不足 (8件/最少20件)
• USB-C Cable: 库存不足 (5件/最少25件)

📋 补货建议
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 4K Monitor - 立即补货 50件 (DisplayTech)
2. Wireless Mouse - 补货 40件 (AccessoryCo)
3. USB-C Cable - 补货 45件 (CableCorp)

💰 补货成本估算
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
总预计成本: $21,118
预计到货时间: 3-5个工作日`
        }

      case 'monthly_summary':
        return {
          title: '月度总结报表',
          date: `${new Date().getFullYear()}年${new Date().getMonth() + 1}月`,
          content: `
📊 月度业绩总览
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 总销售额: $68,945
• 总订单数: 542 笔
• 毛利润: $24,130 (35%)
• 环比增长: +15.2%

🏆 产品表现排行
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Laptop Pro 15" - $32,475 (47.1%)
2. Mechanical Keyboard - $12,879 (18.7%)
3. 4K Monitor - $11,197 (16.2%)
4. Wireless Mouse - $7,834 (11.4%)
5. 其他产品 - $4,560 (6.6%)

📈 趋势洞察
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 电脑类产品持续占主导
• 配件类需求稳步增长
• 显示器类别表现突出

🎯 下月策略建议
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 加大显示器类产品推广
• 优化配件类产品库存
• 考虑拓展新产品线`
        }

      default:
        return {
          title: '报表',
          date: currentDate,
          content: '暂无数据'
        }
    }
  }

  const handlePrint = () => {
    window.print()
  }

  const handleDownload = () => {
    const element = document.createElement('a')
    const file = new Blob([generatedReport.content], {type: 'text/plain'})
    element.href = URL.createObjectURL(file)
    element.download = `${generatedReport.title}_${generatedReport.date}.txt`
    document.body.appendChild(element)
    element.click()
    document.body.removeChild(element)
  }

  return (
    <div>
      <Row>
        <Col lg={8} className="mx-auto">
          <Card className="shadow-sm">
            <Card.Header className="bg-success text-white">
              <h4 className="mb-0">
                <FaFileAlt className="me-2" />
                智能报表生成器
              </h4>
              <small>自动生成各类业务报表</small>
            </Card.Header>
            <Card.Body>
              {/* 报表类型选择 */}
              <Form.Group className="mb-4">
                <Form.Label><strong>选择报表类型：</strong></Form.Label>
                <Row>
                  {reportTypes.map(report => {
                    const IconComponent = report.icon
                    return (
                      <Col md={6} key={report.id} className="mb-3">
                        <Card 
                          className={`h-100 cursor-pointer border-2 ${selectedReport === report.id ? `border-${report.color}` : 'border-light'}`}
                          onClick={() => setSelectedReport(report.id)}
                          style={{ cursor: 'pointer' }}
                        >
                          <Card.Body className="text-center">
                            <IconComponent className={`fa-2x text-${report.color} mb-2`} />
                            <h6 className="card-title">{report.name}</h6>
                            <small className="text-muted">{report.description}</small>
                          </Card.Body>
                        </Card>
                      </Col>
                    )
                  })}
                </Row>
              </Form.Group>

              {/* 日期范围选择 */}
              <Form.Group className="mb-4">
                <Form.Label><strong>日期范围（可选）：</strong></Form.Label>
                <Row>
                  <Col md={6}>
                    <Form.Control
                      type="date"
                      value={dateRange.startDate}
                      onChange={(e) => setDateRange({...dateRange, startDate: e.target.value})}
                    />
                  </Col>
                  <Col md={6}>
                    <Form.Control
                      type="date"
                      value={dateRange.endDate}
                      onChange={(e) => setDateRange({...dateRange, endDate: e.target.value})}
                    />
                  </Col>
                </Row>
              </Form.Group>

              {/* 生成按钮 */}
              <div className="text-center">
                <Button
                  variant="primary"
                  size="lg"
                  onClick={handleGenerateReport}
                  disabled={loading || !selectedReport}
                >
                  {loading ? (
                    <>
                      <div className="spinner-border spinner-border-sm me-2" role="status"></div>
                      生成中...
                    </>
                  ) : (
                    <>
                      <FaFileAlt className="me-2" />
                      生成报表
                    </>
                  )}
                </Button>
              </div>

              {/* 使用提示 */}
              <Alert variant="info" className="mt-4">
                <h6>💡 使用提示：</h6>
                <ul className="mb-0">
                  <li>选择需要的报表类型</li>
                  <li>可选择特定日期范围（留空则使用默认范围）</li>
                  <li>系统将使用AI分析生成智能报表</li>
                  <li>生成的报表支持下载和打印</li>
                </ul>
              </Alert>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* 报表预览模态框 */}
      <Modal show={showModal} onHide={() => setShowModal(false)} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>
            <FaFileAlt className="me-2" />
            {generatedReport?.title}
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <div className="mb-3">
            <small className="text-muted">生成时间: {generatedReport?.date}</small>
          </div>
          <pre style={{ 
            whiteSpace: 'pre-wrap', 
            fontFamily: 'monospace',
            fontSize: '0.9rem',
            lineHeight: '1.4',
            backgroundColor: '#f8f9fa',
            padding: '1rem',
            borderRadius: '0.25rem',
            border: '1px solid #dee2e6'
          }}>
            {generatedReport?.content}
          </pre>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowModal(false)}>
            关闭
          </Button>
          <Button variant="info" onClick={handlePrint}>
            <FaPrint className="me-1" />
            打印
          </Button>
          <Button variant="primary" onClick={handleDownload}>
            <FaDownload className="me-1" />
            下载
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  )
}

export default ReportGenerator 