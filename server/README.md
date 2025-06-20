# Smart  Agent

A Smart  Assistant powered by FastAPI, LangChain, and SQLite with advanced natural language processing capabilities.

## ✨ New Features (v0.2.0)

- **Enhanced Natural Language Sales Queries**: Advanced query processing with Chart.js compatible data output
- **Intelligent Inventory Management**: Natural language inventory queries with automatic threshold detection
- **AI-Powered Report Generation**: LLM-generated professional sales reports with insights and recommendations
- **Chart Data Support**: All endpoints now provide data optimized for frontend chart libraries
- **Unified Query Interface**: Single entry point for both sales and inventory queries
- **Backward Compatibility**: All original API endpoints remain functional

## Features

- **Natural Language Sales Queries**: Ask questions like "本月销售额多少？" or "过去7天每天的销售额是多少？"
- **Inventory Management**: Check low stock levels and get AI-powered restocking suggestions
- **Daily Sales Reports**: Automated reports with sales summaries and insights
- **SQLite Database**: Reliable data storage with automatic CSV import functionality
- **REST API**: Clean RESTful endpoints for easy integration
- **Chart Data Generation**: Ready-to-use data for Chart.js, D3.js, and other visualization libraries

## Project Structure

```
smart_agent/
├── backend/
│   ├── main.py          # FastAPI application with enhanced endpoints
│   ├── agent.py         # LangChain AI agent logic with unified query interface
│   ├── db.py            # SQLite database operations
│   ├── models.py        # Enhanced Pydantic data models
│   ├── report.py        # Advanced report generation with LLM integration
│   └── data/
│       ├── products_data.csv      # Product catalog (100 items)
│       ├── inventory_data.csv     # Stock levels
│       ├── sales_data.csv         # Sales transactions (300 records)
│       └── smart.db          # SQLite database (auto-generated)
├── requirements.txt     # Python dependencies
├── init_database.py     # Database initialization script
├── test_db.py          # Simple database test script
├── test_api.py         # Comprehensive API testing script
└── README.md           # This file
```

## Prerequisites

- **Python 3.8+**: Make sure Python is installed and accessible via `python` command
- **pip**: Python package installer
- **SQLite**: Usually included with Python

## Setup Instructions

### 1. Verify Python Installation

```bash
python --version
# Should show Python 3.8 or higher
```

If `python` command is not found, try:
```bash
python3 --version
# Use python3 instead of python in all subsequent commands
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment Configuration

Create a `.env` file in the project root:

```bash
OPENAI_API_KEY=your_openai_api_key_here
```

> **Note**: The system will work without OpenAI API key, but AI-powered features will be limited.

### 4. Initialize Database

Run the database initialization script:

```bash
python init_database.py
```

This script will:
- Create the SQLite database schema
- Import data from CSV files in `data/`
- Verify the import was successful

### 5. Test Database (Optional)

Run the simple database test:

```bash
python test_db.py
```

This will verify that the database was created correctly and contains the expected data.

### 6. Start the Server

```bash
uvicorn main:app --reload
```

The API will be available at: `http://localhost:8000`

You can visit `http://localhost:8000/docs` for the interactive API documentation.

### 7. Test API Endpoints (Optional)

Run the comprehensive API test suite:

```bash
python test_api.py
```

This will test all new and legacy endpoints to ensure they're working correctly.

## 🚀 New API Endpoints (v0.2.0)

### Enhanced Sales Queries
- **POST** `/api/v1/sales_query` - Advanced natural language sales queries with chart data
  ```json
  {
    "query": "过去7天每天的销售额是多少？"
  }
  ```
  **Response includes:**
  - Natural language answer
  - Chart.js compatible data
  - Query metadata
  - Error handling

### Smart Inventory Management
- **POST** `/api/v1/inventory_check` - Natural language inventory queries
  ```json
  {
    "query": "当前库存低于50的产品有哪些？",
    "threshold": 50
  }
  ```
  **Features:**
  - Automatic threshold detection from query
  - AI-generated recommendations
  - Chart visualization data
  - Product status classification

### AI-Powered Reports
- **GET** `/api/v1/reports/sales_daily` - LLM-generated daily sales reports
  **Includes:**
  - Professional sales analysis
  - Performance insights
  - Business recommendations
  - Visualization-ready data

### System Information
- **GET** `/api/v1/info` - API capabilities and version information

## Legacy API Endpoints (Backward Compatible)

### Sales Queries
- **POST** `/api/v1/sales/query` - Natural language sales queries
  ```json
  {
    "query": "本月销售额多少？"
  }
  ```

### Inventory Management
- **GET** `/api/v1/inventory/check` - Check low stock items

### Reports
- **GET** `/api/v1/reports/daily_sales` - Generate daily sales report

### Health Check
- **GET** `/ping` - Check if the API is running

## Database Schema

### Products Table
- `product_id` (TEXT PRIMARY KEY)
- `product_name` (TEXT)
- `category` (TEXT) 
- `unit_price` (REAL)

### Inventory Table
- `product_id` (TEXT PRIMARY KEY)
- `stock_level` (INTEGER)
- `last_updated` (DATETIME)

### Sales Table
- `sale_id` (TEXT PRIMARY KEY)
- `product_id` (TEXT)
- `product_name` (TEXT)
- `quantity_sold` (INTEGER)
- `price_per_unit` (REAL)
- `total_amount` (REAL)
- `sale_date` (DATETIME)

