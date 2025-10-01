"""
AntV Chart Service for dynamic chart rendering

This module provides chart rendering functionality using PyEcharts for backend
and G2Plot for frontend, replacing static image generation with interactive charts.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Any, Optional, Union
from pyecharts import options as opts
from pyecharts.charts import Line, Bar, Pie, Scatter
from pyecharts.globals import ThemeType

# Import logging utility
try:
    from ..utils.logging import get_logger
except ImportError:
    # Fallback for testing
    import logging
    def get_logger(name):
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(name)

logger = get_logger(__name__)


class AntVChartService:
    """Service for generating interactive chart configurations using PyEcharts"""

    def __init__(self, theme: str = "light"):
        """Initialize the chart service.
        
        Args:
            theme: Chart theme ('light' or 'dark')
        """
        self.theme = ThemeType.LIGHT if theme == "light" else ThemeType.DARK
        logger.info(f"Initialized AntV Chart Service with theme: {theme}")

# Chart.js conversion removed - system now uses structured data directly

    def _convert_pyecharts_to_g2plot_config(self, chart_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert PyEcharts configuration to G2Plot format"""
        try:
            # Extract basic chart information
            chart_type = chart_data.get("chart_type", "line")
            title = chart_data.get("title", "")
            data = chart_data.get("data", [])
            
            # Convert to G2Plot format
            g2plot_config = {
                "type": chart_type,
                "title": title,
                "data": data,
                "xField": chart_data.get("xField", "x"),
                "yField": chart_data.get("yField", "y"),
                "seriesField": chart_data.get("seriesField"),
                "color": chart_data.get("color", ["#1890ff", "#52c41a", "#faad14", "#f5222d"]),
                "smooth": chart_data.get("smooth", True),
                "point": chart_data.get("point", True),
                "tooltip": {
                    "shared": True,
                    "showCrosshairs": True,
                    "crosshairs": {
                        "type": "x"
                    }
                },
                "legend": {
                    "position": "top"
                },
                "responsive": True,
                "interactions": [
                    {"type": "element-active"},
                    {"type": "brush"}
                ]
            }
            
            # Chart-specific configurations
            if chart_type == "pie":
                g2plot_config.update({
                    "angleField": chart_data.get("angleField", "value"),
                    "colorField": chart_data.get("colorField", "category"),
                    "radius": 0.8,
                    "label": {
                        "type": "outer",
                        "content": "{name} {percentage}"
                    }
                })
            elif chart_type == "bar":
                g2plot_config.update({
                    "columnStyle": {
                        "radius": [4, 4, 0, 0]
                    }
                })
            elif chart_type == "area":
                g2plot_config.update({
                    "areaStyle": {
                        "fillOpacity": 0.6
                    }
                })
            
            return g2plot_config
            
        except Exception as e:
            logger.error(f"Error converting PyEcharts to G2Plot config: {e}")
            return {}

    def render_line_chart(self, data: List[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
        """Render line chart configuration"""
        try:
            title = config.get("title", "Line Chart")
            x_field = config.get("xField", "x")
            y_field = config.get("yField", "y")
            series_field = config.get("seriesField")
            
            # Create PyEcharts line chart
            line_chart = Line(init_opts=opts.InitOpts(theme=self.theme))
            line_chart.set_global_opts(
                title_opts=opts.TitleOpts(title=title),
                tooltip_opts=opts.TooltipOpts(trigger="axis"),
                legend_opts=opts.LegendOpts(pos_top="5%"),
                xaxis_opts=opts.AxisOpts(type_="category"),
                yaxis_opts=opts.AxisOpts(type_="value")
            )
            
            # Add data series
            if series_field:
                # Multiple series
                series_data = {}
                for item in data:
                    series_name = item.get(series_field, "default")
                    if series_name not in series_data:
                        series_data[series_name] = []
                    series_data[series_name].append([item.get(x_field), item.get(y_field)])
                
                for series_name, series_points in series_data.items():
                    line_chart.add_xaxis([point[0] for point in series_points])
                    line_chart.add_yaxis(
                        series_name,
                        [point[1] for point in series_points],
                        is_smooth=True,
                        symbol="circle",
                        symbol_size=6
                    )
            else:
                # Single series
                x_data = [item.get(x_field) for item in data]
                y_data = [item.get(y_field) for item in data]
                line_chart.add_xaxis(x_data)
                line_chart.add_yaxis(
                    y_field,
                    y_data,
                    is_smooth=True,
                    symbol="circle",
                    symbol_size=6
                )
            
            # Convert to G2Plot format
            chart_config = {
                "chart_type": "line",
                "title": title,
                "data": data,
                "xField": x_field,
                "yField": y_field,
                "seriesField": series_field,
                "smooth": True,
                "point": True
            }
            
            return self._convert_pyecharts_to_g2plot_config(chart_config)
            
        except Exception as e:
            logger.error(f"Error rendering line chart: {e}")
            return {}

    def render_bar_chart(self, data: List[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
        """Render bar chart configuration"""
        try:
            title = config.get("title", "Bar Chart")
            x_field = config.get("xField", "x")
            y_field = config.get("yField", "y")
            series_field = config.get("seriesField")
            
            # Create PyEcharts bar chart
            bar_chart = Bar(init_opts=opts.InitOpts(theme=self.theme))
            bar_chart.set_global_opts(
                title_opts=opts.TitleOpts(title=title),
                tooltip_opts=opts.TooltipOpts(trigger="axis"),
                legend_opts=opts.LegendOpts(pos_top="5%"),
                xaxis_opts=opts.AxisOpts(type_="category"),
                yaxis_opts=opts.AxisOpts(type_="value")
            )
            
            # Add data series
            if series_field:
                # Multiple series
                series_data = {}
                for item in data:
                    series_name = item.get(series_field, "default")
                    if series_name not in series_data:
                        series_data[series_name] = []
                    series_data[series_name].append([item.get(x_field), item.get(y_field)])
                
                x_data = list(set([item.get(x_field) for item in data]))
                for series_name, series_points in series_data.items():
                    y_data = [0] * len(x_data)
                    for point in series_points:
                        if point[0] in x_data:
                            y_data[x_data.index(point[0])] = point[1]
                    bar_chart.add_xaxis(x_data)
                    bar_chart.add_yaxis(series_name, y_data)
            else:
                # Single series
                x_data = [item.get(x_field) for item in data]
                y_data = [item.get(y_field) for item in data]
                bar_chart.add_xaxis(x_data)
                bar_chart.add_yaxis(y_field, y_data)
            
            # Convert to G2Plot format
            chart_config = {
                "chart_type": "bar",
                "title": title,
                "data": data,
                "xField": x_field,
                "yField": y_field,
                "seriesField": series_field
            }
            
            return self._convert_pyecharts_to_g2plot_config(chart_config)
            
        except Exception as e:
            logger.error(f"Error rendering bar chart: {e}")
            return {}

    def render_pie_chart(self, data: List[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
        """Render pie chart configuration"""
        try:
            title = config.get("title", "Pie Chart")
            category_field = config.get("categoryField", "category")
            value_field = config.get("valueField", "value")
            
            # Create PyEcharts pie chart
            pie_chart = Pie(init_opts=opts.InitOpts(theme=self.theme))
            pie_chart.set_global_opts(
                title_opts=opts.TitleOpts(title=title),
                legend_opts=opts.LegendOpts(pos_left="left", orient="vertical")
            )
            
            # Prepare data for pie chart
            pie_data = [(item.get(category_field), item.get(value_field)) for item in data]
            pie_chart.add("", pie_data)
            
            # Convert to G2Plot format
            chart_config = {
                "chart_type": "pie",
                "title": title,
                "data": data,
                "angleField": value_field,
                "colorField": category_field
            }
            
            return self._convert_pyecharts_to_g2plot_config(chart_config)
            
        except Exception as e:
            logger.error(f"Error rendering pie chart: {e}")
            return {}

    def render_area_chart(self, data: List[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
        """Render area chart configuration"""
        try:
            title = config.get("title", "Area Chart")
            x_field = config.get("xField", "x")
            y_field = config.get("yField", "y")
            series_field = config.get("seriesField")
            
            # Create PyEcharts line chart with area style (Area chart is not available in this version)
            line_chart = Line(init_opts=opts.InitOpts(theme=self.theme))
            line_chart.set_global_opts(
                title_opts=opts.TitleOpts(title=title),
                tooltip_opts=opts.TooltipOpts(trigger="axis"),
                legend_opts=opts.LegendOpts(pos_top="5%"),
                xaxis_opts=opts.AxisOpts(type_="category"),
                yaxis_opts=opts.AxisOpts(type_="value")
            )
            
            # Add data series
            if series_field:
                # Multiple series
                series_data = {}
                for item in data:
                    series_name = item.get(series_field, "default")
                    if series_name not in series_data:
                        series_data[series_name] = []
                    series_data[series_name].append([item.get(x_field), item.get(y_field)])
                
                for series_name, series_points in series_data.items():
                    line_chart.add_xaxis([point[0] for point in series_points])
                    line_chart.add_yaxis(
                        series_name,
                        [point[1] for point in series_points],
                        is_smooth=True,
                        symbol="circle",
                        symbol_size=6,
                        areastyle_opts=opts.AreaStyleOpts(opacity=0.6)
                    )
            else:
                # Single series
                x_data = [item.get(x_field) for item in data]
                y_data = [item.get(y_field) for item in data]
                line_chart.add_xaxis(x_data)
                line_chart.add_yaxis(
                    y_field,
                    y_data,
                    is_smooth=True,
                    symbol="circle",
                    symbol_size=6,
                    areastyle_opts=opts.AreaStyleOpts(opacity=0.6)
                )
            
            # Convert to G2Plot format
            chart_config = {
                "chart_type": "area",
                "title": title,
                "data": data,
                "xField": x_field,
                "yField": y_field,
                "seriesField": series_field
            }
            
            return self._convert_pyecharts_to_g2plot_config(chart_config)
            
        except Exception as e:
            logger.error(f"Error rendering area chart: {e}")
            return {}

    def render_chart(self, chart_type: str, data: List[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
        """Main method to render any chart type"""
        try:
            logger.info(f"Rendering {chart_type} chart with {len(data)} data points")
            
            if chart_type.lower() == "line":
                return self.render_line_chart(data, config)
            elif chart_type.lower() == "bar":
                return self.render_bar_chart(data, config)
            elif chart_type.lower() == "pie":
                return self.render_pie_chart(data, config)
            elif chart_type.lower() == "area":
                return self.render_area_chart(data, config)
            else:
                logger.warning(f"Unsupported chart type: {chart_type}")
                return {}
                
        except Exception as e:
            logger.error(f"Error rendering chart: {e}")
            return {}


# Global instance
chart_service = AntVChartService()


def generate_chart_config(chart_type: str, data: List[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate chart configuration for frontend rendering"""
    return chart_service.render_chart(chart_type, data, config)
