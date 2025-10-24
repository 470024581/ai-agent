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
    console.log('convertBackendChartData input:', backendData);
    
    // If it's already in the correct format (AntV G2Plot format)
    if (backendData.type && backendData.data && Array.isArray(backendData.data)) {
      console.log('Data already in correct format, returning as-is');
      return backendData;
    }

    // Handle direct Chart.js format (backend sends this directly)
    if (backendData.type && backendData.data && backendData.data.labels && backendData.data.datasets) {
      console.log('Converting direct Chart.js format to AntV G2Plot format');
      const labels = backendData.data.labels;
      const values = backendData.data.datasets[0]?.data || [];
      
      // Convert to AntV G2Plot format
      const data = labels.map((label, index) => ({
        category: label,
        value: values[index] || 0
      }));

      const result = {
        type: backendData.type,
        data: data,
        title: backendData.options?.plugins?.title?.text || 'Chart',
        angleField: 'value',
        colorField: 'category'
      };
      
      console.log('Converted result:', result);
      return result;
    }

    // Handle wrapped format (chart_config field)
    const { chart_config, chart_type, chart_data } = backendData;
    
    if (!chart_config) {
      return null;
    }

    // Handle Chart.js format conversion
    if (chart_config.type === 'pie' && chart_config.data && chart_config.data.labels && chart_config.data.datasets) {
      const labels = chart_config.data.labels;
      const values = chart_config.data.datasets[0]?.data || [];
      
      // Convert to AntV G2Plot format
      const data = labels.map((label, index) => ({
        category: label,
        value: values[index] || 0
      }));

      return {
        type: 'pie',
        data: data,
        title: chart_config.options?.plugins?.title?.text || 'Chart',
        angleField: 'value',
        colorField: 'category',
        ...chart_config
      };
    }

    // Handle other Chart.js formats (bar, line, etc.)
    if (chart_config.data && chart_config.data.labels && chart_config.data.datasets) {
      const labels = chart_config.data.labels;
      const values = chart_config.data.datasets[0]?.data || [];
      
      // Convert to AntV G2Plot format
      const data = labels.map((label, index) => ({
        x: label,
        y: values[index] || 0
      }));

      return {
        type: chart_config.type || chart_type || 'line',
        data: data,
        title: chart_config.options?.plugins?.title?.text || 'Chart',
        xField: 'x',
        yField: 'y',
        ...chart_config
      };
    }

    // Handle structured data format
    return {
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
