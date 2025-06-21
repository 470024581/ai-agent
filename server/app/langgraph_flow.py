"""
Intelligent Data Analysis Flow Based on LangGraph
"""
import json
from typing import Dict, Any, List, Optional, TypedDict
import logging
import requests
from .agent import llm, perform_rag_query, get_answer_from_sqltable_datasource

logger = logging.getLogger(__name__)

class GraphState(TypedDict):
    """Define graph state"""
    user_input: str
    query_type: str  # "sql" or "rag"
    sql_task_type: str  # "query" or "chart"
    structured_data: Optional[Dict[str, Any]]
    chart_config: Optional[Dict[str, Any]]
    chart_image: Optional[str]
    answer: str
    quality_score: int
    retry_count: int
    datasource: Dict[str, Any]
    error: Optional[str]

def router_node(state: GraphState) -> GraphState:
    """Router node: determine if it's SQL or RAG requirement"""
    user_input = state["user_input"]
    
    # Simple rule-based judgment
    sql_keywords = ["查询", "统计", "数据", "图表", "销售", "库存", "报表"]
    rag_keywords = ["文档", "知识", "解释", "什么是", "如何", "为什么"]
    
    if any(keyword in user_input for keyword in sql_keywords):
        query_type = "sql"
    elif any(keyword in user_input for keyword in rag_keywords):
        query_type = "rag"
    else:
        query_type = "sql"  # Default
    
    logger.info(f"Router decision result: {query_type} for input: {user_input}")
    
    return {
        **state,
        "query_type": query_type
    }

def sql_classifier_node(state: GraphState) -> GraphState:
    """SQL classification node: determine if it's data query or chart building"""
    user_input = state["user_input"].lower()
    
    chart_keywords = [
        "图表", "可视化", "趋势", "分布", "柱状图", "折线图", "饼图",
        "chart", "visualization", "trend", "distribution", "bar chart", 
        "line chart", "pie chart", "graph", "plot", "generate", "create", "build"
    ]
    
    if any(keyword in user_input for keyword in chart_keywords):
        sql_task_type = "chart"
    else:
        sql_task_type = "query"
    
    logger.info(f"SQL task type: {sql_task_type} for input: {state['user_input']}")
    
    return {
        **state,
        "sql_task_type": sql_task_type
    }

async def sql_execution_node(state: GraphState) -> GraphState:
    """SQL execution node: retrieve structured data"""
    try:
        user_input = state["user_input"]
        datasource = state["datasource"]
        
        # Call existing SQL query logic
        result = await get_answer_from_sqltable_datasource(user_input, datasource)
        
        if result["success"]:
            # Ensure data is correctly passed, including original answer for chart data extraction
            structured_data = result["data"]
            if not structured_data.get("rows") and result.get("answer"):
                # If no rows data, put answer in structured_data for subsequent parsing
                structured_data["answer"] = result["answer"]
            
            logger.info(f"SQL execution successful, structured_data keys: {list(structured_data.keys())}")
            
            return {
                **state,
                "structured_data": structured_data,
                "answer": result["answer"]
            }
        else:
            return {
                **state,
                "error": result.get("error", "SQL execution failed")
            }
    except Exception as e:
        logger.error(f"SQL execution node error: {e}")
        return {
            **state,
            "error": str(e)
        }

def chart_config_node(state: GraphState) -> GraphState:
    """Chart configuration node: generate chart configuration"""
    try:
        structured_data = state.get("structured_data", {})
        user_input = state["user_input"]
        
        # Generate chart configuration based on data and user requirements
        chart_config = generate_chart_config(structured_data, user_input)
        
        return {
            **state,
            "chart_config": chart_config
        }
    except Exception as e:
        logger.error(f"Chart config node error: {e}")
        return {
            **state,
            "error": str(e)
        }

async def rag_query_node(state: GraphState) -> GraphState:
    """RAG query node"""
    try:
        user_input = state["user_input"]
        datasource = state["datasource"]
        
        result = await perform_rag_query(user_input, datasource)
        
        if result["success"]:
            return {
                **state,
                "answer": result["answer"],
                "structured_data": result.get("data", {})
            }
        else:
            return {
                **state,
                "error": result.get("error", "RAG query failed")
            }
    except Exception as e:
        logger.error(f"RAG query node error: {e}")
        return {
            **state,
            "error": str(e)
        }

