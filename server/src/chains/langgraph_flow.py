"""
Intelligent Data Analysis Flow Based on LangGraph
"""
import json
import time
import uuid
import asyncio
import re
from typing import Dict, Any, List, Optional, TypedDict
import logging
import requests
from langgraph.graph import StateGraph
from ..agents.intelligent_agent import llm, perform_rag_query, get_answer_from_sqltable_datasource, get_query_from_sqltable_datasource
from ..models.data_models import WorkflowEvent, WorkflowEventType, NodeStatus
from ..database.db_operations import get_active_datasource  # Added to get active datasource

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
    """Router node: determine whether to use SQL or RAG based on user input"""
    user_input = state["user_input"]
    
    if not llm:
        logger.warning("LLM not available, using fallback rule-based routing")
        # Fallback to simple rule-based routing
        sql_keywords = [
            "sales", "count", "sum", "average", "total", "report", "data", "table", 
            "chart", "graph", "visualization", "trend", "statistics", "analysis",
            "product", "inventory", "amount", "quantity", "value", "calculate",
            "show me", "how many", "how much", "what is the"
        ]
        
        if any(keyword in user_input.lower() for keyword in sql_keywords):
            query_type = "sql"
        else:
            query_type = "rag"
    else:
        # Use LLM for semantic understanding
        try:
            prompt = f"""
            Analyze the following user query and determine the most appropriate processing method:
            1. sql - Data analysis, statistics, calculations, reports, charts (requires structured data from database)
            2. rag - Knowledge search, document questions, explanations (requires document search)
            
            User query: "{user_input}"
            
            Based on the query content, should this be processed with 'sql' or 'rag'?
            Only answer 'sql' or 'rag' (lowercase, no explanation needed).
            """
            
            response = llm.invoke(prompt)
            
            # Handle different response types
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
            sql_keywords = [
                "sales", "count", "sum", "average", "total", "report", "data", "table", 
                "chart", "graph", "visualization", "trend", "statistics", "analysis",
                "product", "inventory", "amount", "quantity", "value", "calculate",
                "show me", "how many", "how much", "what is the"
            ]
            
            if any(keyword in user_input.lower() for keyword in sql_keywords):
                query_type = "sql"
            else:
                query_type = "rag"
    
    logger.info(f"Router decision result: {query_type} for input: {user_input}")
    
    return {**state, "query_type": query_type}

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
    
    # Return updated state while preserving existing state
    return {**state, "sql_task_type": sql_task_type}

async def sql_query_node(state: GraphState) -> GraphState:
    """SQL query node: execute SQL query and return results"""
    try:
        user_input = state["user_input"]
        datasource = state.get("datasource")  # Get datasource from state
        
        if not datasource:
            error_msg = "No data source found in state. Please select or create a data source first."
            logger.error(error_msg)
            return {
                **state,
                "error": error_msg,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "sql_query": {
                        "status": "error",
                        "timestamp": time.time(),
                        "error": "No datasource in state"
                    }
                }
            }
        
        # Call SQL query logic with improved error handling
        result = await get_query_from_sqltable_datasource(
            user_input, 
            datasource
        )
        
        if result["success"]:
            structured_data = result.get("data", {})
            executed_sql = result.get("executed_sql", "")
            
            # Validate the result structure
            if not structured_data:
                error_msg = "No structured data returned from query"
                logger.error(error_msg)
                return {
                    **state,
                    "error": error_msg,
                    "node_outputs": {
                        **state.get("node_outputs", {}),
                        "sql_query": {
                            "status": "error",
                            "timestamp": time.time(),
                            "error": "No data available"
                        }
                    }
                }
            
            logger.info(f"SQL query successful, data: {structured_data}")
            
            return {
                **state,
                "structured_data": structured_data,
                "answer": result["answer"],
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "sql_query": {
                        "status": "completed",
                        "timestamp": time.time(),
                        "data_summary": {
                            "row_count": len(structured_data.get("rows", [])),
                            "executed_sql": executed_sql,
                            "has_answer": bool(result.get("answer"))
                        }
                    }
                }
            }
        else:
            error_msg = result.get("error", "SQL query execution failed")
            logger.error(f"SQL query failed: {error_msg}")
            
            return {
                **state,
                "error": error_msg,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "sql_query": {
                        "status": "error",
                        "timestamp": time.time(),
                        "error": error_msg
                    }
                }
            }
    except Exception as e:
        error_msg = f"Unexpected error in SQL query node: {str(e)}"
        logger.exception(error_msg)
        return {
            **state,
            "error": error_msg,
            "node_outputs": {
                **state.get("node_outputs", {}),
                "sql_query": {
                    "status": "error",
                    "timestamp": time.time(),
                    "error": error_msg
                }
            }
        }

async def sql_chart_node(state: GraphState) -> GraphState:
    """SQL chart node: execute SQL query for chart data"""
    try:
        user_input = state["user_input"]
        datasource = state["datasource"]
        
        # Call existing SQL query logic with chart context
        result = await get_answer_from_sqltable_datasource(user_input, datasource)
        
        if result["success"]:
            structured_data = result["data"]
            
            # Ensure we have the required data for charting
            if not structured_data.get("rows"):
                return {
                    **state,
                    "error": "No data returned for chart generation",
                    "node_outputs": {
                        **state.get("node_outputs", {}),
                        "sql_chart": {
                            "status": "error",
                            "timestamp": time.time(),
                            "error": "No data available for charting"
                        }
                    }
                }
            
            logger.info(f"SQL chart data query successful, data rows: {len(structured_data.get('rows', []))}")
            
            # Update state with chart data
            return {
                **state,
                "structured_data": structured_data,
                "answer": result["answer"],
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "sql_chart": {
                        "status": "completed",
                        "timestamp": time.time(),
                        "data_summary": {
                            "row_count": len(structured_data.get("rows", [])),
                            "executed_sql": structured_data.get("executed_sql"),
                            "queried_table": structured_data.get("queried_table")
                        }
                    }
                }
            }
        else:
            error_msg = result.get("error", "SQL chart data query failed")
            logger.error(f"SQL chart query failed: {error_msg}")
            return {
                **state,
                "error": error_msg,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "sql_chart": {
                        "status": "error",
                        "timestamp": time.time(),
                        "error": error_msg
                    }
                }
            }
    except Exception as e:
        error_msg = f"SQL chart node error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            **state,
            "error": error_msg,
            "node_outputs": {
                **state.get("node_outputs", {}),
                "sql_chart": {
                    "status": "error",
                    "timestamp": time.time(),
                    "error": error_msg
                }
            }
        }

