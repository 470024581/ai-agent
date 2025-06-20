# Smart AI Assistant

> 一个结合自然语言理解与业务数据的智能问答与自动化建议平台

## 🎯 项目概述

Smart AI Assistant是基于产品方案构建的演示项目，展示了如何将AI技术与系统结合，提供智能化的业务数据查询和分析功能。

### 核心功能

- 🧠 **智能问答**: 使用自然语言查询数据
- 📦 **库存检查**: 实时监控库存状态，智能预警
- 📊 **数据图表**: 可视化销售和库存数据
- 📋 **报表生成**: AI自动生成各类业务报表

## 🛠️ 技术栈

### 前端技术
- **React 18** - 用户界面框架
- **Bootstrap 5** - UI组件库
- **React Router** - 路由管理
- **Recharts** - 数据可视化
- **React Icons** - 图标库
- **Axios** - HTTP客户端
- **Vite** - 构建工具

### 后端技术（计划中）
- **FastAPI** - Python Web框架
- **LangChain** - AI Agent框架
- **OpenAI API** - 大语言模型
- **SQLite/PostgreSQL** - 数据库

## 🚀 快速开始

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run dev
```

项目将在 `http://localhost:5173` 启动

### 构建生产版本

```bash
npm run build
```

## 📁 项目结构

```
src/
├── components/          # React组件
│   ├── Header.jsx      # 导航头部
│   ├── Dashboard.jsx   # 仪表板首页
│   ├── QueryForm.jsx   # 智能问答
│   ├── ChartDisplay.jsx # 图表展示
│   ├── InventoryCheck.jsx # 库存检查
│   └── ReportGenerator.jsx # 报表生成
├── services/           # API服务
│   └── api.js         # API接口定义
├── App.jsx            # 主应用组件
└── main.jsx           # 应用入口点
```

## 🎨 功能演示

### 1. 智能问答
- 输入自然语言查询，如"本月销售额多少？"
- AI解析查询意图并返回结构化数据
- 支持查询历史记录

### 2. 库存检查
- 实时库存状态监控
- 自动识别低库存和缺货商品
- AI智能补货建议

### 3. 数据图表
- 多种图表类型：折线图、柱状图、饼图、区域图
- 销售数据和库存数据可视化
- 交互式图表控制

### 4. 报表生成
- 支持多种报表类型：日报、周报、月报
- AI生成智能分析和建议
- 报表下载和打印功能

## 🎯 演示场景

| 场景 | 示例查询 | 预期结果 |
|------|----------|----------|
| 销售查询 | "过去7天每天的销售额是多少？" | 显示图表 + 总结 |
| 库存检查 | "当前库存低于50的产品有哪些？" | 列出低库存产品 |
| 报表生成 | "请生成今天的销售日报。" | 生成格式化报告 |

## 🔧 配置说明

### 环境变量

创建 `.env` 文件：

```env
REACT_APP_API_URL=http://localhost:8000/api
```

### API配置

项目目前使用模拟数据，要连接真实后端，请修改 `src/services/api.js` 中的API端点。

## 📊 数据说明

当前项目使用模拟数据进行演示：
- 销售数据：模拟一周的销售情况
- 库存数据：6种产品的库存状态
- 报表数据：AI生成的示例报表内容

## 🚧 开发计划

### MVP功能（已完成）
- ✅ 智能问答界面
- ✅ 库存检查功能
- ✅ 数据图表展示
- ✅ 报表生成器

### 后续计划
- 🔄 后端API集成
- 🔄 真实数据连接
- 🔄 用户认证系统
- 🔄 OCR发票识别
- 🔄 RAG文档问答

## 🎯 技术亮点

1. **组件化设计**: 高度模块化的React组件
2. **响应式布局**: 适配桌面和移动设备
3. **现代化UI**: 基于Bootstrap 5的美观界面
4. **交互式图表**: 支持多种数据可视化
5. **模拟数据**: 完整的前端演示体验

## 📝 使用指南

1. **浏览首页**: 了解项目功能概览
2. **智能问答**: 尝试输入自然语言查询
3. **查看图表**: 切换不同的图表类型和数据
4. **检查库存**: 查看库存状态和AI建议
5. **生成报表**: 选择报表类型并生成

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目基于 MIT 许可证开源 - 查看 [LICENSE](LICENSE) 文件了解详情

## 📞 联系方式

如有问题或建议，欢迎通过以下方式联系：

- 项目问题: [GitHub Issues](https://github.com/yourusername/smart-ai-assistant/issues)
- 邮箱: your.email@example.com

---

⭐ 如果这个项目对您有帮助，请给个Star支持！ 