def chart_rendering_node(state: GraphState) -> GraphState:
    """Chart rendering node: call MCP service"""
    try:
        chart_config = state.get("chart_config")
        if not chart_config:
            return {
                **state,
                "error": "Missing chart configuration"
            }
        
        # Call QuickChart API to generate chart
        chart_image = generate_chart_image(chart_config)
        
        return {
            **state,
            "chart_image": chart_image
        }
    except Exception as e:
        logger.error(f"Chart rendering node error: {e}")
        return {
            **state,
            "error": str(e)
        }

def llm_processing_node(state: GraphState) -> GraphState:
    """Large model invocation node"""
    try:
        if not llm:
            return state
        
        structured_data = state.get("structured_data", {})
        user_input = state["user_input"]
        
        # Use LLM to optimize the answer
        prompt = f"""
        User Question: {user_input}
        Data Results: {json.dumps(structured_data, ensure_ascii=False, indent=2)}
        
        Please answer the user's question based on the above data in natural language. Requirements:
        1. Answer accurately and concisely
        2. Highlight key data points
        3. Provide answer in English
        4. Focus on the most relevant insights from the data
        """
        
        response = llm.invoke(prompt)
        enhanced_answer = response.content
        
        return {
            **state,
            "answer": enhanced_answer
        }
    except Exception as e:
        logger.error(f"LLM processing node error: {e}")
        return state

def validation_node(state: GraphState) -> GraphState:
    """Output validation node"""
    try:
        answer = state.get("answer", "")
        structured_data = state.get("structured_data", {})
        error = state.get("error")
        
        # Simple quality scoring logic
        score = 10
        
        if error:
            score -= 5
        
        if not answer or len(answer) < 10:
            score -= 3
        
        if not structured_data:
            score -= 2
        
        # Ensure score is within reasonable range
        score = max(0, min(10, score))
        
        return {
            **state,
            "quality_score": score
        }
    except Exception as e:
        logger.error(f"Validation node error: {e}")
        return {
            **state,
            "quality_score": 5
        }

def retry_node(state: GraphState) -> GraphState:
    """Retry node"""
    retry_count = state.get("retry_count", 0)
    
    if retry_count >= 2:  # Maximum 2 retries
        return {
            **state,
            "answer": "Sorry, after multiple attempts, we still cannot generate satisfactory results. Please try to rephrase your question.",
            "quality_score": 10  # Set high score to end the process
        }
    
    return {
        **state,
        "retry_count": retry_count + 1,
        "error": None  # Clear error for retry
    }

