"""
Alert Manager

Centralized management of risk alerts including:
- Alert generation and storage
- Deduplication
- Email routing
- Alert lifecycle management
"""

import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from loguru import logger

from .config import ALERT_COOLDOWN, MAX_ACTIVE_ALERTS, RISK_HIERARCHY
from .models import RiskAlertData, AlertBatch, AlertSummary
from ..data_storage.schema import RiskAlert
from ..data_storage.database import get_db_context


class AlertManager:
    """
    Manages the lifecycle of risk alerts.
    """
    
    def __init__(self, db: Optional[Session] = None):
        self._db = db
        self._active_alerts: List[RiskAlertData] = []
        self._muted_alerts: Dict[str, datetime] = {}  # hash -> mute_until
    
    def _get_db(self) -> Session:
        if self._db:
            return self._db
        raise RuntimeError("No database session provided")
    
    def process_alerts(
        self,
        alerts: List[RiskAlertData],
        source_module: str = 'unknown'
    ) -> AlertBatch:
        """
        Process a batch of incoming alerts.
        
        - Deduplicates against recent alerts
        - Stores new alerts in database
        - Routes critical alerts for immediate notification
        
        Args:
            alerts: List of alerts to process
            source_module: Name of the module generating alerts
            
        Returns:
            AlertBatch with processed alerts
        """
        db = self._get_db()
        new_alerts = []
        
        for alert in alerts:
            # Check if muted
            if self._is_muted(alert):
                logger.debug(f"Skipping muted alert: {alert.alert_type}/{alert.related_entity}")
                continue
            
            # Check for duplicate
            if self._is_duplicate(db, alert):
                logger.debug(f"Skipping duplicate alert: {alert.alert_type}/{alert.related_entity}")
                continue
            
            # Store in database
            db_alert = self._store_alert(db, alert)
            new_alerts.append(alert)
            
            logger.info(f"New {alert.severity} alert: {alert.title}")
        
        db.commit()
        
        return AlertBatch(
            alerts=new_alerts,
            timestamp=datetime.utcnow(),
            source_module=source_module
        )
    
    def _is_muted(self, alert: RiskAlertData) -> bool:
        """Check if alert is currently muted."""
        alert_hash = alert.alert_hash
        
        if alert_hash in self._muted_alerts:
            if datetime.utcnow() < self._muted_alerts[alert_hash]:
                return True
            else:
                del self._muted_alerts[alert_hash]
        
        return False
    
    def _is_duplicate(
        self,
        db: Session,
        alert: RiskAlertData,
        window_hours: Optional[int] = None
    ) -> bool:
        """Check if similar alert exists within cooldown window."""
        if window_hours is None:
            window_hours = ALERT_COOLDOWN.get(alert.alert_type, 3600) / 3600
        
        cutoff = datetime.utcnow() - timedelta(hours=window_hours)
        
        existing = (
            db.query(RiskAlert)
            .filter(RiskAlert.alert_hash == alert.alert_hash)
            .filter(RiskAlert.triggered_at >= cutoff)
            .first()
        )
        
        return existing is not None
    
    def _store_alert(
        self,
        db: Session,
        alert: RiskAlertData
    ) -> RiskAlert:
        """Store alert in database."""
        db_alert = RiskAlert(
            alert_type=alert.alert_type,
            severity=alert.severity,
            title=alert.title,
            message=alert.message,
            details=alert.details,
            triggered_at=alert.triggered_at,
            related_entity=alert.related_entity,
            related_value=alert.related_value,
            threshold_value=alert.threshold_value,
            alert_hash=alert.alert_hash,
            is_active=True,
            email_sent=False
        )
        
        db.add(db_alert)
        return db_alert
    
    def get_active_alerts(
        self,
        alert_type: Optional[str] = None,
        severity: Optional[str] = None
    ) -> List[RiskAlert]:
        """Get all active alerts."""
        db = self._get_db()
        
        query = db.query(RiskAlert).filter(RiskAlert.is_active == True)
        
        if alert_type:
            query = query.filter(RiskAlert.alert_type == alert_type)
        if severity:
            query = query.filter(RiskAlert.severity == severity)
        
        return query.order_by(RiskAlert.triggered_at.desc()).all()
    
    def get_critical_alerts(self) -> List[RiskAlert]:
        """Get active critical alerts."""
        return self.get_active_alerts(severity='CRITICAL')
    
    def get_alerts_for_email(
        self,
        unsent_only: bool = True
    ) -> Dict[str, List[RiskAlert]]:
        """
        Get alerts grouped for email sending.
        
        Returns:
            Dictionary with 'critical' and 'high' alert lists
        """
        db = self._get_db()
        
        query = db.query(RiskAlert).filter(RiskAlert.is_active == True)
        
        if unsent_only:
            query = query.filter(RiskAlert.email_sent == False)
        
        alerts = query.all()
        
        return {
            'critical': [a for a in alerts if a.severity == 'CRITICAL'],
            'high': [a for a in alerts if a.severity == 'HIGH']
        }
    
    def mark_email_sent(self, alert_ids: List[int]) -> None:
        """Mark alerts as having been emailed."""
        db = self._get_db()
        
        db.query(RiskAlert).filter(RiskAlert.id.in_(alert_ids)).update(
            {'email_sent': True, 'email_sent_at': datetime.utcnow()},
            synchronize_session=False
        )
        
        db.commit()
    
    def resolve_alert(self, alert_id: int) -> bool:
        """Mark an alert as resolved."""
        db = self._get_db()
        
        alert = db.query(RiskAlert).filter(RiskAlert.id == alert_id).first()
        if alert:
            alert.is_active = False
            alert.resolved_at = datetime.utcnow()
            db.commit()
            return True
        return False
    
    def acknowledge_alert(self, alert_id: int) -> bool:
        """Mark an alert as acknowledged."""
        db = self._get_db()
        
        alert = db.query(RiskAlert).filter(RiskAlert.id == alert_id).first()
        if alert:
            alert.acknowledged = True
            alert.acknowledged_at = datetime.utcnow()
            db.commit()
            return True
        return False
    
    def mute_alert(
        self,
        alert: RiskAlertData,
        hours: int = 1
    ) -> None:
        """Mute similar alerts for specified hours."""
        self._muted_alerts[alert.alert_hash] = datetime.utcnow() + timedelta(hours=hours)
    
    def get_summary(self) -> AlertSummary:
        """Get summary of current alert status."""
        db = self._get_db()
        
        active = self.get_active_alerts()
        
        summary = AlertSummary(
            timestamp=datetime.utcnow(),
            total_active=len(active),
            by_severity={},
            by_type={},
            critical_alerts=[],
            high_alerts=[]
        )
        
        for alert in active:
            # Count by severity
            if alert.severity not in summary.by_severity:
                summary.by_severity[alert.severity] = 0
            summary.by_severity[alert.severity] += 1
            
            # Count by type
            if alert.alert_type not in summary.by_type:
                summary.by_type[alert.alert_type] = 0
            summary.by_type[alert.alert_type] += 1
            
            # Add to lists
            alert_data = RiskAlertData(
                alert_type=alert.alert_type,
                severity=alert.severity,
                title=alert.title,
                message=alert.message,
                related_entity=alert.related_entity,
                related_value=alert.related_value,
                triggered_at=alert.triggered_at,
                details=alert.details or {}
            )
            
            if alert.severity == 'CRITICAL':
                summary.critical_alerts.append(alert_data)
            elif alert.severity == 'HIGH':
                summary.high_alerts.append(alert_data)
        
        return summary
    
    def expire_old_alerts(self, hours: int = 24) -> int:
        """Automatically resolve alerts older than specified hours."""
        db = self._get_db()
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        count = (
            db.query(RiskAlert)
            .filter(RiskAlert.is_active == True)
            .filter(RiskAlert.triggered_at < cutoff)
            .update({'is_active': False, 'resolved_at': datetime.utcnow()})
        )
        
        db.commit()
        logger.info(f"Expired {count} old alerts")
        return count
    
    def cleanup_old_alerts(self, days: int = 90) -> int:
        """Delete resolved alerts older than specified days."""
        db = self._get_db()
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        count = (
            db.query(RiskAlert)
            .filter(RiskAlert.is_active == False)
            .filter(RiskAlert.resolved_at < cutoff)
            .delete()
        )
        
        db.commit()
        logger.info(f"Cleaned up {count} old alerts")
        return count


