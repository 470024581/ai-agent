"""
Utility functions module - provides data formatting and common functionalities.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json

def format_currency(amount: float) -> str:
    """Formats currency display (keeps '¥' for now, can be made configurable)."""
    return f"¥{amount:,.2f}"

def format_percentage(value: float) -> str:
    """Formats percentage display."""
    return f"{value:.1f}%"

def calculate_growth_rate(current: float, previous: float) -> float:
    """Calculates growth rate."""
    if previous == 0:
        return 0.0
    return ((current - previous) / previous) * 100

def get_status_by_stock_level(stock_level: int, min_stock: int = 10, healthy_stock: int = 50) -> str:
    """Gets status based on stock level."""
    if stock_level == 0:
        return "out_of_stock"
    elif stock_level < min_stock:
        return "critical"
    elif stock_level < healthy_stock:
        return "low"
    else:
        return "healthy"

def get_alert_level_by_stock(stock_level: int) -> str:
    """Gets alert level based on stock."""
    if stock_level == 0:
        return "critical"
    elif stock_level < 10:
        return "urgent" 
    elif stock_level < 50:
        return "warning"
    else:
        return "normal"

def format_chart_data_for_frontend(chart_type: str, labels: List[str], datasets: List[Dict]) -> Dict[str, Any]:
    """Formats chart data to be compatible with Chart.js for the frontend."""
    return {
        "type": chart_type,
        "labels": labels,
        "datasets": datasets
    }

def create_line_chart_dataset(label: str, data: List[float], color: str = "rgb(75, 192, 192)") -> Dict[str, Any]:
    """Creates a line chart dataset."""
    return {
        "label": label,
        "data": data,
        "borderColor": color,
        "backgroundColor": color.replace("rgb", "rgba").replace(")", ", 0.2)"),
        "tension": 0.1
    }

def create_bar_chart_dataset(label: str, data: List[float], colors: List[str] = None) -> Dict[str, Any]:
    """Creates a bar chart dataset."""
    if colors is None:
        colors = ["rgba(54, 162, 235, 0.8)"] * len(data)
    
    return {
        "label": label,
        "data": data,
        "backgroundColor": colors,
        "borderColor": [color.replace("0.8", "1") for color in colors],
        "borderWidth": 1
    }

def create_doughnut_chart_dataset(data: List[float], colors: List[str] = None) -> Dict[str, Any]:
    """Creates a doughnut chart dataset."""
    if colors is None:
        colors = [
            "#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", 
            "#9966FF", "#FF9F40", "#FF6384", "#36A2EB", 
            "#FFCE56", "#4BC0C0"
        ]
    
    return {
        "data": data,
        "backgroundColor": colors[:len(data)],
        "borderWidth": 2,
        "borderColor": "#fff"
    }

def get_time_range_dates(range_type: str) -> tuple[datetime, datetime]:
    """Gets the start and end dates for a time range."""
    now = datetime.now()
    
    if range_type == "day":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    elif range_type == "week":
        start_date = now - timedelta(days=7)
        end_date = now
    elif range_type == "month":
        start_date = now - timedelta(days=30)
        end_date = now
    elif range_type == "quarter":
        start_date = now - timedelta(days=90)
        end_date = now
    elif range_type == "year":
        start_date = now - timedelta(days=365)
        end_date = now
    else:
        # Default to one week
        start_date = now - timedelta(days=7)
        end_date = now
    
    return start_date, end_date

def create_api_response(success: bool = True, data: Any = None, message: str = None, 
                       error: str = None, **kwargs) -> Dict[str, Any]:
    """Creates a standardized API response."""
    response = {
        "success": success,
        "timestamp": datetime.now().isoformat()
    }
    if data is not None: response["data"] = data
    if message: response["message"] = message
    if error: response["error"] = error
    response.update(kwargs)
    return response

def format_sql_date(dt: datetime) -> str:
    """Formats a date for SQL queries."""
    return dt.strftime('%Y-%m-%d %H:%M:%S')

def format_display_date(dt: datetime) -> str:
    """Formats a date for display."""
    return dt.strftime('%Y-%m-%d %H:%M')

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division to avoid zero division errors."""
    if denominator == 0: return default
    return numerator / denominator

def calculate_percentage_distribution(values: List[float]) -> List[float]:
    """Calculates percentage distribution."""
    total = sum(values)
    if total == 0: return [0.0] * len(values)
    return [(value / total) * 100 for value in values]

def get_suggested_order_quantity(current_stock: int, min_stock: int = 20, 
                                target_stock: int = 100) -> int:
    """Calculates suggested order quantity."""
    if current_stock >= target_stock: return 0
    return max(target_stock - current_stock, min_stock)

def generate_report_id() -> str:
    """Generates a report ID."""
    return f"RPT_{int(datetime.now().timestamp())}"

def validate_date_range(start_date: str, end_date: str) -> tuple[datetime, datetime]:
    """Validates and parses a date range."""
    try:
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        if start >= end:
            raise ValueError("Start date must be earlier than end date.")
        return start, end
    except ValueError as e:
        raise ValueError(f"Date format error: {str(e)}")

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncates text."""
    if len(text) <= max_length: return text
    return text[:max_length-3] + "..."

def parse_query_intent(query: str) -> Dict[str, Any]:
    """Parses query intent."""
    query_lower = query.lower()
    
    # Sales related keywords
    sales_keywords = ['sales', 'revenue', 'income', 'volume', 'orders'] # English keywords
    
    # Inventory related keywords
    inventory_keywords = ['inventory', 'warehouse', 'stock', 'goods'] # English keywords
    
    # Time related keywords (English)
    time_keywords = {
        'today': ['today', 'current day'],
        'week': ['this week', 'current week', '7 days', 'seven days'],
        'month': ['this month', 'current month', '30 days', 'thirty days'],
        'year': ['this year', 'current year', 'annual']
    }
    
    intent = {
        'type': 'general', # Default intent type
        'time_range': 'month', # Default time range
        'keywords': []
    }
    
    # Determine query type
    if any(keyword in query_lower for keyword in sales_keywords):
        intent['type'] = 'sales'
        intent['keywords'].extend([kw for kw in sales_keywords if kw in query_lower])
    elif any(keyword in query_lower for keyword in inventory_keywords):
        intent['type'] = 'inventory'
        intent['keywords'].extend([kw for kw in inventory_keywords if kw in query_lower])
    
    # Determine time range
    for time_range, keywords in time_keywords.items():
        if any(keyword in query_lower for keyword in keywords):
            intent['time_range'] = time_range
            intent['keywords'].extend([kw for kw in keywords if kw in query_lower])
            break
    
    return intent 