def chart_config_node(state: GraphState) -> GraphState:
    """Chart configuration node: generate chart configuration"""
    try:
        structured_data = state.get("structured_data", {})
        user_input = state["user_input"]
        
        # Generate chart configuration based on data and user requirements
        chart_config = generate_chart_config(structured_data, user_input)
        
        return {**state, "chart_config": chart_config}
    except Exception as e:
        logger.error(f"Chart config node error: {e}")
        return {**state, "error": str(e)}

async def rag_query_node(state: GraphState) -> GraphState:
    """RAG query node"""
    try:
        user_input = state["user_input"]
        datasource = state["datasource"]
        
        # Call RAG query logic
        result = await perform_rag_query(user_input, datasource)
        
        if result["success"]:
            return {
                **state,
                "answer": result["answer"],
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    "rag_query": {
                        "status": "completed",
                        "timestamp": time.time(),
                        "data": result.get("data", {})
                    }
                }
            }
        else:
            return {**state, "error": result.get("error", "RAG query failed")}
    except Exception as e:
        logger.error(f"RAG query node error: {e}")
        return {**state, "error": str(e)}

def chart_rendering_node(state: GraphState) -> GraphState:
    """Chart rendering node: render chart from configuration"""
    try:
        chart_config = state.get("chart_config")
        if not chart_config:
            return {**state, "error": "Missing chart configuration"}
        
        # Generate chart image
        chart_image = generate_chart_image(chart_config)
        
        return {**state, "chart_image": chart_image}
    except Exception as e:
        logger.error(f"Chart rendering error: {e}")
        return {**state, "error": str(e)}

def llm_processing_node(state: GraphState) -> GraphState:
    """LLM processing node: process results with LLM for natural language response"""
    try:
        user_input = state["user_input"]
        structured_data = state.get("structured_data")
        chart_image = state.get("chart_image")
        existing_answer = state.get("answer", "")
        error = state.get("error")
        
        # Debug logging
        logger.info(f"LLM Processing Node - Input: {user_input}")
        logger.info(f"LLM Processing Node - Has structured_data: {bool(structured_data)}")
        logger.info(f"LLM Processing Node - Has chart_image: {bool(chart_image)}")
        logger.info(f"LLM Processing Node - Existing answer: '{existing_answer}'")
        logger.info(f"LLM Processing Node - Error: {error}")
        
        if structured_data:
            logger.info(f"LLM Processing Node - Structured data keys: {list(structured_data.keys())}")
            rows = structured_data.get("rows", [])
            logger.info(f"LLM Processing Node - Number of rows: {len(rows)}")
            if rows:
                logger.info(f"LLM Processing Node - First row: {rows[0]}")
        
        # If there's an error, provide a helpful response
        if error:
            final_answer = f"I encountered an issue while processing your request: {error}. Please try rephrasing your question or check if the data source is properly configured."
            logger.info(f"LLM Processing Node - Returning error response: {final_answer}")
            return {**state, "answer": final_answer}
        
        # If there's already an answer from RAG, use it
        if existing_answer and not structured_data and not chart_image:
            logger.info(f"LLM Processing Node - Using existing RAG answer: {existing_answer}")
            return {**state, "answer": existing_answer}
        
        # For SQL results, generate a natural language response
        if structured_data:
            if chart_image:
                final_answer = f"I've generated a chart to visualize the results for your query: '{user_input}'. The chart shows the data from your analysis."
                logger.info(f"LLM Processing Node - Chart response: {final_answer}")
            else:
                # Generate intelligent text-based answer from structured data
                rows = structured_data.get("rows", [])
                columns = structured_data.get("columns", [])
                executed_sql = structured_data.get("executed_sql", "")
                
                logger.info(f"LLM Processing Node - Processing SQL results: rows={len(rows)}, columns={columns}")
                
                if rows:
                    logger.info("LLM Processing Node - Calling _generate_intelligent_sql_response")
                    final_answer = _generate_intelligent_sql_response(user_input, rows, columns, executed_sql)
                    logger.info(f"LLM Processing Node - Generated intelligent response: {final_answer[:200]}...")
                else:
                    final_answer = f"No data was found matching your query '{user_input}'. Please try a different question or check if the data exists."
                    logger.info(f"LLM Processing Node - No rows response: {final_answer}")
        else:
            final_answer = existing_answer or f"I've processed your query '{user_input}' but couldn't generate specific results. Please try rephrasing your question."
            logger.info(f"LLM Processing Node - Fallback response: {final_answer}")
        
        logger.info(f"LLM Processing Node - Final answer: {final_answer[:100]}...")
        return {**state, "answer": final_answer}
    except Exception as e:
        logger.error(f"LLM processing error: {e}")
        import traceback
        logger.error(f"LLM processing traceback: {traceback.format_exc()}")
        return {**state, "error": f"LLM processing failed: {e}"}

