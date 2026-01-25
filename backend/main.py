"""
Economic Terminal - FastAPI Backend

Main application entry point with API routes and WebSocket support.
"""

import os
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from loguru import logger

# Configure logging
logger.add(
    "logs/terminal_{time}.log",
    rotation="1 day",
    retention="7 days",
    level=os.getenv('LOG_LEVEL', 'INFO')
)

# Import modules
from modules.data_storage.database import get_db, init_db, check_connection
from modules.data_storage.queries import QueryHelper

# Import API routers
from backend.api import fx, yields, credit, news, risks, health

# Import scheduler
from backend.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle management.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting Economic Terminal...")
    
    # Initialize database
    try:
        init_db()
        logger.success("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
    
    # Start background scheduler
    try:
        start_scheduler()
        logger.success("Background scheduler started")
    except Exception as e:
        logger.error(f"Scheduler start failed: {e}")
    
    logger.info("Economic Terminal ready!")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Economic Terminal...")
    stop_scheduler()
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Economic Terminal",
    description="Enterprise Risk Management Economic Monitoring Dashboard",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(fx.router, prefix="/api/fx", tags=["FX Rates"])
app.include_router(yields.router, prefix="/api/yields", tags=["Yields"])
app.include_router(credit.router, prefix="/api/credit", tags=["Credit"])
app.include_router(news.router, prefix="/api/news", tags=["News"])
app.include_router(risks.router, prefix="/api/risks", tags=["Risk Alerts"])


# =============================================================================
# DASHBOARD SUMMARY ENDPOINTS
# =============================================================================

@app.get("/api/dashboard")
async def get_dashboard(db: Session = Depends(get_db)):
    """
    Get complete dashboard data in a single request.
    
    Returns all data needed to render the main dashboard view.
    """
    try:
        helper = QueryHelper(db)
        return helper.get_dashboard_summary()
    except Exception as e:
        logger.error(f"Dashboard fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status")
async def get_status(db: Session = Depends(get_db)):
    """
    Get system status overview.
    """
    helper = QueryHelper(db)
    
    return {
        'timestamp': datetime.utcnow().isoformat(),
        'database_connected': check_connection(),
        'module_health': [h.to_dict() for h in helper.get_system_health()],
        'active_alerts': len(helper.get_active_alerts()),
        'critical_alerts': len(helper.get_critical_alerts())
    }


# =============================================================================
# STATIC FILE SERVING (Frontend)
# =============================================================================

# Check if frontend build exists
frontend_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'build')

if os.path.exists(frontend_path):
    # Serve static files
    app.mount("/static", StaticFiles(directory=os.path.join(frontend_path, 'static')), name="static")
    
    @app.get("/")
    async def serve_frontend():
        """Serve React frontend."""
        return FileResponse(os.path.join(frontend_path, 'index.html'))
    
    @app.get("/{full_path:path}")
    async def serve_frontend_routes(full_path: str):
        """Handle client-side routing."""
        # Check if it's an API call
        if full_path.startswith('api/'):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        
        # Serve index.html for all other routes (SPA routing)
        index_path = os.path.join(frontend_path, 'index.html')
        if os.path.exists(index_path):
            return FileResponse(index_path)
        
        raise HTTPException(status_code=404, detail="Not found")
else:
    @app.get("/")
    async def root():
        """API root - no frontend available."""
        return {
            "name": "Economic Terminal API",
            "version": "1.0.0",
            "status": "running",
            "docs": "/docs",
            "message": "Frontend not built. Visit /docs for API documentation."
        }


# =============================================================================
# WEBSOCKET ENDPOINT
# =============================================================================

from backend.websocket import websocket_endpoint

app.add_api_websocket_route("/ws", websocket_endpoint)


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return {
        "error": "Internal server error",
        "detail": str(exc) if os.getenv('DEBUG', 'false').lower() == 'true' else "An error occurred"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=int(os.getenv('PORT', 8000)),
        reload=os.getenv('DEBUG', 'false').lower() == 'true'
    )
