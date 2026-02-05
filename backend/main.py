"""
Economic Terminal - FastAPI Backend

Main application entry point with API routes and WebSocket support.
"""

import os
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from loguru import logger

# Import timezone utility
from modules.utils.timezone import get_current_time

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
from backend.api import fx, yields, credit, news, risks, health, news_advanced, indicators, calendar

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
app.include_router(news_advanced.router, prefix="/api/news", tags=["News Advanced"])
app.include_router(risks.router, prefix="/api/risks", tags=["Risk Alerts"])
app.include_router(indicators.router, prefix="/api/indicators", tags=["Economic Indicators"])
app.include_router(calendar.router, prefix="/api/calendar", tags=["Economic Calendar"])


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
        'timestamp': get_current_time().isoformat(),
        'database_connected': check_connection(),
        'module_health': [h.to_dict() for h in helper.get_system_health()],
        'active_alerts': len(helper.get_active_alerts()),
        'critical_alerts': len(helper.get_critical_alerts())
    }


@app.get("/api/summary")
async def get_market_summary(db: Session = Depends(get_db)):
    """
    Get AI-generated market summary.

    Returns comprehensive analysis of current economic conditions including:
    - Headline summary
    - Overview narrative
    - Section-by-section analysis
    - Key metrics
    - Sentiment assessment
    - Alerts and trends
    """
    try:
        from modules.market_summary import MarketSummaryGenerator

        generator = MarketSummaryGenerator(db)
        return generator.to_dict()
    except Exception as e:
        logger.error(f"Market summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/narrative/generate")
async def generate_market_narrative(
    narrative_type: str = 'comprehensive',
    db: Session = Depends(get_db)
):
    """
    Generate an AI-powered market narrative using Claude.

    This endpoint triggers on-demand generation of a market analysis narrative
    with selectable analyst personas/perspectives.

    Args:
        narrative_type: The type of narrative to generate. Options:
            - 'comprehensive': Balanced overview (default)
            - 'fed_watcher': Fed policy deep dive
            - 'rates_trader': Yield curve & credit analysis
            - 'equity_strategist': Stock market focus
            - 'macro_bear': Recession watch & risks
            - 'geopolitical_analyst': Trade/policy/conflicts
            - 'contrarian': Challenge consensus
            - 'quick_brief': Concise 2-minute read

    Returns:
        {
            "narrative": "Long-form analysis text...",
            "generated_at": "2026-01-27T...",
            "model": "claude-sonnet-4-5-20250929",
            "narrative_type": "fed_watcher",
            "narrative_mode": "Fed Watcher",
            "tokens_used": 1234
        }
    """
    try:
        from modules.market_summary import AIMarketNarrative

        # Validate narrative_type
        available_modes = AIMarketNarrative.get_available_narrative_modes()
        if narrative_type not in available_modes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid narrative_type '{narrative_type}'. Available options: {', '.join(available_modes.keys())}"
            )

        generator = AIMarketNarrative(db)

        # Generate narrative (will use fallback if API unavailable)
        result = await generator.generate_narrative(narrative_type=narrative_type)

        if "error" in result:
            error_detail = {
                "error": result["error"],
                "message": "Narrative generation failed. This may be due to data availability issues or system errors.",
                "suggestion": "Please try again later or check the /api/narrative/health endpoint for system status.",
                "timestamp": result.get("generated_at", get_current_time().isoformat())
            }
            raise HTTPException(status_code=500, detail=error_detail)

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Narrative generation error: {e}", exc_info=True)
        error_detail = {
            "error": "Unexpected error during narrative generation",
            "details": str(e),
            "suggestion": "Please check server logs for more information or contact support.",
            "timestamp": get_current_time().isoformat()
        }
        raise HTTPException(status_code=500, detail=error_detail)


@app.get("/api/narrative/modes")
async def get_narrative_modes():
    """
    Get list of available narrative modes with descriptions.

    Returns:
        {
            "comprehensive": {
                "name": "Comprehensive Overview",
                "description": "Balanced analysis covering all major economic themes",
                "icon": "📊"
            },
            ...
        }
    """
    try:
        from modules.market_summary import AIMarketNarrative
        return AIMarketNarrative.get_available_narrative_modes()
    except Exception as e:
        logger.error(f"Error fetching narrative modes: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to retrieve available narrative modes",
                "details": str(e),
                "timestamp": get_current_time().isoformat()
            }
        )


@app.get("/api/narrative/status")
async def get_narrative_status():
    """
    Check if AI narrative generation is available.
    """
    import os
    api_key = os.getenv('ANTHROPIC_API_KEY')

    return {
        "available": bool(api_key),
        "timestamp": get_current_time().isoformat()
    }