def _generate_intelligent_sql_response(user_input: str, rows: list, columns: list, executed_sql: str = "") -> str:
    """Generate intelligent natural language response from SQL results"""
    try:
        logger.info(f"_generate_intelligent_sql_response called with {len(rows)} rows, columns: {columns}")
        
        if not rows:
            logger.info("No rows found, returning no results message")
            return f"No results were found for your query: '{user_input}'"
        
        # Analyze the query type and data structure
        query_lower = user_input.lower()
        row_count = len(rows)
        
        logger.info(f"Query analysis: row_count={row_count}, query_lower='{query_lower}'")
        
        # Single value result
        if row_count == 1 and len(rows[0]) == 1:
            logger.info("Processing single value result")
            value = list(rows[0].values())[0]
            if isinstance(value, (int, float)):
                formatted_value = f"{value:,.2f}" if isinstance(value, float) else f"{value:,}"
            else:
                formatted_value = str(value)
            result = f"Based on your query '{user_input}', the result is: {formatted_value}"
            logger.info(f"Single value result: {result}")
            return result
        
        # Category-value pairs (like our average price case)
        if row_count > 1 and len(columns) == 2:
            logger.info("Processing category-value pairs")
            # Check if this looks like category-value data
            first_row = rows[0]
            logger.info(f"First row structure: {first_row}")
            
            if 'category' in first_row and 'value' in first_row:
                logger.info("Detected category-value structure, processing intelligent response")
                # Sort by value for better presentation
                sorted_rows = sorted(rows, key=lambda x: x.get('value', 0), reverse=True)
                logger.info(f"Sorted rows: {sorted_rows}")
                
                response_lines = [f"Here are the results for '{user_input}':"]
                
                for i, row in enumerate(sorted_rows):
                    category = row.get('category', 'Unknown')
                    value = row.get('value', 0)
                    
                    # Format value based on the query context
                    if 'price' in query_lower or 'cost' in query_lower or 'amount' in query_lower:
                        formatted_value = f"${value:.2f}"
                    elif 'percentage' in query_lower or 'percent' in query_lower:
                        formatted_value = f"{value:.1f}%"
                    elif isinstance(value, float):
                        formatted_value = f"{value:.2f}"
                    else:
                        formatted_value = f"{value:,}"
                    
                    response_lines.append(f"• {category}: {formatted_value}")
                
                # Add insights for average/price queries
                if 'average' in query_lower and 'price' in query_lower:
                    logger.info("Adding price insights")
                    highest = sorted_rows[0]
                    lowest = sorted_rows[-1]
                    response_lines.append(f"\nKey insights:")
                    response_lines.append(f"• Highest average price: {highest['category']} (${highest['value']:.2f})")
                    response_lines.append(f"• Lowest average price: {lowest['category']} (${lowest['value']:.2f})")
                    
                    price_diff = highest['value'] - lowest['value']
                    response_lines.append(f"• Price range: ${price_diff:.2f}")
                
                result = "\n".join(response_lines)
                logger.info(f"Category-value response generated: {result[:200]}...")
                return result
        
        logger.info("Processing as generic structured data")
        # Generic structured data response
        if row_count <= 10:
            # For small result sets, show details
            response_lines = [f"Found {row_count} results for '{user_input}':"]
            
            for i, row in enumerate(rows):
                if len(row) == 1:
                    value = list(row.values())[0]
                    response_lines.append(f"{i+1}. {value}")
                else:
                    # Multi-column row
                    row_parts = []
                    for key, value in row.items():
                        if isinstance(value, (int, float)) and key.lower() in ['price', 'cost', 'amount', 'total']:
                            formatted_value = f"${value:.2f}" if isinstance(value, float) else f"${value:,}"
                        elif isinstance(value, float):
                            formatted_value = f"{value:.2f}"
                        elif isinstance(value, int):
                            formatted_value = f"{value:,}"
                        else:
                            formatted_value = str(value)
                        row_parts.append(f"{key}: {formatted_value}")
                    response_lines.append(f"{i+1}. {', '.join(row_parts)}")
            
            result = "\n".join(response_lines)
            logger.info(f"Generic detailed response: {result[:200]}...")
            return result
        else:
            # For large result sets, provide summary
            result = f"Found {row_count} results for '{user_input}'. The data contains {len(columns)} columns: {', '.join(columns)}. Use filters or more specific queries to narrow down the results."
            logger.info(f"Large dataset summary: {result}")
            return result
    
    except Exception as e:
        logger.error(f"Error generating intelligent SQL response: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return f"I found {len(rows)} results for your query '{user_input}', but had trouble formatting the response. The data is available but the presentation failed."

def validation_node(state: GraphState) -> GraphState:
    """Output validation node - Enhanced with LLM-based quality assessment"""
    try:
        answer = state.get("answer", "")
        user_input = state.get("user_input", "")
        structured_data = state.get("structured_data", {})
        error = state.get("error")
        chart_image = state.get("chart_image")
        
        # Initialize scores for different dimensions
        scores = {
            "relevance": 0,  # How well the answer addresses the user's question
            "completeness": 0,  # Whether all aspects of the question are addressed
            "accuracy": 0,  # Accuracy of the information provided
            "clarity": 0,  # How clear and well-structured the answer is
            "data_support": 0  # Whether the answer is supported by data
        }
        
        # If there's an error, return low quality score
        if error:
            return {
                "quality_score": 0,
                "validation_details": {
                    "error": error,
                    "scores": scores,
                    "feedback": "Failed due to error"
                }
            }

        # Prepare prompt for LLM evaluation
        evaluation_prompt = """
        Please evaluate the following answer for a data analysis question. 
        Rate each aspect on a scale of 0-10 and provide specific feedback.

        User Question: {question}

        Generated Answer: {answer}

        Data Available: {data}
        Chart Generated: {chart}

        Evaluate the following aspects:
        1. Relevance (0-10): How well does the answer address the user's specific question?
        2. Completeness (0-10): Does the answer cover all aspects of the question?
        3. Accuracy (0-10): Based on the provided data, how accurate is the answer?
        4. Clarity (0-10): How clear and well-structured is the answer?
        5. Data Support (0-10): How well is the answer supported by data or visualizations?

        Provide your evaluation in the following format:
        {{
            "scores": {{
                "relevance": [number 0-10],
                "completeness": [number 0-10],
                "accuracy": [number 0-10],
                "clarity": [number 0-10],
                "data_support": [number 0-10]
            }},
            "feedback": "[detailed feedback about strengths and areas for improvement]"
        }}
        """.format(
            question=user_input,
            answer=answer,
            data=json.dumps(structured_data) if structured_data else 'No structured data',
            chart='Yes' if chart_image else 'No'
        )

        # Call LLM for evaluation
        try:
            evaluation_result = llm.invoke(evaluation_prompt)
            # Parse the JSON response
            evaluation_data = json.loads(evaluation_result)
            scores = evaluation_data["scores"]
            feedback = evaluation_data["feedback"]
        except Exception as e:
            logger.error(f"LLM evaluation failed: {e}")
            # Fallback to basic scoring if LLM fails
            scores = {
                "relevance": 7 if len(answer) > 50 else 4,
                "completeness": 7 if structured_data else 4,
                "accuracy": 7 if not error else 3,
                "clarity": 7 if len(answer.split()) > 20 else 4,
                "data_support": 7 if structured_data or chart_image else 3
            }
            feedback = "Fallback scoring used due to LLM evaluation failure"

        # Calculate final quality score (weighted average)
        weights = {
            "relevance": 0.3,
            "completeness": 0.2,
            "accuracy": 0.2,
            "clarity": 0.15,
            "data_support": 0.15
        }
        
        final_score = sum(scores[k] * weights[k] for k in weights)
        final_score = round(final_score)  # Round to nearest integer
        
        # Ensure score is within bounds
        final_score = max(0, min(10, final_score))
        
        # Force a higher score if we've retried too many times
        retry_count = state.get("retry_count", 0)
        if retry_count >= 1:  # After 1 retry, force completion
            final_score = 7
            feedback += " (Score adjusted to prevent excessive retries)"
        
        return {
            "quality_score": final_score,
            "validation_details": {
                "scores": scores,
                "feedback": feedback,
                "final_score": final_score,
                "weights_used": weights
            }
        }
    except Exception as e:
        logger.error(f"Validation node error: {e}")
        # Return a passing score to prevent infinite retries
        return {
            "quality_score": 7,
            "validation_details": {
                "error": str(e),
                "scores": scores,
                "feedback": "Validation failed, defaulting to passing score to prevent retries"
            }
        }

def retry_node(state: GraphState) -> GraphState:
    """Retry node"""
    retry_count = state.get("retry_count", 0)
    
    if retry_count >= 1:  # Maximum 1 retry
        return {
            "answer": "Sorry, after multiple attempts, we still cannot generate satisfactory results. Please try to rephrase your question.",
            "quality_score": 10  # Set high score to end the process
        }
    
    return {
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
            "time_grouping": "none|week|month|quarter|year",
            "is_time_series": true|false
        }}
        
        Analysis requirements:
        1. Determine the most suitable chart type based on user query
        2. Generate meaningful titles and axis labels
        3. Identify which fields in the data should be used for labels and values
        4. **CRITICAL**: Analyze if this is a time series query by looking for keywords:
           - "trend", "over time", "monthly", "weekly", "yearly", "quarterly"
           - "sales trend", "time series", "by month", "by year", "by quarter"
           - "2025", specific years, date ranges
           - If ANY time-related keywords found, set "is_time_series": true and appropriate "time_grouping"
        5. Pay attention to time units mentioned in user query:
           - If user mentions "week" or "weekly": set time_grouping to "week"
           - If user mentions "month" or "monthly": set time_grouping to "month"  
           - If user mentions "year" or "yearly": set time_grouping to "year"
           - If user mentions "quarter" or "quarterly": set time_grouping to "quarter"
           - If user mentions "trend" without specific time unit, default to "month"
        6. Generate appropriate x_axis_label based on time grouping:
           - For week grouping: use "Week"
           - For month grouping: use "Month"
           - For year grouping: use "Year"
           - For quarter grouping: use "Quarter"
           - For non-time series: use appropriate category label
        7. For time series data:
           - Always use "line" chart type for trends
           - Set data_field_for_labels to "0" (first column, usually time)
           - Set data_field_for_values to "1" (second column, usually aggregated values)
        8. Only return JSON, no other explanation
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
        labels, values = extract_chart_data_with_llm_guidance(data, chart_analysis, user_input)
        
        if labels and values:
            chart_config["data"]["labels"] = labels
            chart_config["data"]["datasets"][0]["data"] = values

            # Ensure backgroundColor and borderColor arrays与数据点数量一致
            base_colors_bg = [
                "rgba(54, 162, 235, 0.6)",
                "rgba(255, 99, 132, 0.6)",
                "rgba(255, 206, 86, 0.6)",
                "rgba(75, 192, 192, 0.6)",
                "rgba(153, 102, 255, 0.6)",
                "rgba(255, 159, 64, 0.6)",
                "rgba(199, 199, 199, 0.6)",
                "rgba(83, 102, 255, 0.6)"
            ]
            def to_border(c):
                # 将透明度由 0.6 调整为 1 形成描边色
                if c.endswith("0.6)"):
                    return c.replace("0.6)", "1)")
                return c

            num_points = len(values)
            colors_bg = [base_colors_bg[i % len(base_colors_bg)] for i in range(num_points)]
            colors_border = [to_border(c) for c in colors_bg]

            chart_config["data"]["datasets"][0]["backgroundColor"] = colors_bg
            chart_config["data"]["datasets"][0]["borderColor"] = colors_border
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

