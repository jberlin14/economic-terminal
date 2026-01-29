"""
Health Check API Endpoints
"""

import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, BackgroundTasks
from modules.utils.timezone import get_current_time
from sqlalchemy.orm import Session
from loguru import logger

from modules.data_storage.database import get_db, check_connection, get_database_info
from modules.data_storage.queries import QueryHelper

router = APIRouter()

# Track refresh status
_refresh_status = {
    "running": False,
    "last_refresh": None,
    "results": {}
}


@router.get("/health")
async def health_check():
    """
    Basic health check endpoint.
    
    Returns simple status for load balancers and monitoring.
    """
    return {
        "status": "healthy",
        "timestamp": get_current_time().isoformat()
    }


@router.get("/health/detailed")
async def detailed_health(db: Session = Depends(get_db)):
    """
    Detailed health check with component status.
    """
    helper = QueryHelper(db)
    module_health = helper.get_system_health()
    
    # Calculate overall status
    statuses = [h.status for h in module_health]
    if 'ERROR' in statuses:
        overall_status = 'degraded'
    elif 'WARNING' in statuses:
        overall_status = 'warning'
    else:
        overall_status = 'healthy'
    
    return {
        "status": overall_status,
        "timestamp": get_current_time().isoformat(),
        "components": {
            "database": {
                "status": "healthy" if check_connection() else "unhealthy",
                "info": get_database_info()
            },
            "modules": [
                {
                    "name": h.module_name,
                    "status": h.status,
                    "last_update": h.last_successful_update.isoformat() if h.last_successful_update else None,
                    "errors": h.consecutive_failures
                }
                for h in module_health
            ]
        }
    }


@router.get("/health/modules")
async def module_health(db: Session = Depends(get_db)):
    """
    Get health status of all data modules.
    """
    helper = QueryHelper(db)
    modules = helper.get_system_health()

    return {
        "timestamp": get_current_time().isoformat(),
        "modules": [h.to_dict() for h in modules]
    }


async def _run_refresh_all():
    """Background task to refresh all data sources."""
    global _refresh_status
    _refresh_status["running"] = True
    _refresh_status["results"] = {}

    from backend.scheduler import (
        update_fx_rates,
        update_yields,
        update_credit_spreads,
        fetch_news,
        update_indicators
    )

    tasks = [
        ("fx_rates", update_fx_rates),
        ("yields", update_yields),
        ("credit_spreads", update_credit_spreads),
        ("news", fetch_news),
        ("indicators", update_indicators),
    ]

    for name, task_func in tasks:
        try:
            logger.info(f"Refresh: Starting {name}...")
            await task_func()
            _refresh_status["results"][name] = "success"
            logger.success(f"Refresh: {name} complete")
        except Exception as e:
            _refresh_status["results"][name] = f"error: {str(e)}"
            logger.error(f"Refresh: {name} failed: {e}")

    _refresh_status["running"] = False
    _refresh_status["last_refresh"] = get_current_time().isoformat()
    logger.success("Refresh all complete!")


@router.post("/refresh")
async def refresh_all_data(background_tasks: BackgroundTasks):
    """
    Trigger a manual refresh of all data sources.

    Refreshes:
    - FX rates
    - Yield curve
    - Credit spreads
    - News feeds
    - Economic indicators (incremental)

    Returns immediately and runs refresh in background.
    """
    global _refresh_status

    if _refresh_status["running"]:
        return {
            "status": "already_running",
            "message": "A refresh is already in progress",
            "timestamp": get_current_time().isoformat()
        }

    # Start refresh in background
    background_tasks.add_task(_run_refresh_all)

    return {
        "status": "started",
        "message": "Refresh started for all data sources",
        "timestamp": get_current_time().isoformat()
    }


@router.get("/refresh/status")
async def get_refresh_status():
    """
    Get the status of the current or last refresh operation.
    """
    return {
        "running": _refresh_status["running"],
        "last_refresh": _refresh_status["last_refresh"],
        "results": _refresh_status["results"],
        "timestamp": get_current_time().isoformat()
    }
