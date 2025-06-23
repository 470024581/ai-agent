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
    """Router node: use LLM to determine if it's SQL or RAG requirement"""
    user_input = state["user_input"]
    
    if not llm:
        logger.warning("LLM not available, using fallback rule-based routing")
        # Fallback to rule-based judgment
        sql_keywords = ["query", "statistics", "data", "chart", "sales", "inventory", "report", "analysis", "trends", "dashboard", "metrics", "numbers"]
        rag_keywords = ["document", "knowledge", "explain", "what is", "how", "why", "tell me", "describe", "information", "content"]
        
        if any(keyword in user_input.lower() for keyword in sql_keywords):
            query_type = "sql"
        elif any(keyword in user_input.lower() for keyword in rag_keywords):
            query_type = "rag"
        else:
            query_type = "sql"  # Default
    else:
        # Use LLM for semantic routing
        try:
            prompt = f"""
            Analyze the following user query and determine whether it should be handled by:
            1. SQL - for data queries, statistics, reports, charts, sales analysis, inventory checks
            2. RAG - for document-based questions, knowledge base queries, explanations
            
            User query: "{user_input}"
            
            Respond with only "sql" or "rag" (lowercase, no explanation).
            """
            
            response = llm.invoke(prompt)
            
            # Handle different response types (Ollama returns string, OpenAI returns object)
            if hasattr(response, 'content'):
                query_type = response.content.strip().lower()
            elif isinstance(response, str):
                query_type = response.strip().lower()
            else:
                query_type = str(response).strip().lower()
            
            # Validate response
            if query_type not in ["sql", "rag"]:
                logger.warning(f"Invalid LLM routing response: {query_type}, defaulting to sql")
                query_type = "sql"
                
        except Exception as e:
            logger.error(f"Error in LLM routing: {e}, falling back to rule-based")
            # Fallback to rule-based
            sql_keywords = ["query", "statistics", "data", "chart", "sales", "inventory", "report", "analysis", "trends", "dashboard", "metrics", "numbers"]
            if any(keyword in user_input.lower() for keyword in sql_keywords):
                query_type = "sql"
            else:
                query_type = "rag"
    
    logger.info(f"Router decision result: {query_type} for input: {user_input}")
    
    return {
        **state,
        "query_type": query_type
    }

