import React from 'react';
import ChartRenderer from './ChartRenderer';

const LineChart = ({ data, config = {}, className, style }) => {
  const chartConfig = {
    type: 'line',
    data,
    smooth: true,
    point: true,
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

export default LineChart;
