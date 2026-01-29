"""
Economic Calendar Storage

Stores consensus estimates and historical release data.
"""

from datetime import date, datetime
from typing import Optional, Dict, List, Any
from sqlalchemy.orm import Session
from loguru import logger


class CalendarStorage:
    """
    Handles storage and retrieval of calendar data.

    For now, uses in-memory storage. Can be extended to use database.
    """

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self._consensus_cache: Dict[str, Dict[str, Any]] = {}

    def set_consensus(self, release_id: str, release_date: date, estimate: float, source: str = "manual"):
        """
        Set consensus estimate for a release.

        Args:
            release_id: Release identifier
            release_date: Date of the release
            estimate: Consensus estimate value
            source: Source of the estimate (manual, bloomberg, etc.)
        """
        key = f"{release_id}_{release_date.isoformat()}"
        self._consensus_cache[key] = {
            "release_id": release_id,
            "release_date": release_date.isoformat(),
            "estimate": estimate,
            "source": source,
            "updated_at": datetime.now().isoformat()
        }
        logger.info(f"Set consensus for {release_id} on {release_date}: {estimate}")

    def get_consensus(self, release_id: str, release_date: date) -> Optional[float]:
        """Get consensus estimate for a release."""
        key = f"{release_id}_{release_date.isoformat()}"
        data = self._consensus_cache.get(key)
        return data["estimate"] if data else None

    def get_all_consensus(self) -> List[Dict[str, Any]]:
        """Get all stored consensus estimates."""
        return list(self._consensus_cache.values())

    def calculate_surprise(self, actual: float, consensus: float) -> Dict[str, float]:
        """
        Calculate surprise metrics.

        Returns:
            {
                "surprise": actual - consensus,
                "surprise_percent": percentage difference
            }
        """
        surprise = actual - consensus
        surprise_percent = (surprise / abs(consensus)) * 100 if consensus != 0 else 0

        return {
            "surprise": round(surprise, 4),
            "surprise_percent": round(surprise_percent, 2)
        }