@app.get("/api/narrative/health")
async def get_narrative_health():
    """
    Comprehensive health check for the narrative generation system.

    Returns detailed diagnostics including:
    - Database connectivity
    - API key availability
    - Data source health
    - Cache status
    - Recent generation performance
    """
    health = {
        "status": "healthy",
        "timestamp": get_current_time().isoformat(),
        "checks": {}
    }

    try:
        from modules.market_summary import AIMarketNarrative
        from modules.data_storage import get_db
        import os

        # Check 1: Database connectivity
        try:
            db = next(get_db())
            # Simple query to verify DB is accessible
            db.execute("SELECT 1")
            health["checks"]["database"] = {
                "status": "ok",
                "message": "Database connection successful"
            }
            db.close()
        except Exception as e:
            health["checks"]["database"] = {
                "status": "error",
                "message": f"Database error: {str(e)}"
            }
            health["status"] = "degraded"

        # Check 2: API Key availability
        api_key = os.getenv('ANTHROPIC_API_KEY')
        health["checks"]["api_key"] = {
            "status": "ok" if api_key else "warning",
            "message": "API key configured" if api_key else "API key not configured - using fallback mode"
        }
        if not api_key:
            health["status"] = "degraded" if health["status"] == "healthy" else health["status"]

        # Check 3: Cache stats
        try:
            cache_stats = AIMarketNarrative.get_cache_stats()
            health["checks"]["cache"] = {
                "status": "ok",
                "size": cache_stats.get("cache_size", 0),
                "ttl_minutes": cache_stats.get("ttl_minutes", 30)
            }
        except Exception as e:
            health["checks"]["cache"] = {
                "status": "warning",
                "message": f"Cache stats unavailable: {str(e)}"
            }

        # Check 4: Data quality (if we have a recent narrative)
        try:
            db = next(get_db())
            generator = AIMarketNarrative(db)
            last_narrative = generator.get_last_narrative()

            if last_narrative and 'data_quality' in last_narrative:
                dq = last_narrative['data_quality']
                health["checks"]["data_quality"] = {
                    "status": "ok" if dq.get('quality_level') in ['EXCELLENT', 'GOOD'] else "warning",
                    "quality_score": dq.get('quality_score', 0),
                    "quality_level": dq.get('quality_level', 'UNKNOWN'),
                    "indicators_available": dq.get('indicators_available', 0),
                    "news_count": dq.get('news_count', 0)
                }
                if dq.get('quality_level') in ['DEGRADED', 'POOR']:
                    health["status"] = "degraded"
            else:
                health["checks"]["data_quality"] = {
                    "status": "info",
                    "message": "No recent narrative to assess"
                }

            db.close()
        except Exception as e:
            health["checks"]["data_quality"] = {
                "status": "warning",
                "message": f"Data quality check unavailable: {str(e)}"
            }

        # Check 5: Recent performance metrics
        try:
            if last_narrative and 'timing' in last_narrative:
                timing = last_narrative['timing']
                health["checks"]["performance"] = {
                    "status": "ok",
                    "last_generation_ms": timing.get('total_ms', 0),
                    "from_cache": last_narrative.get('from_cache', False)
                }
            else:
                health["checks"]["performance"] = {
                    "status": "info",
                    "message": "No recent performance data"
                }
        except Exception as e:
            health["checks"]["performance"] = {
                "status": "warning",
                "message": f"Performance metrics unavailable: {str(e)}"
            }

        return health

    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "error",
            "timestamp": get_current_time().isoformat(),
            "error": str(e)
        }


@app.get("/api/narrative/cache/stats")
async def get_narrative_cache_stats():
    """
    Get narrative cache statistics (size, TTL, entries).

    Returns cache metrics useful for monitoring API cost optimization.
    """
    try:
        from modules.market_summary import AIMarketNarrative
        return AIMarketNarrative.get_cache_stats()
    except Exception as e:
        logger.error(f"Error fetching cache stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to retrieve cache statistics",
                "details": str(e),
                "suggestion": "Check server logs for more information",
                "timestamp": get_current_time().isoformat()
            }
        )


@app.post("/api/narrative/cache/clear")
async def clear_narrative_cache():
    """
    Clear all cached narratives (force regeneration on next request).

    Useful when you want to ensure fresh data or after configuration changes.
    """
    try:
        from modules.market_summary import AIMarketNarrative
        count = AIMarketNarrative.clear_cache()
        return {
            "cleared_entries": count,
            "message": f"Successfully cleared {count} cached narrative(s)",
            "timestamp": get_current_time().isoformat()
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to clear narrative cache",
                "details": str(e),
                "suggestion": "Check server logs for more information",
                "timestamp": get_current_time().isoformat()
            }
        )


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
