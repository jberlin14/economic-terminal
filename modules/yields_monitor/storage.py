"""
Yields Storage Module

Handles database operations for yield curve data.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import desc, asc
from sqlalchemy.orm import Session
from loguru import logger

from ..data_storage.schema import YieldCurve
from ..data_storage.database import get_db_context
from .models import YieldCurveData


class YieldsStorage:
    """
    Database storage handler for yield curves.
    """
    
    def __init__(self, db: Optional[Session] = None):
        self._db = db
    
    def _get_db(self) -> Session:
        if self._db:
            return self._db
        raise RuntimeError("No database session provided")
    
    def store_curve(self, curve_data: YieldCurveData) -> YieldCurve:
        """
        Store a yield curve in the database.
        """
        db = self._get_db()
        
        yield_curve = YieldCurve(
            country=curve_data.country,
            timestamp=curve_data.timestamp,
            tenor_1m=curve_data.tenor_1m,
            tenor_3m=curve_data.tenor_3m,
            tenor_6m=curve_data.tenor_6m,
            tenor_1y=curve_data.tenor_1y,
            tenor_2y=curve_data.tenor_2y,
            tenor_5y=curve_data.tenor_5y,
            tenor_10y=curve_data.tenor_10y,
            tenor_20y=curve_data.tenor_20y,
            tenor_30y=curve_data.tenor_30y,
            spread_10y2y=curve_data.spread_10y2y,
            spread_10y3m=curve_data.spread_10y3m,
            spread_30y10y=curve_data.spread_30y10y,
            tips_5y=curve_data.tips_5y,
            tips_10y=curve_data.tips_10y,
            source=curve_data.source
        )
        
        db.add(yield_curve)
        db.commit()
        db.refresh(yield_curve)
        
        logger.debug(f"Stored yield curve: 10Y={curve_data.tenor_10y}%")
        return yield_curve
    
    def get_latest_curve(self, country: str = 'US') -> Optional[YieldCurve]:
        """Get the most recent yield curve."""
        db = self._get_db()
        
        return (
            db.query(YieldCurve)
            .filter(YieldCurve.country == country)
            .order_by(desc(YieldCurve.timestamp))
            .first()
        )
    
    def get_curve_at_time(
        self,
        target_time: datetime,
        country: str = 'US'
    ) -> Optional[YieldCurve]:
        """Get yield curve closest to a specific time."""
        db = self._get_db()
        
        return (
            db.query(YieldCurve)
            .filter(YieldCurve.country == country)
            .filter(YieldCurve.timestamp <= target_time)
            .order_by(desc(YieldCurve.timestamp))
            .first()
        )
    
    def get_curve_history(
        self,
        country: str = 'US',
        days: int = 7
    ) -> List[YieldCurve]:
        """Get yield curve history."""
        db = self._get_db()
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        return (
            db.query(YieldCurve)
            .filter(YieldCurve.country == country)
            .filter(YieldCurve.timestamp >= cutoff)
            .order_by(asc(YieldCurve.timestamp))
            .all()
        )
    
    def get_spread_history(
        self,
        spread_name: str = '10y2y',
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get spread history for charting."""
        db = self._get_db()
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        spread_attr = f"spread_{spread_name}"
        
        curves = (
            db.query(YieldCurve)
            .filter(YieldCurve.timestamp >= cutoff)
            .order_by(asc(YieldCurve.timestamp))
            .all()
        )
        
        history = []
        for curve in curves:
            spread = getattr(curve, spread_attr, None)
            if spread is not None:
                history.append({
                    'timestamp': curve.timestamp.isoformat(),
                    'spread': spread,
                    'spread_bps': spread * 100
                })
        
        return history
    
    def cleanup_old_data(self, days: int = 90) -> int:
        """Remove data older than specified days."""
        db = self._get_db()
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        deleted = (
            db.query(YieldCurve)
            .filter(YieldCurve.timestamp < cutoff)
            .delete()
        )
        
        db.commit()
        logger.info(f"Cleaned up {deleted} old yield curve records")
        return deleted


def store_yield_curve(curve_data: YieldCurveData) -> YieldCurve:
    """Convenience function with context manager."""
    with get_db_context() as db:
        storage = YieldsStorage(db)
        return storage.store_curve(curve_data)


def get_latest_yield_curve() -> Optional[Dict[str, Any]]:
    """Get latest curve as dictionary."""
    with get_db_context() as db:
        storage = YieldsStorage(db)
        curve = storage.get_latest_curve()
        
        if curve:
            return {
                'timestamp': curve.timestamp.isoformat(),
                'country': curve.country,
                'curve': {
                    '1M': curve.tenor_1m,
                    '3M': curve.tenor_3m,
                    '6M': curve.tenor_6m,
                    '1Y': curve.tenor_1y,
                    '2Y': curve.tenor_2y,
                    '5Y': curve.tenor_5y,
                    '10Y': curve.tenor_10y,
                    '20Y': curve.tenor_20y,
                    '30Y': curve.tenor_30y,
                },
                'spreads': {
                    '10Y-2Y': curve.spread_10y2y,
                    '10Y-3M': curve.spread_10y3m,
                    '30Y-10Y': curve.spread_30y10y,
                },
                'tips': {
                    '5Y': curve.tips_5y,
                    '10Y': curve.tips_10y,
                }
            }
        return None
