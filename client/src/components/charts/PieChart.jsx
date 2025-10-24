import React from 'react';
import ChartRenderer from './ChartRenderer';

const PieChart = ({ data, config = {}, className, style }) => {
  const chartConfig = {
    type: 'pie',
    data,
    radius: 0.8,
    label: {
      type: 'outer',
      content: '{name} {percentage}'
    },
    color: ['#1890ff', '#52c41a', '#faad14', '#f5222d'],
    tooltip: {
      showTitle: false,
      showMarkers: false
    },
    legend: {
      position: 'bottom'
    },
    responsive: true,
    interactions: [
      { type: 'element-active' }
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

export default PieChart;
