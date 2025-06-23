from .db import fetch_sales_for_day  # Updated to use SQLite-based data fetching
from datetime import datetime
from langchain_openai import ChatOpenAI
import os
import traceback # Added for detailed error logging
from dotenv import load_dotenv
load_dotenv()

# Get API Key from environment variables or config file
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
LLM_MODEL_NAME = os.getenv("OPENAI_MODEL")

llm = None
if OPENAI_API_KEY and not OPENAI_API_KEY.startswith(("123456", "local_mode")):
    # Initialize LLM, support OpenRouter
    try:
        llm_kwargs = {
            "model_name": LLM_MODEL_NAME,
            "temperature": 0.3,
            "openai_api_key": OPENAI_API_KEY
        }
        
        # If there's a custom base_url (OpenRouter), add to configuration
        if OPENAI_BASE_URL:
            llm_kwargs["openai_api_base"] = OPENAI_BASE_URL
            
        llm = ChatOpenAI(**llm_kwargs)
        print(f"[Report] LLM initialized successfully - Model: {LLM_MODEL_NAME}")
        if OPENAI_BASE_URL:
            print(f"[Report] Using custom API endpoint: {OPENAI_BASE_URL}")
    except Exception as e:
        print(f"[Report] LLM initialization failed: {e}")
        llm = None
else:
    import logging
    logger = logging.getLogger(__name__)
    logger.error("[Report] LLM not properly configured. Report generation will fail.")
    llm = None

async def generate_daily_sales_summary_report() -> tuple[str, dict]:
    """Generates a summary and data for the daily sales report using SQLite database."""
    print("[Report-SQLite] Generating daily sales report...")
    
    # 1. Fetch data for today
    today = datetime.now()
    sales_details = await fetch_sales_for_day(today)  # From db.py, now using SQLite
    
    if not sales_details:
        return f"Today ({today.strftime('%Y-%m-%d')}) has no sales data.", {}

    # 2. Process data and generate summary
    total_sales_amount = sum(item['total_amount'] for item in sales_details)
    total_quantity = sum(item['quantity_sold'] for item in sales_details)
    
    # Sort by quantity_sold to find top product, ensure units_sold is present and integer
    for item in sales_details:
        item['units_sold'] = int(item.get('quantity_sold', 0))
        
    top_product = max(sales_details, key=lambda x: x['units_sold']) if sales_details else None
    top_revenue_product = max(sales_details, key=lambda x: x['total_amount']) if sales_details else None

    # Basic summary
    basic_summary = f"Today ({today.strftime('%Y-%m-%d')}) total sales: ${total_sales_amount:.2f}, total quantity: {total_quantity} units."
    if top_product and top_product['units_sold'] > 0:
        basic_summary += f" Best selling product: {top_product['product_name']} (sold {top_product['units_sold']} units)."
    if top_revenue_product and top_revenue_product != top_product:
        basic_summary += f" Highest revenue product: {top_revenue_product['product_name']} (${top_revenue_product['total_amount']:.2f})."

    # Enhanced summary using LLM if available
    summary = basic_summary
    if llm:
        try:
            # Create detailed sales breakdown
            product_summary_list = []
            for item in sales_details:
                product_summary_list.append({
                    "name": item['product_name'],
                    "quantity": item['quantity_sold'],
                    "revenue": item['total_amount']
                })
            
            prompt = f"""
Generate a professional daily sales report summary for {today.strftime('%Y-%m-%d')} based on the following sales data:

Total Sales: ${total_sales_amount:.2f}
Total Quantity: {total_quantity} units
Products Sold: {len(sales_details)} types

Product Sales Details:
{product_summary_list}

Please generate a concise but informative sales report summary including:
1. Overall sales performance evaluation
2. Key sales highlights
3. Product performance analysis
4. Brief business insights

Keep it professional, concise, and suitable for management review.
"""
            
            llm_response = await llm.ainvoke(prompt)
            summary = llm_response.content
            print(f"[Report-SQLite] Enhanced summary generated using LLM")
            
        except Exception as e:
            print(f"[Report-SQLite] LLM summarization error: {e}")
            summary = basic_summary  # Fallback to basic summary

    report_data = {
        "report_date": today.strftime('%Y-%m-%d'),
        "total_sales": total_sales_amount,
        "total_quantity": total_quantity,
        "products_sold": len(sales_details),
        "top_product_name": top_product['product_name'] if top_product and top_product['units_sold'] > 0 else "N/A",
        "top_product_units_sold": top_product['units_sold'] if top_product and top_product['units_sold'] > 0 else 0,
        "top_revenue_product": top_revenue_product['product_name'] if top_revenue_product else "N/A",
        "top_revenue_amount": top_revenue_product['total_amount'] if top_revenue_product else 0,
        "detailed_sales": sales_details,  # Already contains product_name from database
        "performance_metrics": {
            "average_order_value": total_sales_amount / len(sales_details) if sales_details else 0,
            "average_quantity_per_product": total_quantity / len(sales_details) if sales_details else 0
        }
    }
    
    print(f"[Report-SQLite] Generated enhanced report with {len(sales_details)} sales records")
    return summary, report_data