def extract_chart_data_with_llm_guidance(data: Dict[str, Any], chart_analysis: Dict[str, Any], user_input: str = "") -> tuple:
    """Extract chart data based on LLM analysis results"""
    try:
        labels = []
        values = []
        
        if not isinstance(data, dict) or "rows" not in data or not data["rows"]:
            logger.error("No valid data found in extract_chart_data_with_llm_guidance")
            return labels, values
        
        rows = data["rows"]
        aggregation_method = chart_analysis.get("aggregation_method", "none")
        time_grouping = chart_analysis.get("time_grouping", "none")
        is_time_series = chart_analysis.get("is_time_series", False)
        
        # Smart field detection based on data structure
        sample_row = rows[0] if rows else {}
        logger.info(f"Processing sample row: {sample_row}, type: {type(sample_row)}")
        
        # Handle dictionary format with category/value keys (from parsed string results)
        if isinstance(sample_row, dict) and "category" in sample_row and "value" in sample_row:
            logger.info(f"Processing {len(rows)} rows of category-value data")
            
            # Use LLM to intelligently analyze the data and user intent
            if llm:
                try:
                    # Prepare comprehensive data context for LLM
                    sample_data = rows[:5]  # Use first 5 rows as sample
                    sample_categories = [str(row.get("category", "")) for row in sample_data]
                    sample_values = [row.get("value", 0) for row in sample_data]
                    
                    # Let LLM freely analyze without constraints
                    analysis_prompt = f"""
                    You are an expert data analyst. Analyze the following user request and data to determine the best processing strategy.
                    
                    USER REQUEST: "{user_input}"
                    
                    DATA CONTEXT:
                    - Total records: {len(rows)}
                    - Sample categories: {sample_categories}
                    - Sample values: {sample_values}
                    - First few records: {sample_data}
                    
                    Based on your expertise, provide a comprehensive analysis plan in JSON format. You have complete freedom to design the response structure. Consider:
                    
                    1. What type of data is this? (time series, categorical, hierarchical, etc.)
                    2. What does the user want to achieve?
                    3. How should the data be filtered, sorted, and limited?
                    4. What would be the most meaningful way to present this data?
                    
                    Design your own JSON structure that best captures your analysis. Be creative and thorough.
                    
                    Return only valid JSON, no other text.
                    """
                    
                    response = llm.invoke(analysis_prompt)
                    
                    # Parse LLM response
                    if hasattr(response, 'content'):
                        analysis_text = response.content
                    elif isinstance(response, str):
                        analysis_text = response
                    else:
                        analysis_text = str(response)
                    
                    # Extract JSON
                    import json
                    json_match = re.search(r'\{.*\}', analysis_text, re.DOTALL)
                    if json_match:
                        intelligent_analysis = json.loads(json_match.group())
                        logger.info(f"LLM dynamic analysis result: {intelligent_analysis}")
                        
                        # Apply LLM's custom analysis strategy
                        processed_rows = _apply_dynamic_analysis_strategy(rows, intelligent_analysis, user_input)
                        
                    else:
                        raise ValueError("No valid JSON found in LLM response")
                        
                except Exception as e:
                    logger.warning(f"LLM dynamic analysis failed: {e}, using fallback detection")
                    # Fallback to simple pattern detection
                    intelligent_analysis = _fallback_data_analysis(sample_row, user_input, len(rows))
                    processed_rows = _apply_standard_analysis_strategy(rows, intelligent_analysis)
            else:
                # No LLM available, use fallback
                intelligent_analysis = _fallback_data_analysis(sample_row, user_input, len(rows))
                processed_rows = _apply_standard_analysis_strategy(rows, intelligent_analysis)
            
            # Extract final labels and values
            for row in processed_rows:
                try:
                    label = str(row["category"]) if row["category"] else f"Item{len(labels)+1}"
                    value = float(row["value"]) if isinstance(row["value"], (int, float)) else 0
                    
                    labels.append(label)
                    values.append(value)
                    logger.info(f"Added data point: {label} -> {value}")
                    
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Error processing row: {e}")
                    continue
            
            logger.info(f"Successfully extracted {len(labels)} data points using dynamic analysis")
            return labels, values
        
        # Handle original logic for other data formats
        num_cols = len(sample_row) if isinstance(sample_row, (list, tuple)) else len(sample_row.keys()) if isinstance(sample_row, dict) else 0
        
        # For time series queries, intelligently detect time and value fields
        if is_time_series or time_grouping != "none" or any(keyword in user_input.lower() for keyword in ['trend', 'monthly', 'yearly', 'over time']):
            # This is likely a time series query
            if num_cols == 2:
                # Two columns: likely (time/period, value)
                label_idx, value_idx = 0, 1
            elif isinstance(sample_row, dict) and "label" in sample_row and "value" in sample_row:
                # Dictionary format from parsed results
                label_field, value_field = "label", "value"  
                label_idx, value_idx = "label", "value"
            else:
                # Multi-column: use field specification or defaults
                label_field = chart_analysis.get("data_field_for_labels", "0")  # First column for time
                value_field = chart_analysis.get("data_field_for_values", "1")  # Second column for values
                try:
                    label_idx = int(label_field) if str(label_field).isdigit() else 0
                    value_idx = int(value_field) if str(value_field).isdigit() else 1
                    # Ensure indices are within bounds
                    if label_idx >= num_cols: label_idx = 0
                    if value_idx >= num_cols: value_idx = min(1, num_cols - 1)
                except (ValueError, TypeError):
                    label_idx, value_idx = 0, min(1, num_cols - 1)
        else:
            # Non-time series: use original logic
            label_field = chart_analysis.get("data_field_for_labels", "2")  # Default product name  
            value_field = chart_analysis.get("data_field_for_values", "6")  # Default total amount
            try:
                label_idx = int(label_field) if str(label_field).isdigit() else 2
                value_idx = int(value_field) if str(value_field).isdigit() else 6
                # Ensure indices are within bounds
                if num_cols > 0:
                    if label_idx >= num_cols: label_idx = min(2, num_cols - 1)
                    if value_idx >= num_cols: value_idx = min(num_cols - 1, max(1, num_cols - 1))
            except (ValueError, TypeError):
                label_idx, value_idx = min(2, num_cols - 1), min(num_cols - 1, max(1, num_cols - 1))
        
        logger.info(f"Using label_idx: {label_idx}, value_idx: {value_idx}")
        logger.info(f"Sample row: {sample_row}")
        logger.info(f"Is time series: {is_time_series}, Time grouping: {time_grouping}")
        
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
                            elif time_grouping == "week":
                                # Extract year-week, format as YYYY-WW
                                if '-' in date_str and len(date_str) >= 10:
                                    # Convert date to week format using strftime logic
                                    try:
                                        from datetime import datetime
                                        date_obj = datetime.strptime(date_str[:10], '%Y-%m-%d')
                                        year = date_obj.isocalendar()[0]
                                        week = date_obj.isocalendar()[1]
                                        time_key = f"{year}-W{week:02d}"
                                    except ValueError:
                                        # Fallback: use first 7 characters
                                        time_key = date_str[:7]
                                else:
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
                    elif time_grouping == "week":
                        year, week_str = key.split('-W')
                        return int(year) * 100 + int(week_str)
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
                
                # Handle dictionary format with label/value keys (from parsed string results)
                if isinstance(row, dict) and "label" in row and "value" in row:
                    try:
                        label = str(row["label"]) if row["label"] else f"Item{len(labels)+1}"
                        value = float(row["value"]) if isinstance(row["value"], (int, float)) else 0
                        
                        # Smart label formatting for better display based on context
                        label = _format_label_based_on_context(label, chart_analysis, user_input)
                        
                        data_dict[label] = value
                        logger.info(f"Added data point: {label} -> {value}")
                        
                    except (ValueError, TypeError, IndexError) as e:
                        logger.warning(f"Error processing dictionary row data: {e}")
                        continue
                        
                elif len(row) == 2:
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
                        
                        # Smart label formatting for better display based on context
                        label = _format_label_based_on_context(label, chart_analysis, user_input)
                        
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
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
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