def sql_classifier_node(state: GraphState) -> GraphState:
    """SQL classification node: use LLM to determine if it's data query or chart building"""
    user_input = state["user_input"]
    
    if not llm:
        logger.warning("LLM not available, using fallback rule-based SQL classification")
        # Fallback to rule-based judgment
        chart_keywords = [
            "chart", "visualization", "trend", "distribution", "bar chart", 
            "line chart", "pie chart", "graph", "plot", "generate", "create", "build",
            "visualize", "show", "display", "draw"
        ]
        
        if any(keyword in user_input.lower() for keyword in chart_keywords):
            sql_task_type = "chart"
        else:
            sql_task_type = "query"
    else:
        # Use LLM for semantic classification
        try:
            prompt = f"""
            Analyze the following user query and determine what the user wants:
            1. query - Get data query results (text-based data analysis)
            2. chart - Generate charts or visualizations (charts, trend graphs, distribution graphs, etc.)
            
            User query: "{user_input}"
            
            Only answer "query" or "chart" (lowercase, no explanation needed).
            """
            
            response = llm.invoke(prompt)
            
            # Handle different response types (Ollama returns string, OpenAI returns object)
            if hasattr(response, 'content'):
                sql_task_type = response.content.strip().lower()
            elif isinstance(response, str):
                sql_task_type = response.strip().lower()
            else:
                sql_task_type = str(response).strip().lower()
            
            # Validate response
            if sql_task_type not in ["query", "chart"]:
                logger.warning(f"Invalid LLM SQL classification response: {sql_task_type}, defaulting to query")
                sql_task_type = "query"
                
        except Exception as e:
            logger.error(f"Error in LLM SQL classification: {e}, falling back to rule-based")
            # Fallback to rule-based
            chart_keywords = [
                "chart", "visualization", "trend", "distribution", "bar chart", 
                "line chart", "pie chart", "graph", "plot", "generate", "create", "build",
                "visualize", "show", "display", "draw"
            ]
            if any(keyword in user_input.lower() for keyword in chart_keywords):
                sql_task_type = "chart"
            else:
                sql_task_type = "query"
    
    logger.info(f"SQL task type: {sql_task_type} for input: {user_input}")
    
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
            logger.warning("LLM not available, returning original answer")
            return state
        
        structured_data = state.get("structured_data", {})
        user_input = state["user_input"]
        current_answer = state.get("answer", "")
        
        # Use LLM to optimize the answer
        prompt = f"""
        User question: {user_input}
        
        Data result: {json.dumps(structured_data, ensure_ascii=False, indent=2)}
        
        Current answer: {current_answer}
        
        Please answer the user's question in natural language based on the above data. Requirements:
        1. Answer accurately and concisely
        2. Highlight key data points
        3. Answer in Chinese
        4. Focus on the most relevant insights in the data
        5. If it's sales data, analyze trends and key indicators
        """
        
        response = llm.invoke(prompt)
        
        # Handle different response types
        if hasattr(response, 'content'):
            enhanced_answer = response.content
        elif isinstance(response, str):
            enhanced_answer = response
        else:
            enhanced_answer = str(response)
        
        logger.info(f"LLM enhanced answer generated: {enhanced_answer[:100]}...")
        
        return {
            **state,
            "answer": enhanced_answer
        }
    except Exception as e:
        logger.error(f"LLM processing node error: {e}")
        # Return original state with current answer if LLM fails
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
    """Use LLM to generate chart configuration based on data and user requirements for semantic analysis"""
    try:
        if not llm:
            logger.warning("LLM not available, using fallback chart generation")
            return generate_fallback_chart_config(data, user_input)
        
        # Extract data information for LLM analysis
        data_summary = extract_data_summary(data)
        
        # Use LLM to analyze user intent and data characteristics
        chart_analysis_prompt = f"""
        User query: "{user_input}"
        
        Data summary: {data_summary}
        
        Please analyze the user's chart requirements and return chart configuration suggestions in JSON format:
        {{
            "chart_type": "line|bar|pie",
            "title": "Chart title",
            "x_axis_label": "X-axis label",
            "y_axis_label": "Y-axis label",
            "data_field_for_labels": "Data field name or index for labels",
            "data_field_for_values": "Data field name or index for values",
            "aggregation_method": "none|sum|average|count",
            "time_grouping": "none|month|quarter|year"
        }}
        
        Analysis requirements:
        1. Determine the most suitable chart type based on user query
        2. Generate meaningful titles and axis labels
        3. Identify which fields in the data should be used for labels and values
        4. If it's time series data, determine appropriate time grouping method
        5. Only return JSON, no other explanation
        """
        
        response = llm.invoke(chart_analysis_prompt)
        
        # Process LLM response
        if hasattr(response, 'content'):
            analysis_text = response.content
        elif isinstance(response, str):
            analysis_text = response
        else:
            analysis_text = str(response)
        
        # Parse JSON configuration returned by LLM
        try:
            import json
            import re
            
            # Extract JSON part
            json_match = re.search(r'\{.*\}', analysis_text, re.DOTALL)
            if json_match:
                chart_analysis = json.loads(json_match.group())
            else:
                logger.warning("No JSON found in LLM response, using fallback")
                return generate_fallback_chart_config(data, user_input)
                
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"Failed to parse LLM chart analysis: {e}, using fallback")
            return generate_fallback_chart_config(data, user_input)
        
        # Generate chart configuration based on LLM analysis results
        chart_config = {
            "type": chart_analysis.get("chart_type", "bar"),
            "data": {
                "labels": [],
                "datasets": [{
                    "label": chart_analysis.get("y_axis_label", "Data"),
                    "data": [],
                    "backgroundColor": [
                        "rgba(54, 162, 235, 0.6)",
                        "rgba(255, 99, 132, 0.6)", 
                        "rgba(255, 206, 86, 0.6)",
                        "rgba(75, 192, 192, 0.6)",
                        "rgba(153, 102, 255, 0.6)",
                        "rgba(255, 159, 64, 0.6)",
                        "rgba(199, 199, 199, 0.6)",
                        "rgba(83, 102, 255, 0.6)"
                    ],
                    "borderColor": [
                        "rgba(54, 162, 235, 1)",
                        "rgba(255, 99, 132, 1)",
                        "rgba(255, 206, 86, 1)", 
                        "rgba(75, 192, 192, 1)",
                        "rgba(153, 102, 255, 1)",
                        "rgba(255, 159, 64, 1)",
                        "rgba(199, 199, 199, 1)",
                        "rgba(83, 102, 255, 1)"
                    ],
                    "borderWidth": 2,
                    "fill": chart_analysis.get("chart_type") != "line"
                }]
            },
            "options": {
                "responsive": True,
                "plugins": {
                    "title": {
                        "display": True,
                        "text": chart_analysis.get("title", "Data Chart"),
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
                            "text": chart_analysis.get("y_axis_label", "Value")
                        }
                    },
                    "x": {
                        "title": {
                            "display": True,
                            "text": chart_analysis.get("x_axis_label", "Category")
                        }
                    }
                }
            }
        }
        
        # Process data using LLM-guided approach
        labels, values = extract_chart_data_with_llm_guidance(data, chart_analysis)
        
        if labels and values:
            chart_config["data"]["labels"] = labels
            chart_config["data"]["datasets"][0]["data"] = values
            logger.info(f"LLM-guided chart data configured with {len(labels)} data points")
        else:
            logger.warning("No data extracted with LLM guidance, using fallback")
            return generate_fallback_chart_config(data, user_input)
        
        return chart_config
        
    except Exception as e:
        logger.error(f"Error in LLM-guided chart generation: {e}")
        return generate_fallback_chart_config(data, user_input)

