import asyncio
import sys
import os

# Add current directory to path
sys.path.append('.')

from app.agent import get_answer_from

async def test_query():
    print("=== Testing Query Functionality ===")
    
    query = "What is the average price of each product category?"
    print(f"Query: {query}")
    
    try:
        result = await get_answer_from(query)
        
        print(f"Success: {result.get('success')}")
        
        if result.get('success'):
            print(f"Answer: {result.get('answer')}")
            data = result.get('data', {})
            print(f"Columns: {data.get('columns', [])}")
            rows = data.get('rows', [])
            print(f"Number of rows: {len(rows)}")
            print("First 3 rows:")
            for i, row in enumerate(rows[:3]):
                print(f"  Row {i+1}: {row}")
        else:
            print(f"Error: {result.get('error')}")
            
    except Exception as e:
        print(f"Exception occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_query()) 