def _format_label_based_on_context(label: str, chart_analysis: Dict[str, Any], user_input: str) -> str:
    """Format label based on query context and chart analysis"""
    try:
        if not str(label).isdigit():
            return label
            
        label_num = int(label)
        
        # Analyze user input to determine context
        user_input_lower = user_input.lower()
        
        # Check if it's explicitly about products
        if any(keyword in user_input_lower for keyword in ['product', 'item', 'goods', 'merchandise']):
            return f"Product {label}"
            
        # Check if it's explicitly about time periods
        elif any(keyword in user_input_lower for keyword in ['month', 'monthly', 'quarter', 'quarterly', 'year', 'yearly', 'time', 'trend']):
            if label_num >= 2020 and label_num <= 2030:
                return str(label)  # Year format
            elif label_num >= 1 and label_num <= 12:
                return f"Month {label_num}"
            elif label_num >= 202001 and label_num <= 203012:
                year = label_num // 100
                month = label_num % 100
                if 1 <= month <= 12:
                    return f"{year}-{month:02d}"
            else:
                return f"Period {label}"
                
        # Default logic based on number characteristics
        else:
            if label_num >= 2020 and label_num <= 2030:
                # Likely year
                return str(label)
            elif label_num >= 202001 and label_num <= 203012:
                # YYYYMM format
                year = label_num // 100
                month = label_num % 100
                if 1 <= month <= 12:
                    return f"{year}-{month:02d}"
            else:
                # For other numbers, assume product ID by default
                # This is safer than assuming months for 1-12
                return f"Product {label}"
                
    except (ValueError, TypeError):
        return str(label)

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
        elif time_grouping == "week":
            if '-W' in time_key:
                year, week_str = time_key.split('-W')
                return f"{year}-W{week_str}"
            else:
                return time_key
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

