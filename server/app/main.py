from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict

# Import Pydantic models from .models
from .models import (
    QueryRequest,
    QueryResponse
)

# Import initialization function
from .agent import initialize_app_state

# Import agent functions (simplified)
from .agent import (
    get_answer_from
)

from . import routes # Import the routes module

app = FastAPI(title="Smart AI Assistant API", version="0.5.0")

# CORS Middleware Configuration
origins = [
    "http://localhost:3000",  # Allow your React frontend origin
    "http://localhost:8000",  # Allow local API docs
    "*"  # Allow all origins for development
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the router from routes.py
app.include_router(routes.router) # This line registers all routes from routes.py

@app.on_event("startup")
async def startup_event():
    """Initialize application state (e.g., DB schema, API keys) on startup."""
    print("Application starting up...")
    initialize_app_state()
    print("Application startup completed.")

@app.get("/ping", tags=["Health Check"])
async def ping():
    """
    A simple ping endpoint to check if the API is running.
    """
    return {"status": "ok", "message": "pong!", "version": "0.5.0"}

# Core API endpoints - Intelligent Q&A only

@app.post("/api/v1/query", response_model=QueryResponse, tags=["Intelligent Q&A"])
async def intelligent_query(request: QueryRequest):
    """
    Intelligent Q&A API - Natural language queries
    
    Supports:
    - Sales data queries
    - Inventory status queries  
    - Data source queries (SQL/RAG)
    - Natural language processing
    """
    try:
        result = await get_answer_from(request.query, "general")
        return QueryResponse(
            answer=result.get("answer", "No answer generated"),
            data_for_chart=result.get("chart_data"),
            success=result.get("success", True),
            data=result.get("data", {}),
            suggestions=result.get("suggestions", [])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")

# API information endpoint
@app.get("/api/v1/info", tags=["System Info"])
async def api_info():
    """
    Get API system information and feature overview.
    """
    return {
        "name": "Smart AI Assistant API",
        "version": "0.5.0", 
        "features": {
            "1": "Intelligent Q&A (Natural language queries)",
            "2": "Data Source Management (Multiple data sources)",
            "3": "Multi-format support (CSV, PDF, DOCX, Excel)",
            "4": "AI-powered analysis"
        },
        "endpoints": [
            "POST /api/v1/query",
            "GET /api/v1/datasources",
            "POST /api/v1/datasources",
            "POST /api/v1/datasources/{id}/files/upload"
        ],
        "database": "SQLite with file processing",
        "ai_powered": True
    }

# Example of how to run directly
if __name__ == "__main__":
    import uvicorn
    print("Starting FastAPI server. For production, use: uvicorn main:app --reload")
    uvicorn.run(app, host="0.0.0.0", port=8000) 