async def generate_sales_daily_report() -> dict:
    """
    Generate daily sales report - New API endpoint function
    Use LLM combined with database data to generate formatted text summary and sales data overview
    """
    print("[Report-SQLite] Generating sales daily report for API...")
    
    today = datetime.now()
    sales_details = await fetch_sales_for_day(today)
    
    if not sales_details:
        return {
            "success": False,
            "message": f"Today ({today.strftime('%Y-%m-%d')}) has no sales data",
            "data": None,
            "summary": f"Today ({today.strftime('%Y-%m-%d')}) has no sales records.",
            "report_date": today.strftime('%Y-%m-%d')
        }

    # Calculate key metrics
    total_sales = sum(item['total_amount'] for item in sales_details)
    total_quantity = sum(item['quantity_sold'] for item in sales_details)
    unique_products = len(set(item['product_id'] for item in sales_details))
    
    # Find top performers
    product_sales_dict = {}
    for item in sales_details:
        pid = item['product_id']
        if pid not in product_sales_dict:
            product_sales_dict[pid] = {
                'name': item['product_name'],
                'total_revenue': 0,
                'total_quantity': 0
            }
        product_sales_dict[pid]['total_revenue'] += item['total_amount']
        product_sales_dict[pid]['total_quantity'] += item['quantity_sold']
    
    # Sort by revenue and quantity
    top_by_revenue = sorted(product_sales_dict.values(), key=lambda x: x['total_revenue'], reverse=True)[:5]
    top_by_quantity = sorted(product_sales_dict.values(), key=lambda x: x['total_quantity'], reverse=True)[:5]
    
    # Transform to match ProductSalesInfo model
    top_products_by_revenue_list = [
        {"name": p['name'], "total_revenue": p['total_revenue'], "total_quantity": p['total_quantity']}
        for p in top_by_revenue
    ]
    top_products_by_quantity_list = [
        {"name": p['name'], "total_revenue": p['total_revenue'], "total_quantity": p['total_quantity']}
        for p in top_by_quantity
    ]
    
    # Generate LLM summary if available
    summary_text = f"Today ({today.strftime('%Y-%m-%d')}) total sales ${total_sales:.2f}, sold {unique_products} product types, total {total_quantity} units."
    
    if llm:
        try:
            prompt = f"""
As a sales analyst for the system, generate a professional report based on today's ({today.strftime('%Y-%m-%d')}) sales data:

📊 Sales Overview:
- Total Sales: ${total_sales:.2f}
- Total Quantity: {total_quantity} units
- Product Types Sold: {unique_products} types
- Average Order Value: ${total_sales/len(sales_details) if sales_details else 0:.2f}

🏆 Revenue Rankings:
{chr(10).join([f"{i+1}. {p['name']}: ${p['total_revenue']:.2f}" for i, p in enumerate(top_by_revenue)])}

📦 Quantity Rankings:
{chr(10).join([f"{i+1}. {p['name']}: {p['total_quantity']} units" for i, p in enumerate(top_by_quantity)])}

Please generate a concise and professional daily sales report including:
1. Overall performance evaluation
2. Key product analysis
3. Key data insights
4. Brief suggestions

Language style: professional, objective, data-driven.
"""
            llm_response = await llm.ainvoke(prompt)
            summary_text = llm_response.content
            
        except Exception as e:
            error_str = str(e)
            print(f"[Report-SQLite] LLM report generation error: {e}")
            # Check if it's a quota error
            if "429" in error_str or "quota" in error_str.lower():
                print("[Report-SQLite] API quota insufficient, use basic report mode")
                # Generate basic version of professional report
                summary_text = f"""�� Daily Sales Report - {today.strftime('%Y-%m-%d')}

💰 Sales Overview:
- Total Sales: ${total_sales:.2f}
- Total Quantity: {total_quantity} units
- Product Types: {unique_products} types
- Average Order Value: ${total_sales/len(sales_details) if sales_details else 0:.2f}

🏆 Performance Highlights:
- Top Revenue: {top_by_revenue[0]['name'] if top_by_revenue else 'N/A'}
- Top Quantity: {top_by_quantity[0]['name'] if top_by_quantity else 'N/A'}

📈 Data Insights:
Based on database analysis, today's sales performance {"normal" if total_sales > 1000 else "needs attention"}, suggest continuous monitoring of sales trends.
(Note: Based on database generation, AI enhanced analysis temporarily unavailable)"""
            else:
                # Other errors, use basic summary
                summary_text = f"Today ({today.strftime('%Y-%m-%d')}) total sales ${total_sales:.2f}, sold {unique_products} product types, total {total_quantity} units. Report generation encountered technical issues, suggest checking detailed data."
    
    # Create chart data for top products by revenue
    chart_data_dict = None
    if top_by_revenue:
        chart_data_dict = {
            "type": "horizontalBar",
            "labels": [p['name'] for p in top_by_revenue],
            "datasets": [{
                "label": "Sales ($)",
                "data": [p['total_revenue'] for p in top_by_revenue],
                "backgroundColor": [
                    "rgba(54, 162, 235, 0.8)",
                    "rgba(255, 99, 132, 0.8)",
                    "rgba(75, 192, 192, 0.8)",
                    "rgba(153, 102, 255, 0.8)",
                    "rgba(255, 159, 64, 0.8)"
                ],
                "borderWidth": 1
            }]
        }

    return {
        "success": True,
        "summary": summary_text,
        "report_date": today.strftime('%Y-%m-%d'),
        "data": {
            "total_sales": total_sales,
            "total_quantity": total_quantity,
            "unique_products": unique_products,
            "average_order_value": total_sales / len(sales_details) if sales_details else 0,
            "top_products_by_revenue": top_products_by_revenue_list,
            "top_products_by_quantity": top_products_by_quantity_list,
            "detailed_sales": sales_details
        },
        "chart_data": chart_data_dict
    }

# Placeholder for other report types if needed in the future
async def generate_inventory_status_report():
    # TODO: Implement inventory report logic using SQLite data
    return "Inventory status report not yet implemented for SQLite.", {}

async def generate_weekly_sales_report():
    # TODO: Implement weekly sales report logic using SQLite data
    return "Weekly sales report not yet implemented for SQLite.", {}, None 