"""
FX Storage Module

Handles database operations for FX rate data.
Manages storage, retrieval, and historical calculations.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import desc, asc, func, and_
from sqlalchemy.orm import Session
from loguru import logger

from ..data_storage.schema import FXRate
from ..data_storage.database import get_db_context
from .models import FXRateData, FXUpdate
from .rate_calculator import RateCalculator
from .config import get_decimal_places, SPARKLINE_POINTS


class FXStorage:
    """
    Database storage handler for FX rates.
    """
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize with optional database session."""
        self._db = db
    
    def _get_db(self) -> Session:
        """Get database session."""
        if self._db:
            return self._db
        # This will be managed externally
        raise RuntimeError("No database session provided")
    
    def store_rate(self, rate_data: FXRateData) -> FXRate:
        """
        Store a single FX rate in the database.
        
        Args:
            rate_data: FXRateData to store
            
        Returns:
            Created FXRate database record
        """
        db = self._get_db()
        
        fx_rate = FXRate(
            pair=rate_data.pair,
            rate=rate_data.rate,
            timestamp=rate_data.timestamp,
            change_1h=rate_data.change_1h,
            change_24h=rate_data.change_24h,
            change_1w=rate_data.change_1w,
            change_ytd=rate_data.change_ytd,
            sparkline_data=rate_data.sparkline,
            source=rate_data.source
        )
        
        db.add(fx_rate)
        db.commit()
        db.refresh(fx_rate)
        
        logger.debug(f"Stored FX rate: {rate_data.pair} = {rate_data.rate}")
        return fx_rate
    
    def store_batch(self, update: FXUpdate) -> List[FXRate]:
        """
        Store multiple FX rates from an update.
        
        Args:
            update: FXUpdate containing multiple rates
            
        Returns:
            List of created FXRate records
        """
        db = self._get_db()
        records = []
        
        for rate_data in update.rates:
            # Calculate changes before storing
            rate_with_changes = self._enrich_with_changes(rate_data)
            
            fx_rate = FXRate(
                pair=rate_with_changes.pair,
                rate=rate_with_changes.rate,
                timestamp=rate_with_changes.timestamp,
                change_1h=rate_with_changes.change_1h,
                change_24h=rate_with_changes.change_24h,
                change_1w=rate_with_changes.change_1w,
                change_ytd=rate_with_changes.change_ytd,
                sparkline_data=rate_with_changes.sparkline,
                source=rate_with_changes.source
            )
            
            db.add(fx_rate)
            records.append(fx_rate)
        
        db.commit()
        logger.info(f"Stored {len(records)} FX rates")
        return records
    
    def _enrich_with_changes(self, rate_data: FXRateData) -> FXRateData:
        """
        Calculate change percentages for a rate.
        
        Args:
            rate_data: FXRateData with current rate
            
        Returns:
            FXRateData with calculated changes
        """
        db = self._get_db()
        now = datetime.utcnow()
        
        # Get historical rates for comparison
        rate_1h = self._get_rate_at_time(db, rate_data.pair, now - timedelta(hours=1))
        rate_24h = self._get_rate_at_time(db, rate_data.pair, now - timedelta(hours=24))
        rate_1w = self._get_rate_at_time(db, rate_data.pair, now - timedelta(weeks=1))
        
        # Get YTD start rate
        year_start = datetime(now.year, 1, 1)
        rate_ytd = self._get_rate_at_time(db, rate_data.pair, year_start)
        
        # Calculate changes
        changes = RateCalculator.calculate_all_changes(
            rate_data.rate,
            rate_1h,
            rate_24h,
            rate_1w,
            rate_ytd
        )
        
        # Update the rate data
        return FXRateData(
            pair=rate_data.pair,
            rate=rate_data.rate,
            timestamp=rate_data.timestamp,
            source=rate_data.source,
            change_1h=changes['change_1h'],
            change_24h=changes['change_24h'],
            change_1w=changes['change_1w'],
            change_ytd=changes['change_ytd'],
            sparkline=rate_data.sparkline
        )
    
    def _get_rate_at_time(
        self,
        db: Session,
        pair: str,
        target_time: datetime
    ) -> Optional[float]:
        """Get the rate closest to a target time."""
        rate = (
            db.query(FXRate.rate)
            .filter(FXRate.pair == pair)
            .filter(FXRate.timestamp <= target_time)
            .order_by(desc(FXRate.timestamp))
            .first()
        )
        return rate[0] if rate else None
    
    def get_latest_rates(self) -> List[FXRate]:
        """
        Get the most recent rate for each currency pair.
        
        Returns:
            List of latest FXRate records
        """
        db = self._get_db()
        
        # Subquery to get max timestamp per pair
        subquery = (
            db.query(
                FXRate.pair,
                func.max(FXRate.timestamp).label('max_ts')
            )
            .group_by(FXRate.pair)
            .subquery()
        )
        
        # Join to get full records
        rates = (
            db.query(FXRate)
            .join(subquery, and_(
                FXRate.pair == subquery.c.pair,
                FXRate.timestamp == subquery.c.max_ts
            ))
            .order_by(FXRate.pair)
            .all()
        )
        
        return rates
    
    def get_rate_history(
        self,
        pair: str,
        hours: int = 24
    ) -> List[FXRate]:
        """
        Get historical rates for a pair.
        
        Args:
            pair: Currency pair
            hours: Number of hours of history
            
        Returns:
            List of FXRate records ordered by timestamp
        """
        db = self._get_db()
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        return (
            db.query(FXRate)
            .filter(FXRate.pair == pair)
            .filter(FXRate.timestamp >= cutoff)
            .order_by(asc(FXRate.timestamp))
            .all()
        )
    
    def get_sparkline_data(
        self,
        pair: str,
        hours: int = 24
    ) -> List[float]:
        """
        Get sparkline data from stored history.
        
        Args:
            pair: Currency pair
            hours: Hours of history
            
        Returns:
            List of rate values for sparkline
        """
        history = self.get_rate_history(pair, hours)
        
        if not history:
            return []
        
        # Extract rates and generate sparkline
        rates = [(r.timestamp, r.rate) for r in history]
        return RateCalculator.generate_sparkline(rates, hours=hours)
    
    def get_rate_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all current rates for dashboard.
        
        Returns:
            Dictionary with rate summaries
        """
        db = self._get_db()
        rates = self.get_latest_rates()
        
        summary = {
            'rates': {},
            'timestamp': datetime.utcnow().isoformat(),
            'count': len(rates)
        }
        
        biggest_gain = None
        biggest_loss = None
        
        for rate in rates:
            rate_dict = {
                'rate': rate.rate,
                'change_1h': rate.change_1h,
                'change_24h': rate.change_24h,
                'change_1w': rate.change_1w,
                'change_ytd': rate.change_ytd,
                'timestamp': rate.timestamp.isoformat() if rate.timestamp else None,
                'sparkline': rate.sparkline_data or []
            }
            summary['rates'][rate.pair] = rate_dict
            
            # Track biggest movers (by 24h change)
            if rate.change_24h is not None:
                if biggest_gain is None or rate.change_24h > biggest_gain['change']:
                    biggest_gain = {'pair': rate.pair, 'change': rate.change_24h}
                if biggest_loss is None or rate.change_24h < biggest_loss['change']:
                    biggest_loss = {'pair': rate.pair, 'change': rate.change_24h}
        
        summary['biggest_gainer'] = biggest_gain
        summary['biggest_loser'] = biggest_loss
        
        return summary
    
    def cleanup_old_data(self, days: int = 90) -> int:
        """
        Remove data older than specified days.
        
        Args:
            days: Number of days to retain
            
        Returns:
            Number of records deleted
        """
        db = self._get_db()
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        deleted = (
            db.query(FXRate)
            .filter(FXRate.timestamp < cutoff)
            .delete()
        )
        
        db.commit()
        logger.info(f"Cleaned up {deleted} old FX rate records")
        return deleted


def store_fx_update(update: FXUpdate) -> List[FXRate]:
    """
    Convenience function to store FX update with context manager.
    
    Args:
        update: FXUpdate to store
        
    Returns:
        List of created FXRate records
    """
    with get_db_context() as db:
        storage = FXStorage(db)
        return storage.store_batch(update)


def get_latest_fx_rates() -> List[Dict[str, Any]]:
    """
    Convenience function to get latest rates.
    
    Returns:
        List of rate dictionaries
    """
    with get_db_context() as db:
        storage = FXStorage(db)
        rates = storage.get_latest_rates()
        return [
            {
                'pair': r.pair,
                'rate': r.rate,
                'change_1h': r.change_1h,
                'change_24h': r.change_24h,
                'change_1w': r.change_1w,
                'change_ytd': r.change_ytd,
                'timestamp': r.timestamp.isoformat() if r.timestamp else None,
                'sparkline': r.sparkline_data or []
            }
            for r in rates
        ]
