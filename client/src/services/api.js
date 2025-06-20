import axios from 'axios';

// 配置API基础URL - 使用Vite环境变量
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000,
  headers: {
    'Content-Type': 'application/json',
  }
});

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    // 可以在这里添加认证token等
    console.log('API Request:', config.method.toUpperCase(), config.url);
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    console.log('API Response:', response.status, response.config.url);
    return response;
  },
  (error) => {
    console.error('API Error:', error.response?.status, error.config?.url, error.message);
    return Promise.reject(error);
  }
);

// 智能问答API
export const queryAPI = {
  // 发送自然语言查询
  sendQuery: async (query) => {
    try {
      const response = await api.post('/query', { query });
      return response.data;
    } catch (error) {
      throw new Error('查询失败: ' + error.message);
    }
  }
};

// 库存管理API
export const inventoryAPI = {
  // 获取库存列表
  getInventory: async () => {
    try {
      const response = await api.get('/inventory');
      return response.data;
    } catch (error) {
      throw new Error('获取库存数据失败: ' + error.message);
    }
  },

  // 获取库存预警
  getInventoryAlerts: async () => {
    try {
      const response = await api.get('/inventory/alerts');
      return response.data;
    } catch (error) {
      throw new Error('获取库存预警失败: ' + error.message);
    }
  }
};

// 销售数据API
export const salesAPI = {
  // 获取销售数据
  getSalesData: async (timeRange = 'week') => {
    try {
      const response = await api.get(`/sales?range=${timeRange}`);
      return response.data;
    } catch (error) {
      throw new Error('获取销售数据失败: ' + error.message);
    }
  },

  // 获取产品销量排行
  getProductSales: async () => {
    try {
      const response = await api.get('/sales/products');
      return response.data;
    } catch (error) {
      throw new Error('获取产品销量失败: ' + error.message);
    }
  }
};

// 报表生成API
export const reportAPI = {
  // 生成报表
  generateReport: async (reportType, dateRange = null) => {
    try {
      const payload = {
        type: reportType,
        ...(dateRange && { dateRange })
      };
      const response = await api.post('/reports/generate', payload);
      return response.data;
    } catch (error) {
      throw new Error('生成报表失败: ' + error.message);
    }
  },

  // 获取报表列表
  getReports: async () => {
    try {
      const response = await api.get('/reports');
      return response.data;
    } catch (error) {
      throw new Error('获取报表列表失败: ' + error.message);
    }
  }
};

// 用户认证API（如果需要）
export const authAPI = {
  // 登录
  login: async (credentials) => {
    try {
      const response = await api.post('/auth/login', credentials);
      return response.data;
    } catch (error) {
      throw new Error('登录失败: ' + error.message);
    }
  },

  // 注销
  logout: async () => {
    try {
      const response = await api.post('/auth/logout');
      return response.data;
    } catch (error) {
      throw new Error('注销失败: ' + error.message);
    }
  }
};

// 数据分析API
export const analyticsAPI = {
  // 获取仪表板数据
  getDashboardData: async () => {
    try {
      const response = await api.get('/analytics/dashboard');
      return response.data;
    } catch (error) {
      throw new Error('获取仪表板数据失败: ' + error.message);
    }
  },

  // 获取趋势分析
  getTrendAnalysis: async (metric, timeRange) => {
    try {
      const response = await api.get(`/analytics/trends?metric=${metric}&timeRange=${timeRange}`);
      return response.data;
    } catch (error) {
      throw new Error('获取趋势分析失败: ' + error.message);
    }
  }
};

// 模拟数据（用于开发环境）
export const mockData = {
  // 模拟查询响应
  queryResponse: {
    answer: "根据最新数据，本月销售额为 $68,945，比上月增长 15.2%",
    data: {
      sales: 68945,
      growth: 15.2,
      orders: 542
    },
    charts: null,
    suggestions: [
      "销售表现优秀，建议继续当前策略",
      "重点关注库存管理，避免缺货"
    ]
  },

  // 模拟库存数据
  inventoryData: [
    {
      id: 1,
      name: 'Laptop Pro 15"',
      stock: 45,
      minStock: 10,
      status: 'healthy'
    }
    // ... 更多数据
  ]
};

export default api; 