# Enhanced flow processing function with WebSocket support
async def process_intelligent_query(
    user_input: str, 
    datasource: Dict[str, Any], 
    execution_id: str = None
) -> Dict[str, Any]:
    """
    Process intelligent analysis query using LangGraph, with WebSocket support.
    """
    
    # Import WebSocket manager
    from ..websocket.websocket_manager import websocket_manager
    
    if not datasource:
        return {
            "success": False,
            "error": "No active data source found. Please select or create a data source first.",
            "user_input": user_input
        }
    
    # Define workflow graph
    workflow = StateGraph(GraphState)
    
    # Add nodes to the graph
    workflow.add_node("start_node", lambda state: state)  # Start node just passes through
    workflow.add_node("router_node", router_node)
    workflow.add_node("sql_classifier_node", sql_classifier_node)
    workflow.add_node("sql_query_node", sql_query_node)  # New node for SQL queries
    workflow.add_node("sql_chart_node", sql_chart_node)  # Renamed from sql_execution_node
    workflow.add_node("rag_query_node", rag_query_node)
    workflow.add_node("chart_config_node", chart_config_node)
    workflow.add_node("chart_rendering_node", chart_rendering_node)
    workflow.add_node("llm_processing_node", llm_processing_node)
    workflow.add_node("validation_node", validation_node)
    workflow.add_node("retry_node", retry_node)
    workflow.add_node("end_node", lambda state: {"success": True})

    # Set entry point
    workflow.set_entry_point("start_node")
    
    # Connect start to router
    workflow.add_edge("start_node", "router_node")

    # Add edges
    workflow.add_conditional_edges(
        "router_node",
        lambda state: state["query_type"],
        {
            "sql": "sql_classifier_node",
            "rag": "rag_query_node"
        }
    )

    # SQL Classifier routes based on task type
    workflow.add_conditional_edges(
        "sql_classifier_node",
        lambda state: state["sql_task_type"],
        {
            "query": "sql_query_node",     # Query task goes to SQL Query node
            "chart": "sql_chart_node"      # Chart task goes to SQL Chart node
        }
    )

    # Connect SQL Query node to LLM Processing
    workflow.add_edge("sql_query_node", "llm_processing_node")

    # Connect SQL Chart node to Chart Config
    workflow.add_edge("sql_chart_node", "chart_config_node")

    # Rest of the edges remain the same
    workflow.add_edge("chart_config_node", "chart_rendering_node")
    workflow.add_edge("chart_rendering_node", "llm_processing_node")
    workflow.add_edge("rag_query_node", "llm_processing_node")
    workflow.add_edge("llm_processing_node", "validation_node")

    # Add conditional edges for validation
    workflow.add_conditional_edges(
        "validation_node",
        lambda state: "retry" if state["quality_score"] < 7 else "end",
        {
            "retry": "retry_node",
            "end": "end_node"
        }
    )

    # Connect retry node back to LLM processing
    workflow.add_edge("retry_node", "llm_processing_node")

    # Set finish point
    workflow.set_finish_point("end_node")

    # Compile the graph
    app = workflow.compile()
    
    # Initial state
    initial_state = {
        "user_input": user_input,
        "datasource": datasource,
        "query_type": "",  # Will be set by router_node
        "sql_task_type": "",  # Will be set by sql_classifier_node
        "structured_data": None,
        "chart_config": None,
        "chart_image": None,
        "answer": "",
        "quality_score": 10,
        "retry_count": 0,
        "error": None
    }
    
    config = {"recursion_limit": 50, "configurable": {"execution_id": execution_id}}
    
    # Helper to emit events
    async def emit_event(event_type: WorkflowEventType, node_id: str = None, **kwargs):
        if execution_id:
            event = WorkflowEvent(
                type=event_type,
                timestamp=time.time(),  # Add current timestamp
                execution_id=execution_id, 
                node_id=node_id, 
                **kwargs
            )
            await websocket_manager.broadcast_to_execution(execution_id, event)
    
    await emit_event("execution_started", data={"query": user_input})
    
    final_state = None
    
    try:
        # Use both astream_events for real-time updates and astream for final state
        events_task = None
        async def track_events():
            async for event in app.astream_events(initial_state, config, version="v1"):
                kind = event["event"]
                
                if kind == "on_chain_start":
                    node_name = event.get("name", "")
                    logger.info(f"Node started: {node_name}")
                    await emit_event("node_started", node_id=node_name)
                
                elif kind == "on_chain_end":
                    node_name = event.get("name", "")
                    logger.info(f"Node completed: {node_name}")
                    await emit_event("node_completed", node_id=node_name, data=event.get("data"))
                
                elif kind == "on_chain_error":
                    node_name = event.get("name", "")
                    logger.error(f"Node error: {node_name} - {event.get('data')}")
                    await emit_event("node_error", node_id=node_name, error=str(event.get("data", "")))
        
        # Start event tracking in background and get final state
        events_task = asyncio.create_task(track_events())
        
        # Get the complete final state using astream
        # We need to accumulate the state throughout the execution
        accumulated_state = initial_state.copy()
        async for state in app.astream(initial_state, config):
            if isinstance(state, dict):
                accumulated_state.update(state)
            else:
                # Handle AddableUpdatesDict or similar types
                for key, value in state.items():
                    accumulated_state[key] = value
        
        final_state = accumulated_state
        
        # Wait for events to complete
        if events_task:
            try:
                await events_task
            except Exception as e:
                logger.warning(f"Event tracking completed with exception: {e}")
        
        # final_state should now be the complete final state
        if not isinstance(final_state, dict):
            final_state = {}
        
        logger.info(f"Final state structure: {type(final_state)}")
        logger.info(f"Sending execution_completed event for {execution_id} with final_state keys: {list(final_state.keys()) if isinstance(final_state, dict) else 'not_dict'}")
        
        # Make sure we're sending a dict for the WorkflowEvent
        final_state_for_event = final_state if isinstance(final_state, dict) else {}
        await emit_event("execution_completed", data=final_state_for_event)
        logger.info(f"Execution completed event sent for {execution_id}")
        
        return {
            "success": not final_state.get("error"),
            **final_state
        }
    
    except Exception as e:
        logger.error(f"Error during graph execution for {execution_id}: {e}")
        await emit_event("execution_error", error=str(e))
        return {
            "success": False,
            "user_input": user_input,
            "error": str(e)
        }
    finally:
        # Final cleanup - let routes.py handle this after sending completion event
        logger.info(f"Execution {execution_id} finished or was terminated.")

