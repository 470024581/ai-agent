from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Dict
import os
from pathlib import Path

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

# Configure static files for frontend
static_dir = Path(__file__).parent.parent.parent / "client" / "dist"
if static_dir.exists():
    # Mount static files (CSS, JS, images, etc.)
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")
    
    # Serve the main HTML file for all frontend routes
    @app.get("/", tags=["Frontend"])
    async def serve_frontend():
        """Serve the main frontend application"""
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "Frontend not found. Please build the frontend first."}
    
    @app.get("/{path:path}", tags=["Frontend"])
    async def serve_frontend_routes(path: str):
        """Serve frontend routes and static files"""
        # Check if it's a static file request
        file_path = static_dir / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        
        # For all other routes, serve the index.html (SPA routing)
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        
        return {"message": f"File not found: {path}"}

# Include the router from routes.py
app.include_router(routes.router) # This line registers all routes from routes.py

@app.on_event("startup")
async def startup_event():
    """Initialize application state (e.g., DB schema, API keys) on startup."""
    print("Application starting up...")
    initialize_app_state()
    
    # Check if frontend is available
    frontend_available = static_dir.exists()
    print(f"Frontend available: {frontend_available}")
    if frontend_available:
        print(f"Frontend directory: {static_dir}")
        print("Frontend will be served at http://localhost:8000/")
    else:
        print("Frontend not found. Only API will be available.")
    
    print("Application startup completed.")

@app.get("/ping", tags=["Health Check"])
async def ping():
    """
    A simple ping endpoint to check if the API is running.
    """
    return {"status": "ok", "message": "pong!", "version": "0.5.0"}

@app.get("/health", tags=["Health Check"])
async def health():
    """
    Health check endpoint for Docker and monitoring.
    """
    frontend_available = static_dir.exists()
    return {
        "status": "healthy",
        "version": "0.5.0",
        "components": {
            "api": "running",
            "frontend": "available" if frontend_available else "not_found"
        }
    }

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
    frontend_available = static_dir.exists()
    return {
        "name": "Smart AI Assistant API",
        "version": "0.5.0", 
        "features": {
            "1": "Intelligent Q&A (Natural language queries)",
            "2": "Data Source Management (Multiple data sources)",
            "3": "Multi-format support (CSV, PDF, DOCX, Excel)",
            "4": "AI-powered analysis",
            "5": "Web Frontend" if frontend_available else "API Only"
        },
        "endpoints": [
            "GET / (Frontend)" if frontend_available else None,
            "POST /api/v1/query",
            "GET /api/v1/datasources",
            "POST /api/v1/datasources",
            "POST /api/v1/datasources/{id}/files/upload"
        ],
        "frontend_available": frontend_available,
        "database": "SQLite with file processing",
        "ai_powered": True
    }

# Example of how to run directly
if __name__ == "__main__":
    import uvicorn
    print("Starting FastAPI server. For production, use: uvicorn main:app --reload")
    uvicorn.run(app, host="0.0.0.0", port=8000) 