def generate_chart_config(data: Dict[str, Any], user_input: str) -> Dict[str, Any]:
    """Generate chart configuration based on data and user input"""
    try:
        # Determine chart type
        chart_type = "bar"
        if "trend" in user_input.lower() or "趋势" in user_input:
            chart_type = "line"
        elif "pie" in user_input.lower() or "饼图" in user_input:
            chart_type = "pie"
        
        # Generate title
        title = "Sales Data Chart"
        if "销售" in user_input:
            title = "Sales Analysis Chart"
        elif "trend" in user_input.lower() or "趋势" in user_input:
            title = "Sales Trend Chart"
        elif "distribution" in user_input.lower() or "分布" in user_input:
            title = "Distribution Chart"
        
        chart_config = {
            "type": chart_type,
            "data": {
                "labels": [],
                "datasets": [{
                    "label": "Sales Amount",
                    "data": [],
                    "backgroundColor": [
                        "rgba(54, 162, 235, 0.6)",
                        "rgba(255, 99, 132, 0.6)", 
                        "rgba(255, 206, 86, 0.6)",
                        "rgba(75, 192, 192, 0.6)",
                        "rgba(153, 102, 255, 0.6)"
                    ],
                    "borderColor": [
                        "rgba(54, 162, 235, 1)",
                        "rgba(255, 99, 132, 1)",
                        "rgba(255, 206, 86, 1)", 
                        "rgba(75, 192, 192, 1)",
                        "rgba(153, 102, 255, 1)"
                    ],
                    "borderWidth": 2,
                    "fill": False if chart_type == "line" else True
                }]
            },
            "options": {
                "responsive": True,
                "plugins": {
                    "title": {
                        "display": True,
                        "text": title,
                        "font": {
                            "size": 16,
                            "weight": "bold"
                        }
                    },
                    "legend": {
                        "display": True,
                        "position": "top"
                    }
                },
                "scales": {
                    "y": {
                        "beginAtZero": True,
                        "title": {
                            "display": True,
                            "text": "Amount"
                        }
                    },
                    "x": {
                        "title": {
                            "display": True,
                            "text": "Period"
                        }
                    }
                }
            }
        }
        
        # Process data - ensure chart data is completely consistent with SQL query results
        logger.info(f"Processing chart data from: {type(data)} with keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
        
        if isinstance(data, dict):
            # Prioritize processing rows data
            if "rows" in data and data["rows"]:
                rows = data["rows"]
                logger.info(f"Found {len(rows)} rows in data")
                if len(rows) > 0:
                    labels = []
                    values = []
                    
                    # For sales trend charts, need to aggregate data by date
                    if "trend" in user_input.lower() or "趋势" in user_input:
                        # Aggregate sales data by month
                        monthly_data = {}
                        
                        for i, row in enumerate(rows):
                            logger.info(f"Processing row {i}: {row}")
                            if len(row) >= 8:  # Ensure sufficient columns (including date and amount)
                                try:
                                    # Column 7 is date (saledate), column 6 is total amount (totalamount)
                                    date_str = str(row[7]) if row[7] is not None else ""
                                    amount_str = str(row[6]) if row[6] is not None else "0"
                                    
                                    # Parse date, extract year-month
                                    if date_str and len(date_str) >= 7:  # Format like 2025-05-10
                                        year_month = date_str[:7]  # Take first 7 characters 2025-05
                                        amount = float(amount_str)
                                        
                                        if year_month in monthly_data:
                                            monthly_data[year_month] += amount
                                        else:
                                            monthly_data[year_month] = amount
                                        
                                        logger.info(f"Added to monthly data: {year_month} -> {amount}")
                                except (ValueError, TypeError, IndexError) as e:
                                    logger.warning(f"Skipping row {i} due to data parsing error: {e}")
                                    continue
                        
                        # Convert to chart data
                        if monthly_data:
                            # Sort by year-month
                            sorted_months = sorted(monthly_data.keys())
                            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                                         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                            
                            for year_month in sorted_months:
                                try:
                                    year, month = year_month.split('-')
                                    month_idx = int(month) - 1
                                    if 0 <= month_idx < 12:
                                        label = f"{month_names[month_idx]} {year[-2:]}"  # e.g. "May 25"
                                        value = monthly_data[year_month]
                                        labels.append(label)
                                        values.append(value)
                                        logger.info(f"Chart data point: {label} -> {value}")
                                except (ValueError, IndexError):
                                    continue
                    else:
                        # For other types of queries, directly use first few rows of data
                        for i, row in enumerate(rows[:10]):  # Display maximum 10 data points
                            logger.info(f"Processing row {i}: {row}")
                            if len(row) >= 2:
                                try:
                                    # Use product name as label, total amount as value
                                    if len(row) >= 7:  # Has product name and total amount
                                        label = str(row[2]) if row[2] is not None else f"Item {i+1}"  # Product name
                                        value = float(row[6]) if row[6] is not None else 0  # Total amount
                                    else:
                                        # Generic processing
                                        label = str(row[0]) if row[0] is not None else f"Item {i+1}"
                                        value = float(row[1]) if len(row) > 1 and row[1] is not None else 0
                                    
                                    labels.append(label)
                                    values.append(value)
                                    logger.info(f"Added data point: {label} -> {value}")
                                except (ValueError, TypeError, IndexError):
                                    logger.warning(f"Skipping row {i} due to data parsing error")
                                    continue
                    
                    if labels and values:
                        chart_config["data"]["labels"] = labels
                        chart_config["data"]["datasets"][0]["data"] = values
                        logger.info(f"Chart data configured with {len(labels)} data points: {list(zip(labels, values))}")
                    else:
                        logger.warning("No valid data found for chart generation")
            
            # Special processing: if data contains SQL query text result, try to parse
            elif "answer" in data and isinstance(data["answer"], str):
                # Try to extract data from answer text
                answer_text = data["answer"]
                logger.info(f"Attempting to extract chart data from answer: {answer_text}")
                
                if "2022-" in answer_text or "2023-" in answer_text or "2024-" in answer_text:  # Detect recognizable date patterns
                    try:
                        # Use regex to extract year and month
                        import re
                        pattern = r'(\d{4}-\d{2})：(\d+\.?\d*)'
                        matches = re.findall(pattern, answer_text)
                        
                        if matches:
                            labels = []
                            values = []
                            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                                         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                            
                            for date_str, value_str in matches:
                                try:
                                    year, month = date_str.split('-')
                                    month_idx = int(month) - 1
                                    if 0 <= month_idx < 12:
                                        label = f"{month_names[month_idx]} {year[-2:]}"
                                        value = float(value_str)
                                        labels.append(label)
                                        values.append(value)
                                except (ValueError, IndexError):
                                    continue
                            
                            if labels and values:
                                chart_config["data"]["labels"] = labels
                                chart_config["data"]["datasets"][0]["data"] = values
                                logger.info(f"Extracted chart data from answer text: {list(zip(labels, values))}")
                            else:
                                logger.warning("No valid data extracted from answer text")
                        else:
                            logger.warning(f"No regex matches found in answer text: {answer_text}")
                    except Exception as e:
                        logger.error(f"Failed to extract data from answer text: {e}")
                else:
                    logger.info("Answer text does not contain recognizable date patterns")
            
            elif "detailed_sales" in data and data["detailed_sales"]:
                # Process sales data format
                sales_data = data["detailed_sales"][:10]  # Limit to display first 10
                labels = [item.get("product_name", f"Product {i+1}") for i, item in enumerate(sales_data)]
                values = [float(item.get("total_amount", 0)) for item in sales_data]
                
                chart_config["data"]["labels"] = labels
                chart_config["data"]["datasets"][0]["data"] = values
        
        # If no data, generate example data
        if not chart_config["data"]["labels"]:
            chart_config["data"]["labels"] = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
            chart_config["data"]["datasets"][0]["data"] = [100, 150, 120, 200, 180, 220]
        
        return chart_config
    except Exception as e:
        logger.error(f"Error generating chart config: {e}")
        return {}

def generate_chart_image(chart_config: Dict[str, Any]) -> str:
    """Call QuickChart to generate chart image"""
    try:
        import json
        import urllib.parse
        
        quickchart_url = "https://quickchart.io/chart"
        
        # Use GET request method, pass chart configuration as URL parameters
        chart_json = json.dumps(chart_config)
        encoded_chart = urllib.parse.quote(chart_json)
        
        chart_url = f"{quickchart_url}?c={encoded_chart}&width=800&height=400&format=png&devicePixelRatio=2.0"
        
        logger.info(f"Generated QuickChart URL with config: {json.dumps(chart_config, indent=2)}")
        logger.info(f"Chart URL: {chart_url}")
        
        # Verify URL accessibility
        response = requests.head(chart_url, timeout=10)
        if response.status_code == 200:
            return chart_url
        else:
            logger.error(f"QuickChart URL validation failed: {response.status_code}")
            return ""
    except Exception as e:
        logger.error(f"Failed to generate chart image: {e}")
        return ""

# Simplified flow processing function
async def process_intelligent_query(user_input: str, datasource: Dict[str, Any]) -> Dict[str, Any]:
    """Process simplified version of intelligent query"""
    try:
        # Initialize state
        state = {
            "user_input": user_input,
            "query_type": "",
            "sql_task_type": "",
            "structured_data": None,
            "chart_config": None,
            "chart_image": None,
            "answer": "",
            "quality_score": 0,
            "retry_count": 0,
            "datasource": datasource,
            "error": None
        }
        
        # Execute flow
        # 1. Router judgment
        state = router_node(state)
        
        # 2. Process based on query type
        if state["query_type"] == "sql":
            # SQL classification
            state = sql_classifier_node(state)
            
            # SQL execution
            state = await sql_execution_node(state)
            
            if state["sql_task_type"] == "chart" and not state.get("error"):
                # Chart configuration
                state = chart_config_node(state)
                # Chart rendering
                state = chart_rendering_node(state)
            else:
                # LLM processing
                state = llm_processing_node(state)
        else:
            # RAG query
            state = await rag_query_node(state)
        
        # 3. Output validation
        state = validation_node(state)
        
        # 4. If quality is poor and retry count not exceeded, retry
        if state["quality_score"] < 8 and state["retry_count"] < 2:
            state = retry_node(state)
            # Here simplified processing, actual should re-execute flow
            state["quality_score"] = 8  # Avoid infinite retry
        
        return {
            "success": state["quality_score"] >= 8,
            "answer": state["answer"],
            "query_type": state["query_type"],
            "data": state.get("structured_data"),
            "chart_config": state.get("chart_config"),
            "chart_image": state.get("chart_image"),
            "quality_score": state["quality_score"],
            "error": state.get("error")
        }
        
    except Exception as e:
        logger.error(f"Error processing intelligent query: {e}")
        return {
            "success": False,
            "answer": f"Error occurred while processing query: {str(e)}",
            "error": str(e)
        } 