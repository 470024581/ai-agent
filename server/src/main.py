"""
Smart AI Assistant - Main Application Entry Point

This is the main entry point for the LangChain-based intelligent data analysis system.
Following LangChain best practices for project structure and organization.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Dict
import os
from pathlib import Path
import logging
import sys
from .config.config import config
from fastapi import Request
import time

# Import from the restructured modules
from .agents.intelligent_agent import initialize_app_state
from .api.routes import router

# ===== CRITICAL FIX: Configure logging in worker process =====
# Uvicorn reload spawns worker processes that don't inherit log_config from parent
# We must configure logging HERE (in the application module) to ensure worker processes have proper logging

# 1. Clear any existing handlers to avoid duplicates
root_logger = logging.getLogger()
root_logger.handlers.clear()

# 2. Add a single console handler to root
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
console_handler.setFormatter(logging.Formatter(config.LOG_FORMAT))
root_logger.addHandler(console_handler)
root_logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))

# 3. Configure uvicorn loggers to propagate (use root's handler)
for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
    logger_obj = logging.getLogger(logger_name)
    logger_obj.handlers.clear()  # Remove uvicorn's default handlers
    # uvicorn.error logs too much DEBUG info (ping/pong, websocket messages), set to INFO
    if logger_name == "uvicorn.error":
        logger_obj.setLevel(logging.INFO)
    else:
        logger_obj.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
    logger_obj.propagate = True  # Use root's handler

# 4. Silence noisy third-party loggers
logging.getLogger("botocore").setLevel(logging.WARNING)  # Bedrock streaming is too verbose
logging.getLogger("botocore.parsers").setLevel(logging.WARNING)
logging.getLogger("boto3").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.INFO)
logging.getLogger("watchfiles").setLevel(logging.WARNING)  # File change detection noise

# 4. Configure src.* loggers
src_logger = logging.getLogger("src")
src_logger.handlers.clear()
src_logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
src_logger.propagate = True

# Logging configured successfully in worker process

app = FastAPI(title="Smart AI Assistant API", version="0.5.0")

# ===== ACCESS LOGGING MIDDLEWARE (Must be added BEFORE other middlewares) =====
from starlette.middleware.base import BaseHTTPMiddleware

class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - start) * 1000)
        
        # Log access
        try:
            logger = logging.getLogger("uvicorn.access")
            client = request.client.host if request.client else "-"
            logger.info(f"{client} - \"{request.method} {request.url.path}\" {response.status_code} ({duration_ms}ms)")
        except Exception:
            pass
        
        return response

# Add access log middleware FIRST (before CORS!)
app.add_middleware(AccessLogMiddleware)

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

# Test route to verify logging works

# Include the router from the restructured API module
app.include_router(router)

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
    
    # TEMPORARILY DISABLED to test if this is blocking API routes
    # # Catch-all route for frontend SPA - MUST be last and most specific
    # @app.get("/{full_path:path}", tags=["Frontend"], include_in_schema=False)
    # async def serve_frontend_catchall(full_path: str):
    #     """Catch-all route for frontend SPA - only handles non-API routes"""
    #     # This route should NEVER handle API routes - they are registered first and take precedence
    #     # If we're here, it means no API route matched, so serve frontend
    #     
    #     # Check if it's a static file request
    #     file_path = static_dir / full_path
    #     if file_path.exists() and file_path.is_file():
    #         return FileResponse(str(file_path))
    #     
    #     # For all other routes (SPA routing), serve the index.html
    #     index_file = static_dir / "index.html"
    #     if index_file.exists():
    #         return FileResponse(str(index_html))
    #     
    #     return {"message": f"File not found: {full_path}"}

@app.on_event("startup")
async def startup_event():
    """Initialize application state on startup."""
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
    """A simple ping endpoint to check if the API is running."""
    return {"status": "ok", "message": "pong!", "version": "0.5.0"}

@app.get("/health", tags=["Health Check"])
async def health():
    """Health check endpoint for Docker and monitoring."""
    frontend_available = static_dir.exists()
    return {
        "status": "healthy",
        "version": "0.5.0",
        "components": {
            "api": "running",
            "frontend": "available" if frontend_available else "not_found"
        }
    }

# API information endpoint
@app.get("/api/v1/info", tags=["System Info"])
async def api_info():
    """Get API system information and feature overview."""
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
    print("Starting FastAPI server with new LangChain structure...")
    print("For production, use: uvicorn src.main:app --reload")
    uvicorn.run(app, host="0.0.0.0", port=8000) 