"""
Risk Alerts API Endpoints
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from modules.utils.timezone import get_current_time
from sqlalchemy.orm import Session

from modules.data_storage.database import get_db
from modules.data_storage.queries import QueryHelper
from modules.risk_detector.alert_manager import AlertManager

router = APIRouter()


@router.get("/active")
async def get_active_alerts(
    alert_type: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None, pattern="^(CRITICAL|HIGH|MEDIUM)$"),
    db: Session = Depends(get_db)
):
    """
    Get all active (unresolved) risk alerts.
    """
    helper = QueryHelper(db)
    alerts = helper.get_active_alerts(alert_type=alert_type, severity=severity)
    
    return {
        "timestamp": get_current_time().isoformat(),
        "count": len(alerts),
        "alerts": [a.to_dict() for a in alerts]
    }


@router.get("/critical")
async def get_critical_alerts(db: Session = Depends(get_db)):
    """
    Get active CRITICAL alerts only.
    """
    helper = QueryHelper(db)
    alerts = helper.get_critical_alerts()
    
    return {
        "timestamp": get_current_time().isoformat(),
        "count": len(alerts),
        "alerts": [a.to_dict() for a in alerts]
    }


@router.get("/summary")
async def get_alert_summary(db: Session = Depends(get_db)):
    """
    Get summary of alert status.
    """
    manager = AlertManager(db)
    summary = manager.get_summary()
    
    return {
        "timestamp": summary.timestamp.isoformat(),
        "total_active": summary.total_active,
        "by_severity": summary.by_severity,
        "by_type": summary.by_type,
        "has_critical": summary.has_critical,
        "critical_alerts": [a.to_dict() for a in summary.critical_alerts],
        "high_alerts": [a.to_dict() for a in summary.high_alerts]
    }


@router.get("/digest")
async def get_digest_alerts(
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db)
):
    """
    Get alerts for daily digest grouped by severity.
    """
    helper = QueryHelper(db)
    alerts_by_severity = helper.get_alerts_for_digest(hours=hours)
    
    return {
        "timestamp": get_current_time().isoformat(),
        "hours": hours,
        "critical": [a.to_dict() for a in alerts_by_severity.get('CRITICAL', [])],
        "high": [a.to_dict() for a in alerts_by_severity.get('HIGH', [])],
        "medium": [a.to_dict() for a in alerts_by_severity.get('MEDIUM', [])]
    }


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db)
):
    """
    Mark an alert as resolved.
    """
    manager = AlertManager(db)
    success = manager.resolve_alert(alert_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    
    return {"status": "resolved", "alert_id": alert_id}


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db)
):
    """
    Mark an alert as acknowledged.
    """
    manager = AlertManager(db)
    success = manager.acknowledge_alert(alert_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    
    return {"status": "acknowledged", "alert_id": alert_id}
