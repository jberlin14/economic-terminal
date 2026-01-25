"""
Health Check API Endpoints
"""

from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from modules.data_storage.database import get_db, check_connection, get_database_info
from modules.data_storage.queries import QueryHelper

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Basic health check endpoint.
    
    Returns simple status for load balancers and monitoring.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
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
        "timestamp": datetime.utcnow().isoformat(),
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
        "timestamp": datetime.utcnow().isoformat(),
        "modules": [h.to_dict() for h in modules]
    }