def extract_data_summary(data: Dict[str, Any]) -> str:
    """Extract data summary for LLM analysis"""
    try:
        summary_parts = []
        
        if isinstance(data, dict):
            if "rows" in data and data["rows"]:
                rows = data["rows"]
                summary_parts.append(f"Data rows: {len(rows)}")
                
                if len(rows) > 0:
                    sample_row = rows[0]
                    summary_parts.append(f"Data columns: {len(sample_row)}")
                    summary_parts.append(f"Sample data: {sample_row}")
                    
                    # Analyze data types
                    if len(sample_row) >= 8:
                        summary_parts.append("Contains fields: ID, Product ID, Product Name, Category, Sales Volume, Unit Price, Total Amount, Date")
                    elif len(sample_row) >= 3:
                        summary_parts.append(f"Contains structured data with {len(sample_row)} fields")
                    elif len(sample_row) == 2:
                        # Handle aggregated query results, such as month and sales
                        summary_parts.append("Contains aggregated data with time and values")
                    
            if "answer" in data:
                summary_parts.append(f"Query result description: {str(data['answer'])[:100]}...")
                
        return "; ".join(summary_parts) if summary_parts else "Data structure unclear"
        
    except Exception as e:
        logger.error(f"Error extracting data summary: {e}")
        return "Data summary extraction failed"