def _fallback_data_analysis(sample_row: Dict[str, Any], user_input: str, total_rows: int) -> Dict[str, Any]:
    """Fallback data analysis when LLM is not available or fails"""
    try:
        sample_category = str(sample_row.get("category", ""))
        user_lower = user_input.lower()
        
        # Detect if it's time series data
        is_date_format = bool(re.match(r'^\d{4}(-\d{2})?(-\d{2})?$', sample_category))
        has_time_keywords = any(keyword in user_lower for keyword in [
            'trend', 'monthly', 'weekly', 'yearly', 'over time', 'time series', 'quarterly'
        ])
        
        is_time_series = is_date_format and has_time_keywords
        
        # Determine year filter
        year_filter = None
        if '2025' in user_input and '2024' not in user_input:
            year_filter = "2025"
        elif '2024' in user_input and '2025' not in user_input:
            year_filter = "2024"
        
        # Determine sort strategy
        if is_time_series:
            sort_strategy = "chronological"
        elif any(keyword in user_lower for keyword in ['top', 'highest', 'best', 'largest']):
            sort_strategy = "value_desc"
        elif any(keyword in user_lower for keyword in ['lowest', 'smallest', 'worst']):
            sort_strategy = "value_asc"
        else:
            sort_strategy = "value_desc"  # Default
        
        # Determine data limit
        if is_time_series:
            data_limit = None  # No limit for time series
        else:
            data_limit = 10  # Limit for category data
        
        # Determine chart type
        chart_type = "line" if is_time_series else "bar"
        
        return {
            "is_time_series": is_time_series,
            "data_type": "time_series" if is_time_series else "category_ranking",
            "time_period_format": "YYYY-MM" if is_date_format else None,
            "filter_criteria": {
                "year_filter": year_filter,
                "time_range": None
            },
            "sort_strategy": sort_strategy,
            "data_limit": data_limit,
            "chart_type_suggestion": chart_type
        }
    except Exception as e:
        logger.error(f"Fallback analysis failed: {e}")
        # Ultimate fallback
        return {
            "is_time_series": False,
            "data_type": "general",
            "time_period_format": None,
            "filter_criteria": {"year_filter": None, "time_range": None},
            "sort_strategy": "value_desc",
            "data_limit": 10,
            "chart_type_suggestion": "bar"
        }

def _apply_dynamic_analysis_strategy(rows: List[Dict], analysis: Dict[str, Any], user_input: str) -> List[Dict]:
    """Apply LLM's custom analysis strategy with complete flexibility"""
    try:
        processed_rows = rows.copy()
        logger.info(f"Applying dynamic strategy with analysis: {analysis}")
        
        # Let LLM's analysis guide the processing - be completely flexible
        # The analysis can contain any structure the LLM designed
        
        # Generic filtering logic that adapts to any filter structure
        if "filter" in analysis or "filtering" in analysis or "filters" in analysis:
            filter_config = analysis.get("filter") or analysis.get("filtering") or analysis.get("filters")
            processed_rows = _apply_flexible_filters(processed_rows, filter_config, user_input)
        
        # Generic sorting logic that adapts to any sort instruction
        if "sort" in analysis or "sorting" in analysis or "order" in analysis:
            sort_config = analysis.get("sort") or analysis.get("sorting") or analysis.get("order")
            processed_rows = _apply_flexible_sorting(processed_rows, sort_config, user_input)
        
        # Generic limiting logic that adapts to any limit instruction
        if "limit" in analysis or "top" in analysis or "max" in analysis or "count" in analysis:
            limit_config = analysis.get("limit") or analysis.get("top") or analysis.get("max") or analysis.get("count")
            processed_rows = _apply_flexible_limiting(processed_rows, limit_config, user_input)
        
        # Generic transformation logic for any custom processing
        if "transform" in analysis or "processing" in analysis or "format" in analysis:
            transform_config = analysis.get("transform") or analysis.get("processing") or analysis.get("format")
            processed_rows = _apply_flexible_transformations(processed_rows, transform_config, user_input)
        
        logger.info(f"Dynamic strategy applied, {len(processed_rows)} rows after processing")
        return processed_rows
        
    except Exception as e:
        logger.error(f"Error applying dynamic strategy: {e}")
        return rows  # Return original rows if processing fails


def _apply_standard_analysis_strategy(rows: List[Dict], analysis: Dict[str, Any]) -> List[Dict]:
    """Apply standard analysis strategy based on fallback detection"""
    processed_rows = rows.copy()
    
    # Apply filtering based on analysis
    filter_criteria = analysis.get("filter_criteria", {})
    year_filter = filter_criteria.get("year_filter")
    time_range = filter_criteria.get("time_range")
    
    if year_filter:
        processed_rows = [row for row in processed_rows 
                        if str(row.get("category", "")).startswith(year_filter)]
        logger.info(f"Applied year filter '{year_filter}': {len(processed_rows)} rows remaining")
    
    if time_range and analysis.get("is_time_series"):
        start_period = time_range.get("start")
        end_period = time_range.get("end")
        if start_period and end_period:
            processed_rows = [row for row in processed_rows 
                            if start_period <= str(row.get("category", "")) <= end_period]
            logger.info(f"Applied time range filter {start_period} to {end_period}: {len(processed_rows)} rows remaining")
    
    # Apply sorting based on analysis
    sort_strategy = analysis.get("sort_strategy", "value_desc")
    
    if sort_strategy == "chronological":
        def sort_time_key(row):
            category = str(row.get("category", ""))
            try:
                if re.match(r'^\d{4}-\d{2}$', category):  # YYYY-MM
                    year, month = category.split('-')
                    return int(year) * 100 + int(month)
                elif re.match(r'^\d{4}-\d{2}-\d{2}$', category):  # YYYY-MM-DD
                    return category  # String comparison works for ISO dates
                elif re.match(r'^\d{4}$', category):  # YYYY
                    return int(category)
                else:
                    return category
            except:
                return category
                
        processed_rows = sorted(processed_rows, key=sort_time_key)
        logger.info("Applied chronological sorting")
        
    elif sort_strategy == "value_desc":
        processed_rows = sorted(processed_rows, key=lambda x: x.get('value', 0), reverse=True)
        logger.info("Applied value descending sorting")
        
    elif sort_strategy == "value_asc":
        processed_rows = sorted(processed_rows, key=lambda x: x.get('value', 0))
        logger.info("Applied value ascending sorting")
        
    elif sort_strategy == "alphabetical":
        processed_rows = sorted(processed_rows, key=lambda x: str(x.get('category', '')))
        logger.info("Applied alphabetical sorting")
    
    # Apply data limiting based on analysis
    data_limit = analysis.get("data_limit")
    if data_limit and len(processed_rows) > data_limit:
        processed_rows = processed_rows[:data_limit]
        logger.info(f"Limited data to {data_limit} points")
    
    return processed_rows


