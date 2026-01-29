"""
Database Query Helpers

Common query patterns for the Economic Terminal.
Provides convenient methods for data retrieval and aggregation.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import desc, asc, func, and_, or_
from sqlalchemy.orm import Session

from .schema import (
    FXRate, YieldCurve, CreditSpread, EconomicRelease,
    NewsArticle, RiskAlert, SystemHealth
)


class QueryHelper:
    """
    Helper class for common database queries.
    
    Usage:
        with get_db_context() as db:
            helper = QueryHelper(db)
            fx_rates = helper.get_latest_fx_rates()
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    # =========================================================================
    # FX RATE QUERIES
    # =========================================================================
    
    def get_latest_fx_rates(self) -> List[FXRate]:
        """Get the most recent rate for each currency pair."""
        subquery = (
            self.db.query(
                FXRate.pair,
                func.max(FXRate.timestamp).label('max_ts')
            )
            .group_by(FXRate.pair)
            .subquery()
        )
        
        return (
            self.db.query(FXRate)
            .join(subquery, and_(
                FXRate.pair == subquery.c.pair,
                FXRate.timestamp == subquery.c.max_ts
            ))
            .order_by(FXRate.pair)
            .all()
        )
    
    def get_fx_history(
        self,
        pair: str,
        hours: int = 24
    ) -> List[FXRate]:
        """Get FX rate history for a specific pair."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return (
            self.db.query(FXRate)
            .filter(FXRate.pair == pair)
            .filter(FXRate.timestamp >= cutoff)
            .order_by(asc(FXRate.timestamp))
            .all()
        )
    
    def get_fx_rate_at_time(
        self,
        pair: str,
        target_time: datetime
    ) -> Optional[FXRate]:
        """Get the FX rate closest to a specific time."""
        return (
            self.db.query(FXRate)
            .filter(FXRate.pair == pair)
            .filter(FXRate.timestamp <= target_time)
            .order_by(desc(FXRate.timestamp))
            .first()
        )
    
    # =========================================================================
    # YIELD CURVE QUERIES
    # =========================================================================
    
    def get_latest_yield_curve(
        self,
        country: str = 'US'
    ) -> Optional[YieldCurve]:
        """Get the most recent yield curve for a country."""
        return (
            self.db.query(YieldCurve)
            .filter(YieldCurve.country == country)
            .order_by(desc(YieldCurve.timestamp))
            .first()
        )
    
    def get_yield_curve_history(
        self,
        country: str = 'US',
        days: int = 7
    ) -> List[YieldCurve]:
        """Get yield curve history for comparison."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        return (
            self.db.query(YieldCurve)
            .filter(YieldCurve.country == country)
            .filter(YieldCurve.timestamp >= cutoff)
            .order_by(asc(YieldCurve.timestamp))
            .all()
        )
    
    def get_yield_curve_at_date(
        self,
        country: str,
        target_date: datetime
    ) -> Optional[YieldCurve]:
        """Get yield curve closest to a specific date."""
        return (
            self.db.query(YieldCurve)
            .filter(YieldCurve.country == country)
            .filter(YieldCurve.timestamp <= target_date)
            .order_by(desc(YieldCurve.timestamp))
            .first()
        )
    
    # =========================================================================
    # CREDIT SPREAD QUERIES
    # =========================================================================
    
    def get_latest_credit_spreads(self) -> List[CreditSpread]:
        """Get the most recent spread for each credit index."""
        subquery = (
            self.db.query(
                CreditSpread.index_name,
                func.max(CreditSpread.timestamp).label('max_ts')
            )
            .group_by(CreditSpread.index_name)
            .subquery()
        )
        
        return (
            self.db.query(CreditSpread)
            .join(subquery, and_(
                CreditSpread.index_name == subquery.c.index_name,
                CreditSpread.timestamp == subquery.c.max_ts
            ))
            .order_by(CreditSpread.index_name)
            .all()
        )
    
    def get_credit_spread_history(
        self,
        index_name: str,
        days: int = 90
    ) -> List[CreditSpread]:
        """Get credit spread history for percentile calculations."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        return (
            self.db.query(CreditSpread)
            .filter(CreditSpread.index_name == index_name)
            .filter(CreditSpread.timestamp >= cutoff)
            .order_by(asc(CreditSpread.timestamp))
            .all()
        )
    
    # =========================================================================
    # ECONOMIC DATA QUERIES
    # =========================================================================
    
    def get_recent_releases(
        self,
        country: str = 'US',
        days: int = 7
    ) -> List[EconomicRelease]:
        """Get recent economic data releases."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        return (
            self.db.query(EconomicRelease)
            .filter(EconomicRelease.country == country)
            .filter(EconomicRelease.release_date >= cutoff)
            .filter(EconomicRelease.actual.isnot(None))
            .order_by(desc(EconomicRelease.release_date))
            .all()
        )
    
    def get_upcoming_releases(
        self,
        country: str = 'US',
        days: int = 7
    ) -> List[EconomicRelease]:
        """Get upcoming economic data releases (calendar)."""
        now = datetime.utcnow()
        future = now + timedelta(days=days)
        return (
            self.db.query(EconomicRelease)
            .filter(EconomicRelease.country == country)
            .filter(EconomicRelease.release_date >= now)
            .filter(EconomicRelease.release_date <= future)
            .filter(EconomicRelease.actual.is_(None))
            .order_by(asc(EconomicRelease.release_date))
            .all()
        )
    
    def get_surprise_releases(
        self,
        threshold: float = 30.0,
        days: int = 30
    ) -> List[EconomicRelease]:
        """Get releases with significant surprises."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        return (
            self.db.query(EconomicRelease)
            .filter(EconomicRelease.release_date >= cutoff)
            .filter(func.abs(EconomicRelease.surprise_pct) >= threshold)
            .order_by(desc(EconomicRelease.release_date))
            .all()
        )
    
    # =========================================================================
    # NEWS QUERIES
    # =========================================================================
    
    def get_recent_news(
        self,
        hours: int = 24,
        severity: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
        sort_by_relevance: bool = False
    ) -> List[NewsArticle]:
        """Get recent news articles with optional filters."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        query = (
            self.db.query(NewsArticle)
            .filter(NewsArticle.published_at >= cutoff)
        )

        if severity:
            query = query.filter(NewsArticle.severity == severity)
        if category:
            query = query.filter(NewsArticle.category == category)

        if sort_by_relevance:
            # Higher relevance first, then most recent
            query = query.order_by(
                desc(NewsArticle.relevance_score),
                desc(NewsArticle.published_at)
            )
        else:
            query = query.order_by(desc(NewsArticle.published_at))

        return query.limit(limit).all()
    
    def get_critical_news(
        self,
        hours: int = 24
    ) -> List[NewsArticle]:
        """Get CRITICAL severity news only."""
        return self.get_recent_news(hours=hours, severity='CRITICAL')
    
    def get_news_by_country(
        self,
        country: str,
        hours: int = 24,
        limit: int = 20
    ) -> List[NewsArticle]:
        """Get news filtered by country tag."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return (
            self.db.query(NewsArticle)
            .filter(NewsArticle.published_at >= cutoff)
            .filter(NewsArticle.country_tags.contains([country]))
            .order_by(desc(NewsArticle.published_at))
            .limit(limit)
            .all()
        )
    
    def check_duplicate_news(self, content_hash: str) -> bool:
        """Check if a news article already exists."""
        return (
            self.db.query(NewsArticle)
            .filter(NewsArticle.content_hash == content_hash)
            .first() is not None
        )
    
    # =========================================================================
    # RISK ALERT QUERIES
    # =========================================================================
    
    def get_active_alerts(
        self,
        alert_type: Optional[str] = None,
        severity: Optional[str] = None
    ) -> List[RiskAlert]:
        """Get all active (unresolved) risk alerts."""
        query = (
            self.db.query(RiskAlert)
            .filter(RiskAlert.is_active == True)
        )
        
        if alert_type:
            query = query.filter(RiskAlert.alert_type == alert_type)
        if severity:
            query = query.filter(RiskAlert.severity == severity)
        
        return (
            query
            .order_by(desc(RiskAlert.triggered_at))
            .all()
        )
    
    def get_critical_alerts(self) -> List[RiskAlert]:
        """Get active CRITICAL alerts only."""
        return self.get_active_alerts(severity='CRITICAL')
    
    def get_alerts_for_digest(
        self,
        hours: int = 24
    ) -> Dict[str, List[RiskAlert]]:
        """Get alerts grouped by severity for daily digest."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        alerts = (
            self.db.query(RiskAlert)
            .filter(RiskAlert.triggered_at >= cutoff)
            .order_by(desc(RiskAlert.triggered_at))
            .all()
        )
        
        return {
            'CRITICAL': [a for a in alerts if a.severity == 'CRITICAL'],
            'HIGH': [a for a in alerts if a.severity == 'HIGH'],
            'MEDIUM': [a for a in alerts if a.severity == 'MEDIUM']
        }
    
    def check_duplicate_alert(
        self,
        alert_hash: str,
        hours: int = 1
    ) -> bool:
        """Check if a similar alert was already generated recently."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return (
            self.db.query(RiskAlert)
            .filter(RiskAlert.alert_hash == alert_hash)
            .filter(RiskAlert.triggered_at >= cutoff)
            .first() is not None
        )
    
    def resolve_alert(self, alert_id: int) -> bool:
        """Mark an alert as resolved."""
        alert = self.db.query(RiskAlert).filter(RiskAlert.id == alert_id).first()
        if alert:
            alert.is_active = False
            alert.resolved_at = datetime.utcnow()
            self.db.commit()
            return True
        return False
    
    # =========================================================================
    # SYSTEM HEALTH QUERIES
    # =========================================================================
    
    def get_system_health(self) -> List[SystemHealth]:
        """Get the latest health status for all modules."""
        subquery = (
            self.db.query(
                SystemHealth.module_name,
                func.max(SystemHealth.timestamp).label('max_ts')
            )
            .group_by(SystemHealth.module_name)
            .subquery()
        )
        
        return (
            self.db.query(SystemHealth)
            .join(subquery, and_(
                SystemHealth.module_name == subquery.c.module_name,
                SystemHealth.timestamp == subquery.c.max_ts
            ))
            .order_by(SystemHealth.module_name)
            .all()
        )
    
    def get_module_health(self, module_name: str) -> Optional[SystemHealth]:
        """Get health status for a specific module."""
        return (
            self.db.query(SystemHealth)
            .filter(SystemHealth.module_name == module_name)
            .order_by(desc(SystemHealth.timestamp))
            .first()
        )
    
    def update_module_health(
        self,
        module_name: str,
        status: str,
        message: Optional[str] = None,
        error: Optional[str] = None
    ) -> SystemHealth:
        """Update health status for a module."""
        health = SystemHealth(
            module_name=module_name,
            status=status,
            status_message=message,
            timestamp=datetime.utcnow()
        )
        
        if status == 'OK':
            health.last_successful_update = datetime.utcnow()
            health.consecutive_failures = 0
        elif status == 'ERROR' and error:
            health.last_error = error
            health.last_error_at = datetime.utcnow()
            # Get previous to increment failure count
            prev = self.get_module_health(module_name)
            if prev:
                health.consecutive_failures = prev.consecutive_failures + 1
        
        self.db.add(health)
        self.db.commit()
        return health
    
    # =========================================================================
    # AGGREGATION QUERIES
    # =========================================================================
    
    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get a complete summary for the dashboard."""
        return {
            'fx_rates': [r.to_dict() for r in self.get_latest_fx_rates()],
            'yield_curve': self.get_latest_yield_curve().to_dict() if self.get_latest_yield_curve() else None,
            'credit_spreads': [s.to_dict() for s in self.get_latest_credit_spreads()],
            'recent_releases': [r.to_dict() for r in self.get_recent_releases(days=3)],
            'upcoming_releases': [r.to_dict() for r in self.get_upcoming_releases(days=7)],
            'active_alerts': [a.to_dict() for a in self.get_active_alerts()],
            'recent_news': [n.to_dict() for n in self.get_recent_news(hours=24, limit=30, sort_by_relevance=True)],
            'system_health': [h.to_dict() for h in self.get_system_health()],
            'timestamp': datetime.utcnow().isoformat()
        }
    
    # =========================================================================
    # CLEANUP QUERIES
    # =========================================================================
    
    def cleanup_old_data(self, days: int = 90) -> Dict[str, int]:
        """Remove data older than specified days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        counts = {}
        
        # FX rates older than 90 days
        counts['fx_rates'] = (
            self.db.query(FXRate)
            .filter(FXRate.timestamp < cutoff)
            .delete()
        )
        
        # Yield curves: keep one record per day forever (for historical charts).
        # Only delete duplicate intraday snapshots older than 90 days.
        # The backfill script and daily snapshots use source='fred_daily'.
        counts['yield_curves'] = (
            self.db.query(YieldCurve)
            .filter(YieldCurve.timestamp < cutoff)
            .filter(YieldCurve.source != 'fred_daily')
            .delete()
        )
        
        # News older than 90 days
        counts['news'] = (
            self.db.query(NewsArticle)
            .filter(NewsArticle.published_at < cutoff)
            .delete()
        )
        
        # Resolved alerts older than 90 days
        counts['alerts'] = (
            self.db.query(RiskAlert)
            .filter(RiskAlert.is_active == False)
            .filter(RiskAlert.resolved_at < cutoff)
            .delete()
        )
        
        self.db.commit()
        return counts