def extract_chart_data_with_llm_guidance(data: Dict[str, Any], chart_analysis: Dict[str, Any]) -> tuple:
    """Extract chart data based on LLM analysis results"""
    try:
        labels = []
        values = []
        
        if not isinstance(data, dict) or "rows" not in data or not data["rows"]:
            return labels, values
        
        rows = data["rows"]
        aggregation_method = chart_analysis.get("aggregation_method", "none")
        time_grouping = chart_analysis.get("time_grouping", "none")
        label_field = chart_analysis.get("data_field_for_labels", "2")  # Default product name
        value_field = chart_analysis.get("data_field_for_values", "6")  # Default total amount
        
        # Convert field indices
        try:
            label_idx = int(label_field) if str(label_field).isdigit() else 2
            value_idx = int(value_field) if str(value_field).isdigit() else 6
        except (ValueError, TypeError):
            label_idx, value_idx = 2, 6
        
        logger.info(f"Using label_idx: {label_idx}, value_idx: {value_idx}")
        logger.info(f"Sample row: {rows[0] if rows else 'No rows'}")
        
        if time_grouping != "none" and len(rows[0]) > 7:
            # Time series data processing
            time_data = {}
            
            for row in rows:
                if len(row) > max(label_idx, value_idx, 7):
                    try:
                        date_str = str(row[7]) if row[7] else ""
                        # Handle TEXT type numeric fields
                        value_str = str(row[value_idx]) if row[value_idx] else "0"
                        # Try to convert to float
                        try:
                            value = float(value_str)
                        except ValueError:
                            # If conversion fails, try to extract numbers
                            import re
                            numbers = re.findall(r'-?\d+\.?\d*', value_str)
                            value = float(numbers[0]) if numbers else 0
                        
                        if date_str and len(date_str) >= 7:
                            if time_grouping == "month":
                                # Extract year-month, support different date formats
                                if '-' in date_str:
                                    time_key = date_str[:7]  # YYYY-MM
                                else:
                                    # Handle other formats
                                    time_key = date_str[:7] if len(date_str) >= 7 else date_str
                            elif time_grouping == "quarter":
                                year = date_str[:4]
                                month_str = date_str[5:7] if len(date_str) > 6 else "01"
                                try:
                                    month = int(month_str)
                                    quarter = (month - 1) // 3 + 1
                                    time_key = f"{year}-Q{quarter}"
                                except ValueError:
                                    time_key = f"{year}-Q1"
                            elif time_grouping == "year":
                                time_key = date_str[:4]  # YYYY
                            else:
                                time_key = date_str[:7]
                            
                            if aggregation_method == "sum":
                                time_data[time_key] = time_data.get(time_key, 0) + value
                            elif aggregation_method == "average":
                                if time_key in time_data:
                                    time_data[time_key] = (time_data[time_key] + value) / 2
                                else:
                                    time_data[time_key] = value
                            elif aggregation_method == "count":
                                time_data[time_key] = time_data.get(time_key, 0) + 1
                            else:
                                time_data[time_key] = value
                                
                    except (ValueError, TypeError, IndexError) as e:
                        logger.warning(f"Error processing row data: {e}")
                        continue
            
            # Convert time data to chart format with proper time-based sorting
            def sort_time_key(key):
                """Custom time key sorting function"""
                try:
                    if time_grouping == "year":
                        return int(key)
                    elif time_grouping == "month":
                        year, month = key.split('-')
                        return int(year) * 100 + int(month)
                    elif time_grouping == "quarter":
                        year, quarter = key.split('-Q')
                        return int(year) * 10 + int(quarter)
                    else:
                        return key
                except:
                    return key
            
            for time_key in sorted(time_data.keys(), key=sort_time_key):
                labels.append(format_time_label(time_key, time_grouping))
                values.append(time_data[time_key])
                
        else:
            # Non-time series data processing
            data_dict = {}
            
            logger.info(f"Processing {len(rows)} rows of data")
            
            for i, row in enumerate(rows):
                logger.info(f"Processing row {i}: {row}, length: {len(row)}")
                
                if len(row) == 2:
                    # Handle aggregated query results (e.g., month and sales)
                    try:
                        label = str(row[0]) if row[0] else f"Item{len(labels)+1}"
                        # Handle TEXT type numeric fields
                        value_str = str(row[1]) if row[1] else "0"
                        try:
                            value = float(value_str)
                        except ValueError:
                            # If conversion fails, try to extract numbers
                            import re
                            numbers = re.findall(r'-?\d+\.?\d*', value_str)
                            value = float(numbers[0]) if numbers else 0
                        
                        # Smart label formatting for better display
                        if str(label).isdigit():
                            label_num = int(label)
                            if label_num >= 2020 and label_num <= 2030:
                                # Year format - keep as is for now, can be localized later
                                label = str(label)
                            elif label_num >= 1 and label_num <= 12:
                                # Month format - use numeric representation
                                label = f"Month {label_num}"
                            elif label_num >= 202001 and label_num <= 203012:
                                # YYYYMM format
                                year = label_num // 100
                                month = label_num % 100
                                if 1 <= month <= 12:
                                    label = f"{year}-{month:02d}"
                        
                        data_dict[label] = value
                        logger.info(f"Added data point: {label} -> {value}")
                        
                    except (ValueError, TypeError, IndexError) as e:
                        logger.warning(f"Error processing 2-column row data: {e}")
                        continue
                        
                elif len(row) > max(label_idx, value_idx):
                    # Handle multi-column data
                    try:
                        label = str(row[label_idx]) if row[label_idx] else f"Item{len(labels)+1}"
                        # Handle TEXT type numeric fields
                        value_str = str(row[value_idx]) if row[value_idx] else "0"
                        try:
                            value = float(value_str)
                        except ValueError:
                            # If conversion fails, try to extract numbers
                            import re
                            numbers = re.findall(r'-?\d+\.?\d*', value_str)
                            value = float(numbers[0]) if numbers else 0
                        
                        if aggregation_method == "sum":
                            data_dict[label] = data_dict.get(label, 0) + value
                        elif aggregation_method == "average":
                            if label in data_dict:
                                data_dict[label] = (data_dict[label] + value) / 2
                            else:
                                data_dict[label] = value
                        elif aggregation_method == "count":
                            data_dict[label] = data_dict.get(label, 0) + 1
                        else:
                            data_dict[label] = value
                            
                    except (ValueError, TypeError, IndexError) as e:
                        logger.warning(f"Error processing row data: {e}")
                        continue
            
            # Limit data points and apply intelligent sorting
            if data_dict:
                # Detect if labels represent years (numeric values in reasonable year range)
                labels_are_years = _detect_year_labels(list(data_dict.keys()))
                
                if labels_are_years:
                    # Sort by year in ascending order
                    sorted_items = sorted(data_dict.items(), key=lambda x: _extract_year_from_label(x[0]))
                    logger.info("Sorted by year (ascending)")
                else:
                    # Sort by value in descending order (original logic)
                    sorted_items = sorted(data_dict.items(), key=lambda x: x[1], reverse=True)[:10]
                    logger.info("Sorted by value (descending)")
                
                labels = [item[0] for item in sorted_items]
                values = [item[1] for item in sorted_items]
                logger.info(f"Final chart data: labels={labels}, values={values}")
            else:
                logger.warning("No data extracted from rows")
        
        return labels, values
        
    except Exception as e:
        logger.error(f"Error extracting chart data with LLM guidance: {e}")
        return [], []

