/**
 * Chart utility functions for data transformation and configuration
 */

/**
 * Convert backend chart data to frontend format
 * @param {Object} backendData - Data from backend
 * @returns {Object} Frontend chart configuration
 */
export const convertBackendChartData = (backendData) => {
  if (!backendData) return null;

  try {
    // If it's already in the correct format
    if (backendData.type && backendData.data) {
      return backendData;
    }

    // Convert from old format
    const { chart_config, chart_type, chart_data } = backendData;
    
    if (!chart_config) {
      return null;
    }

    // Chart.js format conversion removed - system now uses structured data directly

    // Handle other formats
    return {
      // 优先使用后端明确给出的 chart_config.type，避免被旧字段覆盖
      type: chart_config.type || chart_type || 'line',
      data: chart_data || [],
      title: chart_config.title,
      xField: chart_config.xField || 'x',
      yField: chart_config.yField || 'y',
      seriesField: chart_config.seriesField,
      color: chart_config.color,
      ...chart_config
    };
  } catch (error) {
    console.error('Error converting backend chart data:', error);
    return null;
  }
};

/**
 * Validate chart data format
 * @param {Object} chartConfig - Chart configuration
 * @returns {boolean} Whether the config is valid
 */
export const validateChartConfig = (chartConfig) => {
  if (!chartConfig) return false;
  
  const requiredFields = ['type', 'data'];
  return requiredFields.every(field => chartConfig[field] !== undefined);
};

/**
 * Get chart type display name
 * @param {string} chartType - Chart type
 * @returns {string} Display name
 */
export const getChartTypeDisplayName = (chartType) => {
  const typeMap = {
    'line': 'Line Chart',
    'bar': 'Bar Chart',
    'column': 'Column Chart',
    'pie': 'Pie Chart',
    'area': 'Area Chart',
    'scatter': 'Scatter Plot'
  };
  
  return typeMap[chartType] || 'Chart';
};

/**
 * Generate default chart colors
 * @param {number} count - Number of colors needed
 * @returns {Array} Color array
 */
export const generateChartColors = (count = 4) => {
  const defaultColors = [
    '#1890ff', // Blue
    '#52c41a', // Green
    '#faad14', // Orange
    '#f5222d', // Red
    '#722ed1', // Purple
    '#13c2c2', // Cyan
    '#eb2f96', // Pink
    '#fa8c16'  // Gold
  ];
  
  return defaultColors.slice(0, count);
};

/**
 * Format chart data for display
 * @param {Array} data - Chart data
 * @param {string} type - Chart type
 * @returns {Array} Formatted data
 */
export const formatChartData = (data, type) => {
  if (!Array.isArray(data)) return [];
  
  return data.map(item => {
    const formatted = { ...item };
    
    // Format numeric values
    Object.keys(formatted).forEach(key => {
      if (typeof formatted[key] === 'number') {
        // Round to 2 decimal places for display
        formatted[key] = Math.round(formatted[key] * 100) / 100;
      }
    });
    
    return formatted;
  });
};

/**
 * Get chart interaction options
 * @param {string} chartType - Chart type
 * @returns {Array} Interaction options
 */
export const getChartInteractions = (chartType) => {
  const baseInteractions = [{ type: 'element-active' }];
  
  switch (chartType) {
    case 'line':
    case 'area':
    case 'bar':
      return [...baseInteractions, { type: 'brush' }];
    case 'pie':
      return baseInteractions;
    default:
      return baseInteractions;
  }
};

/**
 * Create responsive chart configuration
 * @param {Object} config - Base configuration
 * @returns {Object} Responsive configuration
 */
export const createResponsiveConfig = (config) => {
  return {
    ...config,
    responsive: true,
    autoFit: true,
    padding: 'auto'
  };
};
