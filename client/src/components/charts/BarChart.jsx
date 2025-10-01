import React from 'react';
import ChartRenderer from './ChartRenderer';

const BarChart = ({ data, config = {}, className, style }) => {
  const chartConfig = {
    type: 'bar',
    data,
    color: ['#1890ff', '#52c41a', '#faad14', '#f5222d'],
    columnStyle: {
      radius: [4, 4, 0, 0]
    },
    tooltip: {
      shared: true
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

export default BarChart;
