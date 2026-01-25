"""
Credit Spreads Storage Module

Handles database operations for credit spread data.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import desc, asc
from sqlalchemy.orm import Session
from loguru import logger

from ..data_storage.schema import CreditSpread
from ..data_storage.database import get_db_context
from .models import CreditSpreadData, CreditUpdate


class CreditStorage:
    """
    Database storage handler for credit spreads.
    """

    def __init__(self, db: Optional[Session] = None):
        self._db = db

    def _get_db(self) -> Session:
        if self._db:
            return self._db
        raise RuntimeError("No database session provided")

    def store_spread(self, spread_data: CreditSpreadData) -> CreditSpread:
        """
        Store a credit spread in the database.
        """
        db = self._get_db()

        credit_spread = CreditSpread(
            index_name=spread_data.index_name,
            spread_bps=spread_data.spread_bps,
            timestamp=spread_data.timestamp,
            percentile_90d=spread_data.percentile_90d,
            percentile_1y=spread_data.percentile_1y,
            avg_30d=spread_data.avg_30d,
            avg_90d=spread_data.avg_90d,
            change_1d=spread_data.change_1d,
            change_1w=spread_data.change_1w,
            fred_series=spread_data.fred_series,
            source=spread_data.source
        )

        db.add(credit_spread)
        db.commit()
        db.refresh(credit_spread)

        logger.debug(f"Stored credit spread: {spread_data.index_name}={spread_data.spread_bps} bps")
        return credit_spread

    def store_update(self, update: CreditUpdate) -> List[CreditSpread]:
        """
        Store a batch of credit spreads.
        """
        db = self._get_db()
        stored = []

        for spread in update.spreads:
            credit_spread = self.store_spread(spread)
            stored.append(credit_spread)

        logger.info(f"Stored {len(stored)} credit spreads")
        return stored

    def get_latest_spread(self, index_name: str) -> Optional[CreditSpread]:
        """Get the most recent spread for an index."""
        db = self._get_db()

        return (
            db.query(CreditSpread)
            .filter(CreditSpread.index_name == index_name)
            .order_by(desc(CreditSpread.timestamp))
            .first()
        )

    def get_all_latest_spreads(self) -> List[CreditSpread]:
        """Get the most recent spread for each index."""
        db = self._get_db()

        # Get latest timestamp for each index
        spreads = []
        for index_name in ['US_IG', 'US_BBB', 'US_HY', 'US_HY_CCC']:
            latest = self.get_latest_spread(index_name)
            if latest:
                spreads.append(latest)

        return spreads

    def get_spread_history(
        self,
        index_name: str,
        days: int = 90
    ) -> List[CreditSpread]:
        """Get spread history for an index."""
        db = self._get_db()
        cutoff = datetime.utcnow() - timedelta(days=days)

        return (
            db.query(CreditSpread)
            .filter(CreditSpread.index_name == index_name)
            .filter(CreditSpread.timestamp >= cutoff)
            .order_by(asc(CreditSpread.timestamp))
            .all()
        )

    def get_spread_series(
        self,
        index_name: str,
        days: int = 90
    ) -> List[Dict[str, Any]]:
        """Get spread history as list of dicts for charting."""
        history = self.get_spread_history(index_name, days)

        return [
            {
                'timestamp': spread.timestamp.isoformat(),
                'spread_bps': spread.spread_bps,
                'percentile_90d': spread.percentile_90d
            }
            for spread in history
        ]

    def cleanup_old_data(self, days: int = 90) -> int:
        """Remove data older than specified days."""
        db = self._get_db()
        cutoff = datetime.utcnow() - timedelta(days=days)

        deleted = (
            db.query(CreditSpread)
            .filter(CreditSpread.timestamp < cutoff)
            .delete()
        )

        db.commit()
        logger.info(f"Cleaned up {deleted} old credit spread records")
        return deleted


def store_credit_update(update: CreditUpdate) -> List[CreditSpread]:
    """Convenience function with context manager."""
    with get_db_context() as db:
        storage = CreditStorage(db)
        return storage.store_update(update)


def get_latest_credit_spreads() -> Optional[Dict[str, Any]]:
    """Get latest spreads as dictionary."""
    with get_db_context() as db:
        storage = CreditStorage(db)
        spreads = storage.get_all_latest_spreads()

        if not spreads:
            return None

        result = {
            'timestamp': datetime.utcnow().isoformat(),
            'spreads': {}
        }

        for spread in spreads:
            result['spreads'][spread.index_name] = {
                'spread_bps': spread.spread_bps,
                'percentile_90d': spread.percentile_90d,
                'percentile_1y': spread.percentile_1y,
                'avg_30d': spread.avg_30d,
                'avg_90d': spread.avg_90d,
                'change_1d': spread.change_1d,
                'change_1w': spread.change_1w,
                'timestamp': spread.timestamp.isoformat()
            }

        return result