def _apply_flexible_filters(rows: List[Dict], filter_config: Any, user_input: str) -> List[Dict]:
    """Apply flexible filtering based on LLM's filter configuration"""
    if not filter_config:
        return rows
    
    try:
        # Handle different filter config structures
        if isinstance(filter_config, dict):
            for filter_key, filter_value in filter_config.items():
                if filter_key.lower() in ['year', 'year_filter']:
                    rows = [row for row in rows if str(filter_value) in str(row.get("category", ""))]
                    logger.info(f"Applied flexible year filter '{filter_value}': {len(rows)} rows remaining")
                elif filter_key.lower() in ['range', 'time_range']:
                    if isinstance(filter_value, dict) and 'start' in filter_value and 'end' in filter_value:
                        start, end = filter_value['start'], filter_value['end']
                        rows = [row for row in rows if start <= str(row.get("category", "")) <= end]
                        logger.info(f"Applied flexible range filter {start}-{end}: {len(rows)} rows remaining")
        elif isinstance(filter_config, str):
            # Handle string-based filter instructions
            if any(year in filter_config for year in ['2025', '2024', '2023']):
                for year in ['2025', '2024', '2023']:
                    if year in filter_config:
                        rows = [row for row in rows if year in str(row.get("category", ""))]
                        logger.info(f"Applied string-based year filter '{year}': {len(rows)} rows remaining")
                        break
        
        return rows
        
    except Exception as e:
        logger.warning(f"Error applying flexible filters: {e}")
        return rows


def _apply_flexible_sorting(rows: List[Dict], sort_config: Any, user_input: str) -> List[Dict]:
    """Apply flexible sorting based on LLM's sort configuration"""
    if not sort_config:
        return rows
    
    try:
        if isinstance(sort_config, str):
            sort_config = sort_config.lower()
            if 'time' in sort_config or 'chronolog' in sort_config or 'date' in sort_config:
                # Apply chronological sorting
                def sort_time_key(row):
                    category = str(row.get("category", ""))
                    try:
                        if re.match(r'^\d{4}-\d{2}$', category):
                            year, month = category.split('-')
                            return int(year) * 100 + int(month)
                        elif re.match(r'^\d{4}$', category):
                            return int(category)
                        else:
                            return category
                    except:
                        return category
                rows = sorted(rows, key=sort_time_key)
                logger.info("Applied flexible chronological sorting")
            elif 'desc' in sort_config or 'high' in sort_config or 'large' in sort_config:
                rows = sorted(rows, key=lambda x: x.get('value', 0), reverse=True)
                logger.info("Applied flexible descending value sorting")
            elif 'asc' in sort_config or 'low' in sort_config or 'small' in sort_config:
                rows = sorted(rows, key=lambda x: x.get('value', 0))
                logger.info("Applied flexible ascending value sorting")
            elif 'alpha' in sort_config or 'name' in sort_config:
                rows = sorted(rows, key=lambda x: str(x.get('category', '')))
                logger.info("Applied flexible alphabetical sorting")
        
        elif isinstance(sort_config, dict):
            # Handle dict-based sort config
            if sort_config.get('by') == 'value' and sort_config.get('order') == 'desc':
                rows = sorted(rows, key=lambda x: x.get('value', 0), reverse=True)
            elif sort_config.get('by') == 'value' and sort_config.get('order') == 'asc':
                rows = sorted(rows, key=lambda x: x.get('value', 0))
            elif sort_config.get('by') == 'time' or sort_config.get('by') == 'chronological':
                def sort_time_key(row):
                    category = str(row.get("category", ""))
                    try:
                        if re.match(r'^\d{4}-\d{2}$', category):
                            year, month = category.split('-')
                            return int(year) * 100 + int(month)
                        elif re.match(r'^\d{4}$', category):
                            return int(category)
                        else:
                            return category
                    except:
                        return category
                rows = sorted(rows, key=sort_time_key)
        
        return rows
        
    except Exception as e:
        logger.warning(f"Error applying flexible sorting: {e}")
        return rows


def _apply_flexible_limiting(rows: List[Dict], limit_config: Any, user_input: str) -> List[Dict]:
    """Apply flexible limiting based on LLM's limit configuration"""
    if not limit_config:
        return rows
    
    try:
        if isinstance(limit_config, int):
            return rows[:limit_config]
        elif isinstance(limit_config, str):
            # Extract number from string
            numbers = re.findall(r'\d+', limit_config)
            if numbers:
                limit = int(numbers[0])
                logger.info(f"Applied flexible limit: {limit}")
                return rows[:limit]
        elif isinstance(limit_config, dict):
            if 'count' in limit_config:
                limit = int(limit_config['count'])
                return rows[:limit]
        
        return rows
        
    except Exception as e:
        logger.warning(f"Error applying flexible limiting: {e}")
        return rows


def _apply_flexible_transformations(rows: List[Dict], transform_config: Any, user_input: str) -> List[Dict]:
    """Apply flexible transformations based on LLM's transformation configuration"""
    if not transform_config:
        return rows
    
    try:
        # This can be extended to handle any custom transformations the LLM suggests
        # For now, just log and return as-is
        logger.info(f"Transformation config received: {transform_config}")
        return rows
        
    except Exception as e:
        logger.warning(f"Error applying flexible transformations: {e}")
        return rows 