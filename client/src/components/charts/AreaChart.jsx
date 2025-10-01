import React from 'react';
import ChartRenderer from './ChartRenderer';

const AreaChart = ({ data, config = {}, className, style }) => {
  const chartConfig = {
    type: 'area',
    data,
    smooth: true,
    areaStyle: {
      fillOpacity: 0.6
    },
    color: ['#1890ff', '#52c41a', '#faad14', '#f5222d'],
    tooltip: {
      shared: true,
      showCrosshairs: true,
      crosshairs: {
        type: 'x'
      }
    },
    legend: {
      position: 'top'
    },
    responsive: true,
    interactions: [
      { type: 'element-active' },
      { type: 'brush' }
    ],
    ...config
  };

  return (
    <ChartRenderer 
      chartConfig={chartConfig} 
      className={className}
      style={style}
    />
  );
};

export default AreaChart;
