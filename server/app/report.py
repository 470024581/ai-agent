from .db import fetch_sales_for_day  # Updated to use SQLite-based data fetching
from datetime import datetime
from langchain_openai import ChatOpenAI
import os
import traceback # Added for detailed error logging
from dotenv import load_dotenv
load_dotenv()

# 从环境变量或配置文件获取API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
LLM_MODEL_NAME = os.getenv("OPENAI_MODEL")

llm = None
if OPENAI_API_KEY and not OPENAI_API_KEY.startswith(("123456", "local_mode")):
    # 初始化LLM，支持OpenRouter
    try:
        llm_kwargs = {
            "model_name": LLM_MODEL_NAME,
            "temperature": 0.3,
            "openai_api_key": OPENAI_API_KEY
        }
        
        # 如果有自定义base_url（OpenRouter），添加到配置中
        if OPENAI_BASE_URL:
            llm_kwargs["openai_api_base"] = OPENAI_BASE_URL
            
        llm = ChatOpenAI(**llm_kwargs)
        print(f"[Report] LLM 初始化成功 - 模型: {LLM_MODEL_NAME}")
        if OPENAI_BASE_URL:
            print(f"[Report] 使用自定义API端点: {OPENAI_BASE_URL}")
    except Exception as e:
        print(f"[Report] LLM 初始化失败: {e}")
        llm = None
else:
    print("[Report] 使用模拟API Key或无Key，LLM功能将被模拟或不可用")

async def generate_daily_sales_summary_report() -> tuple[str, dict]:
    """Generates a summary and data for the daily sales report using SQLite database."""
    print("[Report-SQLite] Generating daily sales report...")
    
    # 1. Fetch data for today
    today = datetime.now()
    sales_details = await fetch_sales_for_day(today)  # From db.py, now using SQLite
    
    if not sales_details:
        return f"今日 ({today.strftime('%Y-%m-%d')}) 暂无销售数据。", {}

    # 2. Process data and generate summary
    total_sales_amount = sum(item['total_amount'] for item in sales_details)
    total_quantity = sum(item['quantity_sold'] for item in sales_details)
    
    # Sort by quantity_sold to find top product, ensure units_sold is present and integer
    for item in sales_details:
        item['units_sold'] = int(item.get('quantity_sold', 0))
        
    top_product = max(sales_details, key=lambda x: x['units_sold']) if sales_details else None
    top_revenue_product = max(sales_details, key=lambda x: x['total_amount']) if sales_details else None

    # Basic summary
    basic_summary = f"今日 ({today.strftime('%Y-%m-%d')}) 销售总额为 ¥{total_sales_amount:.2f}，总销量 {total_quantity} 件。"
    if top_product and top_product['units_sold'] > 0:
        basic_summary += f" 畅销产品为 {top_product['product_name']} (售出 {top_product['units_sold']} 件)。"
    if top_revenue_product and top_revenue_product != top_product:
        basic_summary += f" 收入最高产品为 {top_revenue_product['product_name']} (¥{top_revenue_product['total_amount']:.2f})。"

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
基于以下销售数据为 {today.strftime('%Y年%m月%d日')} 生成一份专业的每日销售报告摘要：

总销售额: ¥{total_sales_amount:.2f}
总销量: {total_quantity} 件
销售产品数: {len(sales_details)} 种

产品销售详情:
{product_summary_list}

请生成一份简洁但信息丰富的销售报告摘要，包括：
1. 整体销售表现评价
2. 主要销售亮点
3. 产品表现分析
4. 简短的业务洞察

保持专业、简洁，适合管理层阅读。
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
    生成每日销售报告 - 新的API端点函数
    使用LLM结合数据库数据生成格式化的文本摘要和销售数据概览
    """
    print("[Report-SQLite] Generating sales daily report for API...")
    
    today = datetime.now()
    sales_details = await fetch_sales_for_day(today)
    
    if not sales_details:
        return {
            "success": False,
            "message": f"今日 ({today.strftime('%Y-%m-%d')}) 暂无销售数据",
            "data": None,
            "summary": f"今日 ({today.strftime('%Y-%m-%d')}) 暂无销售记录。",
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
    summary_text = f"今日 ({today.strftime('%Y-%m-%d')}) 销售总额 ¥{total_sales:.2f}，销售 {unique_products} 种产品，总计 {total_quantity} 件。"
    
    if llm:
        try:
            prompt = f"""
作为系统的销售分析师，基于以下今日({today.strftime('%Y年%m月%d日')})销售数据生成专业报告：

📊 销售概览:
- 总销售额: ¥{total_sales:.2f}
- 总销量: {total_quantity} 件
- 销售产品种类: {unique_products} 种
- 平均客单价: ¥{total_sales/len(sales_details) if sales_details else 0:.2f}

🏆 收入排行榜:
{chr(10).join([f"{i+1}. {p['name']}: ¥{p['total_revenue']:.2f}" for i, p in enumerate(top_by_revenue)])}

📦 销量排行榜:
{chr(10).join([f"{i+1}. {p['name']}: {p['total_quantity']} 件" for i, p in enumerate(top_by_quantity)])}

请生成一份简洁专业的销售日报，包括：
1. 整体表现评价
2. 亮点产品分析
3. 关键数据洞察
4. 简短建议

语言风格：专业、客观、数据驱动。
"""
            llm_response = await llm.ainvoke(prompt)
            summary_text = llm_response.content
            
        except Exception as e:
            error_str = str(e)
            print(f"[Report-SQLite] LLM report generation error: {e}")
            # 检查是否是配额错误
            if "429" in error_str or "quota" in error_str.lower():
                print("[Report-SQLite] API配额不足，使用基础报告模式")
                # 生成基础版本的专业报告
                summary_text = f"""📊 每日销售报告 - {today.strftime('%Y年%m月%d日')}

💰 销售概览:
- 总销售额: ¥{total_sales:.2f}
- 总销量: {total_quantity} 件
- 产品种类: {unique_products} 种
- 平均客单价: ¥{total_sales/len(sales_details) if sales_details else 0:.2f}

🏆 业绩亮点:
- 收入榜首: {top_by_revenue[0]['name'] if top_by_revenue else 'N/A'}
- 销量冠军: {top_by_quantity[0]['name'] if top_by_quantity else 'N/A'}

📈 数据洞察:
基于数据库记录分析，今日销售表现{"正常" if total_sales > 1000 else "需关注"}，建议持续监控销售趋势。
（注：基于数据库生成，AI增强分析暂时不可用）"""
            else:
                # 其他错误，使用基础摘要
                summary_text = f"今日 ({today.strftime('%Y-%m-%d')}) 销售总额 ¥{total_sales:.2f}，销售 {unique_products} 种产品，总计 {total_quantity} 件。报告生成时遇到技术问题，建议查看详细数据。"
    
    # Create chart data for top products by revenue
    chart_data_dict = None
    if top_by_revenue:
        chart_data_dict = {
            "type": "horizontalBar",
            "labels": [p['name'] for p in top_by_revenue],
            "datasets": [{
                "label": "销售额 (¥)",
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