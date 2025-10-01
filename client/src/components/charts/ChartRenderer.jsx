import React, { useEffect, useRef, useState } from 'react';
import { Line, Column, Pie, Area } from '@antv/g2plot';

const ChartRenderer = ({ chartConfig, className = "", style = {} }) => {
  const containerRef = useRef(null);
  const chartInstanceRef = useRef(null);
  const [error, setError] = useState(null);

  // helper to safely truncate long labels
  const truncate = (text, maxLen = 14) => {
    if (!text && text !== 0) return '';
    const str = String(text);
    return str.length > maxLen ? str.slice(0, maxLen - 1) + '…' : str;
  };

  useEffect(() => {
    if (!chartConfig || !containerRef.current) return;

    try {
      // Destroy existing chart instance
      if (chartInstanceRef.current) {
        chartInstanceRef.current.destroy();
        chartInstanceRef.current = null;
      }

      let { type, data, ...config } = chartConfig;
      
      // Validate data
      if (!data || !Array.isArray(data) || data.length === 0) {
        setError('No data available for chart');
        return;
      }

      // Normalize pie data if backend sent x/y keys
      if (type && type.toLowerCase() === 'pie' && Array.isArray(data)) {
        const hasXY = data.length > 0 && data[0] && (('x' in data[0]) || ('y' in data[0]));
        if (hasXY) {
          data = data.map(item => ({
            category: item.category ?? item.x,
            value: item.value ?? item.y
          }));
          // ensure fields
          config.angleField = config.angleField || 'value';
          config.colorField = config.colorField || 'category';
        }
      }

      // Create chart based on type
      let chart;
      switch (type.toLowerCase()) {
        case 'line':
          chart = new Line(containerRef.current, {
            data,
            xField: config.xField || 'x',
            yField: config.yField || 'y',
            seriesField: config.seriesField,
            smooth: config.smooth !== false,
            point: config.point !== false,
            color: config.color || ['#1890ff', '#52c41a', '#faad14', '#f5222d'],
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
          });
          break;

        case 'bar':
        case 'column':
          chart = new Column(containerRef.current, {
            data,
            xField: config.xField || 'x',
            yField: config.yField || 'y',
            seriesField: config.seriesField,
            color: config.color || ['#1890ff', '#52c41a', '#faad14', '#f5222d'],
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
          });
          break;

        case 'pie':
          chart = new Pie(containerRef.current, {
            data,
            angleField: config.angleField || 'value',
            colorField: config.colorField || 'category',
            radius: 0.8,
            appendPadding: 12,
            autoFit: true,
            pieStyle: { stroke: '#fff', lineWidth: 1 },
            // spider 标签更适合长文本，避免重叠和出框
            label: {
              type: 'spider',
              labelHeight: 24,
              formatter: (datum) => {
                const name = truncate(datum.category ?? datum.colorField ?? '');
                const percent = typeof datum.percent === 'number' ? (datum.percent * 100).toFixed(2) : undefined;
                return percent ? `${name} ${percent}%` : name;
              }
            },
            color: config.color || ['#1890ff', '#52c41a', '#faad14', '#f5222d'],
            tooltip: {
              showTitle: false,
              showMarkers: false,
              formatter: (datum) => {
                const percent = typeof datum.percent === 'number' ? (datum.percent * 100).toFixed(2) + '%' : '';
                return { name: datum.category, value: `${datum.value}${percent ? ` (${percent})` : ''}` };
              }
            },
            legend: {
              position: 'right',
              itemName: {
                formatter: (text) => truncate(text)
              }
            },
            responsive: true,
            interactions: [
              { type: 'element-active' }
            ],
            ...config
          });
          break;

        case 'area':
          chart = new Area(containerRef.current, {
            data,
            xField: config.xField || 'x',
            yField: config.yField || 'y',
            seriesField: config.seriesField,
            smooth: config.smooth !== false,
            areaStyle: {
              fillOpacity: 0.6
            },
            color: config.color || ['#1890ff', '#52c41a', '#faad14', '#f5222d'],
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
          });
          break;

        default:
          throw new Error(`Unsupported chart type: ${type}`);
      }

      // Render chart
      chart.render();
      chartInstanceRef.current = chart;
      setError(null);

    } catch (err) {
      console.error('Chart rendering error:', err);
      setError(err.message);
    }

    // Cleanup function
    return () => {
      if (chartInstanceRef.current) {
        chartInstanceRef.current.destroy();
        chartInstanceRef.current = null;
      }
    };
  }, [chartConfig]);

  // Handle resize
  useEffect(() => {
    const handleResize = () => {
      if (chartInstanceRef.current) {
        chartInstanceRef.current.changeSize(
          containerRef.current?.clientWidth || 400,
          containerRef.current?.clientHeight || 300
        );
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  if (error) {
    return (
      <div className={`flex items-center justify-center p-8 bg-gray-50 rounded-lg border ${className}`} style={style}>
        <div className="text-center text-gray-500">
          <div className="text-lg font-semibold mb-2">Chart Error</div>
          <div className="text-sm">{error}</div>
        </div>
      </div>
    );
  }

  return (
    <div 
      ref={containerRef} 
      className={`w-full h-full ${className}`}
      style={{ minHeight: '300px', ...style }}
    />
  );
};

export default ChartRenderer;