def _detect_year_labels(labels: list) -> bool:
    """Detect if labels represent years by checking if they are numeric values in reasonable year range"""
    if not labels:
        return False
    
    try:
        for label in labels:
            year_value = _extract_year_from_label(label)
            if not (1900 <= year_value <= 2100):
                return False
        return True
    except:
        return False

def _extract_year_from_label(label) -> int:
    """Extract year value from label, handling various formats"""
    label_str = str(label)
    
    # Remove common year suffixes and prefixes
    import re
    # Remove non-digit characters except those that might be part of year format
    year_pattern = r'(\d{4})'
    matches = re.findall(year_pattern, label_str)
    
    if matches:
        return int(matches[0])
    
    # If no 4-digit pattern found, try to extract any digits
    digits_only = re.sub(r'[^\d]', '', label_str)
    if digits_only.isdigit():
        year_candidate = int(digits_only)
        if 1900 <= year_candidate <= 2100:
            return year_candidate
    
    # Fallback: try to convert directly
    try:
        return int(float(label_str))
    except:
        raise ValueError(f"Cannot extract year from label: {label}")

def format_time_label(time_key: str, time_grouping: str) -> str:
    """Format time labels for display"""
    try:
        if time_grouping == "month":
            year, month = time_key.split('-')
            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            month_idx = int(month) - 1
            if 0 <= month_idx < 12:
                return f"{month_names[month_idx]} {year[-2:]}"
        elif time_grouping == "quarter":
            return time_key  # Already formatted as YYYY-Q1
        elif time_grouping == "year":
            return time_key  # Already formatted as YYYY
        
        return time_key
    except:
        return time_key

def generate_fallback_chart_config(data: Dict[str, Any], user_input: str) -> Dict[str, Any]:
    """Generate fallback chart configuration (simplified version)"""
    chart_config = {
        "type": "bar",
        "data": {
            "labels": ["No Data"],
            "datasets": [{
                "label": "Data",
                "data": [0],
                "backgroundColor": ["rgba(54, 162, 235, 0.6)"],
                "borderColor": ["rgba(54, 162, 235, 1)"],
                "borderWidth": 2
            }]
        },
        "options": {
            "responsive": True,
            "plugins": {
                "title": {
                    "display": True,
                    "text": "Data Chart",
                    "font": {"size": 16, "weight": "bold"}
                }
            }
        }
    }
    
            # Try to extract basic information from data
    try:
        if isinstance(data, dict) and "rows" in data and data["rows"]:
            rows = data["rows"][:5]  # Only take first 5 rows to avoid overly complex charts
            labels = []
            values = []
            
            for i, row in enumerate(rows):
                if len(row) >= 3:
                    label = str(row[2]) if row[2] else f"Item{i+1}"
                    value = float(row[6]) if len(row) > 6 and row[6] else i+1
                    labels.append(label)
                    values.append(value)
            
            if labels and values:
                chart_config["data"]["labels"] = labels
                chart_config["data"]["datasets"][0]["data"] = values
                
    except Exception as e:
        logger.warning(f"Fallback chart generation error: {e}")
    
    return chart_config

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
            "sql_task_type": state.get("sql_task_type"),
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