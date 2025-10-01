import React, { useState, useCallback } from 'react';
import ChartRenderer from './ChartRenderer';
import { Button } from '../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { 
  FaDownload, 
  FaExpand, 
  FaCompress, 
  FaFilter, 
  FaChartLine,
  FaChartBar,
  FaChartPie,
  FaChartArea
} from 'react-icons/fa';

const InteractiveChart = ({ 
  chartConfig, 
  className = "", 
  style = {},
  onDataPointClick = null,
  onChartTypeChange = null,
  showControls = true 
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedDataPoints, setSelectedDataPoints] = useState([]);
  const [chartType, setChartType] = useState(chartConfig?.type || 'line');

  const handleDataPointClick = useCallback((event) => {
    if (onDataPointClick) {
      onDataPointClick(event);
    }
    
    // Update selected data points for highlighting
    const { data } = event;
    setSelectedDataPoints(prev => 
      prev.includes(data) 
        ? prev.filter(point => point !== data)
        : [...prev, data]
    );
  }, [onDataPointClick]);

  const handleChartTypeChange = useCallback((newType) => {
    setChartType(newType);
    if (onChartTypeChange) {
      onChartTypeChange(newType);
    }
  }, [onChartTypeChange]);

  const handleExport = useCallback(() => {
    // Export chart data as JSON
    const exportData = {
      chartType: chartType,
      data: chartConfig.data,
      config: chartConfig,
      timestamp: new Date().toISOString()
    };
    
    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: 'application/json'
    });
    
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chart-${chartType}-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [chartType, chartConfig]);

  const toggleExpanded = useCallback(() => {
    setIsExpanded(prev => !prev);
  }, []);

  const getChartTypeIcon = (type) => {
    switch (type) {
      case 'line': return FaChartLine;
      case 'bar': return FaChartBar;
      case 'pie': return FaChartPie;
      case 'area': return FaChartArea;
      default: return FaChartLine;
    }
  };

  const availableChartTypes = ['line', 'bar', 'pie', 'area'];
  const currentConfig = {
    ...chartConfig,
    type: chartType,
    onPointClick: handleDataPointClick
  };

  return (
    <Card className={`w-full ${isExpanded ? 'fixed inset-4 z-50' : ''} ${className}`}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center text-lg font-semibold">
            {React.createElement(getChartTypeIcon(chartType), { 
              className: "h-5 w-5 text-blue-500 mr-2" 
            })}
            Interactive Chart
          </CardTitle>
          
          {showControls && (
            <div className="flex items-center gap-2">
              {/* Chart Type Selector */}
              <div className="flex items-center gap-1">
                {availableChartTypes.map(type => (
                  <Button
                    key={type}
                    variant={chartType === type ? "default" : "outline"}
                    size="sm"
                    onClick={() => handleChartTypeChange(type)}
                    className="h-8 w-8 p-0"
                    title={`Switch to ${type} chart`}
                  >
                    {React.createElement(getChartTypeIcon(type), { 
                      className: "h-3 w-3" 
                    })}
                  </Button>
                ))}
              </div>
              
              {/* Export Button */}
              <Button
                variant="outline"
                size="sm"
                onClick={handleExport}
                className="h-8 px-3"
                title="Export chart data"
              >
                <FaDownload className="h-3 w-3 mr-1" />
                Export
              </Button>
              
              {/* Expand/Collapse Button */}
              <Button
                variant="outline"
                size="sm"
                onClick={toggleExpanded}
                className="h-8 w-8 p-0"
                title={isExpanded ? "Collapse chart" : "Expand chart"}
              >
                {isExpanded ? (
                  <FaCompress className="h-3 w-3" />
                ) : (
                  <FaExpand className="h-3 w-3" />
                )}
              </Button>
            </div>
          )}
        </div>
        
        {/* Chart Info */}
        <div className="flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
          <div>
            {chartConfig.data?.length || 0} data points
          </div>
          <div>
            Type: {chartType} | Interactive
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="pt-0">
        <div 
          className="w-full bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 shadow-sm"
          style={{ 
            height: isExpanded ? 'calc(100vh - 200px)' : '400px',
            ...style 
          }}
        >
          <ChartRenderer 
            chartConfig={currentConfig}
            className="w-full h-full"
          />
        </div>
        
        {/* Selected Data Points Info */}
        {selectedDataPoints.length > 0 && (
          <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
            <div className="text-sm font-medium text-blue-800 dark:text-blue-200 mb-2">
              Selected Data Points ({selectedDataPoints.length})
            </div>
            <div className="text-xs text-blue-600 dark:text-blue-300">
              Click on chart points to select them for detailed analysis
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default InteractiveChart;