def process_all_risks(
    fx_data: Optional[Dict] = None,
    yield_data: Optional[Dict] = None,
    credit_data: Optional[Dict] = None,
    news_articles: Optional[List] = None,
    economic_releases: Optional[List] = None
) -> AlertBatch:
    """
    Convenience function to process all risk types at once.
    """
    from .fx_rules import detect_fx_risks
    from .yield_rules import detect_yield_risks
    from .credit_rules import detect_credit_risks
    from .geopolitical_rules import detect_geopolitical_risks
    from .economic_rules import detect_economic_risks
    
    all_alerts = []
    
    if fx_data:
        all_alerts.extend(detect_fx_risks(fx_data))
    
    if yield_data:
        all_alerts.extend(detect_yield_risks(yield_data))
    
    if credit_data:
        all_alerts.extend(detect_credit_risks(credit_data))
    
    if news_articles:
        all_alerts.extend(detect_geopolitical_risks(news_articles))
    
    if economic_releases:
        all_alerts.extend(detect_economic_risks(economic_releases))
    
    # Sort by risk hierarchy
    all_alerts.sort(key=lambda a: RISK_HIERARCHY.get(a.alert_type, 99))
    
    # Process through alert manager
    with get_db_context() as db:
        manager = AlertManager(db)
        return manager.process_alerts(all_alerts, source_module='aggregator')