## Sample Data

The system comes with comprehensive sample data:

- **100 Products**: Diverse catalog including electronics, office supplies, accessories, etc.
- **300 Sales Records**: Realistic sales transactions from October 1-29, 2023
- **100 Inventory Records**: Stock levels ranging from 7-500 units

## 🎯 Supported Query Types

### Sales Queries
- `"本月销售额多少？"` - Current month total sales
- `"过去7天每天的销售额是多少？"` - Daily sales for last 7 days
- `"today's sales performance"` - English queries are also supported
- `"哪个产品卖得最好？"` - Best-selling product queries

### Inventory Queries
- `"当前库存低于50的产品有哪些？"` - Low stock with specific threshold
- `"库存紧急的产品"` - Critical inventory levels
- `"需要补货的产品列表"` - Restocking recommendations

## 📊 Chart Data Format

All endpoints that support visualization return Chart.js compatible data:

```json
{
  "chart_data": {
    "type": "line",
    "labels": ["2023-10-23", "2023-10-24", "2023-10-25"],
    "datasets": [{
      "label": "每日销售额 (¥)",
      "data": [1250.50, 2100.75, 1800.25],
      "borderColor": "rgba(75, 192, 192, 1)",
      "backgroundColor": "rgba(75, 192, 192, 0.2)"
    }]
  }
}
```

**Supported Chart Types:**
- `line` - Time series data (daily sales, trends)
- `bar` - Category comparisons (product performance)
- `horizontalBar` - Rankings (top products)
- `doughnut` - Single value representation (total sales)

## Database Management

### Reinitialize Database
To reset the database with fresh data:

```bash
python init_database.py
```

### Manual Database Operations
The database file is located at `data/smart.db`. You can use any SQLite client to inspect or modify the data.

### Database Backup
To backup your database:

```bash
# Copy the database file
cp data/smart.db backup_smart.db
```

## Development

### Adding New Query Types
To add support for new natural language queries, modify the `get_answer_from()` function in `agent.py`.

### Extending the Schema
To add new tables or modify existing ones:
1. Update the schema in `initialize_database_schema()` in `db.py`
2. Add corresponding CSV files in `data/`
3. Update the import logic in `import_csv_data_to_db()`

### Adding New Report Types
Create new functions in `report.py` and add corresponding endpoints in `main.py`.

## Testing

### Database Testing
```bash
python test_db.py
```

### API Testing
```bash
python test_api.py
```

### Manual Testing
1. **Test Sales Query**:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/sales_query" \
        -H "Content-Type: application/json" \
        -d '{"query": "本月销售额多少？"}'
   ```

2. **Test Inventory Check**:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/inventory_check" \
        -H "Content-Type: application/json" \
        -d '{"query": "库存低于30的产品", "threshold": 30}'
   ```

3. **Test Sales Report**:
   ```bash
   curl "http://localhost:8000/api/v1/reports/sales_daily"
   ```

## Troubleshooting

### Common Issues

1. **Python Command Not Found**
   - Ensure Python 3.8+ is installed
   - Try using `python3` instead of `python`
   - On Windows, make sure Python is added to PATH

2. **Database Initialization Fails**
   - Check that CSV files exist in `backend/data/`
   - Ensure proper file permissions
   - Run `python init_database.py` to see detailed error messages
   - Try running `python test_db.py` to test database connectivity

3. **API Starts but Queries Fail**
   - Verify database contains data by running `python test_db.py`
   - Check the FastAPI startup logs for database initialization messages
   - Ensure OpenAI API key is valid (if using LLM features)
   - Run `python test_api.py` to test all endpoints

4. **Import Errors**
   - Check that you're running commands from the project root
   - Verify Python path includes the backend directory
   - Install dependencies: `pip install -r requirements.txt`

5. **Permission Errors**
   - On Linux/Mac, you might need to use `sudo` or adjust file permissions
   - Ensure the `backend/data/` directory is writable

6. **Port Already in Use**
   - If port 8000 is busy, start the server on a different port:
     ```bash
     uvicorn backend.main:app --reload --port 8001
     ```

7. **Chart Data Not Displaying**
   - Ensure your frontend properly handles the `chart_data` field
   - Check that the chart type is supported by your visualization library
   - Verify data format matches Chart.js requirements

### Logs

The application provides detailed logging with prefixes:
- `[DB-SQLite]` - Database operations
- `[Agent-SQLite]` - AI agent activities  
- `[Report-SQLite]` - Report generation

## Performance Notes

- **Database Queries**: SQLite provides excellent performance for typical  datasets
- **LLM Calls**: OpenAI API calls may take 1-3 seconds; consider caching for frequently asked questions
- **Chart Data**: Limited to top 10 items by default to prevent UI clutter
- **Concurrent Requests**: FastAPI handles multiple requests efficiently

## Alternative Setups

### Using Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python init_database.py
uvicorn backend.main:app --reload
```

### Using Docker (Optional)

Create a `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN python init_database.py

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## License

This project is for educational and demonstration purposes.

## Dependencies

- **FastAPI**: Web framework
- **LangChain**: AI agent framework
- **OpenAI**: Language model (optional)
- **SQLite**: Database
- **Pydantic**: Data validation
- **python-dotenv**: Environment management
- **requests**: For API testing script 