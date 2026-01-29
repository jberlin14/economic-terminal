"""
Credit Spreads Data Fetcher

Fetches ICE BofA credit spread indices from FRED API.
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from loguru import logger

try:
    from fredapi import Fred
    FRED_AVAILABLE = True
except ImportError:
    FRED_AVAILABLE = False
    logger.warning("fredapi not installed. Run: pip install fredapi")

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logger.warning("pandas not installed. Run: pip install pandas")

from .models import CreditSpreadData, CreditUpdate


# ICE BofA Credit Spread Indices
CREDIT_INDICES = {
    'US_IG': {
        'fred_id': 'BAMLC0A0CM',
        'name': 'US Investment Grade',
        'description': 'ICE BofA US Corporate Index Option-Adjusted Spread'
    },
    'US_BBB': {
        'fred_id': 'BAMLC0A4CBBB',
        'name': 'US BBB Corporate',
        'description': 'ICE BofA BBB US Corporate Index Option-Adjusted Spread'
    },
    'US_HY': {
        'fred_id': 'BAMLH0A0HYM2',
        'name': 'US High Yield',
        'description': 'ICE BofA US High Yield Index Option-Adjusted Spread'
    },
    'US_HY_CCC': {
        'fred_id': 'BAMLH0A3HYC',
        'name': 'US CCC & Below',
        'description': 'ICE BofA CCC & Below US High Yield Index Option-Adjusted Spread'
    }
}


class CreditDataFetcher:
    """
    Fetches credit spread data from FRED API.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('FRED_API_KEY', '')
        self._fred = None

        if not FRED_AVAILABLE:
            logger.error("fredapi package not installed")
        elif not self.api_key:
            logger.warning("FRED API key not configured")

    @property
    def fred(self) -> Optional['Fred']:
        """Get or create FRED client."""
        if not FRED_AVAILABLE:
            return None

        if self._fred is None and self.api_key:
            self._fred = Fred(api_key=self.api_key)

        return self._fred

    def fetch_series(
        self,
        series_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Optional[float]:
        """
        Fetch the latest value for a FRED series.

        Args:
            series_id: FRED series ID (e.g., 'BAMLC0A0CM')
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            Latest spread value in basis points or None
        """
        if not self.fred:
            return None

        try:
            # Get recent data (last 30 days to ensure we get something)
            if start_date is None:
                start_date = datetime.now() - timedelta(days=30)

            data = self.fred.get_series(
                series_id,
                observation_start=start_date,
                observation_end=end_date
            )

            if data.empty:
                logger.warning(f"No data returned for {series_id}")
                return None

            # Get the most recent non-null value
            latest = data.dropna().iloc[-1]
            return float(latest)

        except Exception as e:
            logger.error(f"Error fetching FRED series {series_id}: {e}")
            return None

    def fetch_series_history(
        self,
        series_id: str,
        days: int = 365
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical data for a FRED series.

        Args:
            series_id: FRED series ID
            days: Number of days of history

        Returns:
            List of {date, value} dictionaries
        """
        if not self.fred or not PANDAS_AVAILABLE:
            return []

        try:
            start_date = datetime.now() - timedelta(days=days)
            data = self.fred.get_series(series_id, observation_start=start_date)

            if data.empty:
                return []

            history = []
            for date, value in data.items():
                if not pd.isna(value):
                    history.append({
                        'date': date.to_pydatetime(),
                        'value': float(value)
                    })

            return history

        except Exception as e:
            logger.error(f"Error fetching history for {series_id}: {e}")
            return []

    def calculate_percentile(
        self,
        current_value: float,
        history: List[Dict[str, Any]]
    ) -> Optional[float]:
        """
        Calculate percentile rank of current value vs historical data.

        Args:
            current_value: Current spread value
            history: List of historical {date, value} dicts

        Returns:
            Percentile rank (0-100) or None
        """
        if not history or not PANDAS_AVAILABLE:
            return None

        try:
            values = [h['value'] for h in history]
            values.append(current_value)

            # Calculate percentile rank
            series = pd.Series(values)
            percentile = (series < current_value).sum() / len(series) * 100

            return round(percentile, 1)

        except Exception as e:
            logger.error(f"Error calculating percentile: {e}")
            return None

    def fetch_all_spreads(self) -> Optional[CreditUpdate]:
        """
        Fetch all credit spread indices.

        Returns:
            CreditUpdate with all spreads and calculated metrics
        """
        if not self.fred:
            logger.error("FRED client not available")
            return None

        logger.info("Fetching credit spreads from FRED...")

        spreads = []
        errors = []

        for index_name, config in CREDIT_INDICES.items():
            try:
                # Fetch current value (FRED returns OAS in percentage points)
                raw_value = self.fetch_series(config['fred_id'])

                if raw_value is None:
                    errors.append(f"No data for {index_name}")
                    continue

                # Convert from percentage points to basis points (1% = 100 bps)
                current_value = round(raw_value * 100, 2)

                # Fetch 90-day history for percentile calculation
                history_90d = self.fetch_series_history(config['fred_id'], days=90)

                # Convert history to bps too
                history_bps = [{'date': h['date'], 'value': h['value'] * 100} for h in history_90d] if history_90d else []

                # Calculate percentile
                percentile_90d = None
                if history_bps:
                    percentile_90d = self.calculate_percentile(current_value, history_bps)

                # Calculate 90-day average
                avg_90d = None
                if history_bps:
                    values = [h['value'] for h in history_bps]
                    avg_90d = round(sum(values) / len(values), 2)

                # Calculate 1-day change
                change_1d = None
                if len(history_bps) >= 2:
                    yesterday_value = history_bps[-2]['value']
                    change_1d = round(current_value - yesterday_value, 2)

                # Create spread data
                spread_data = CreditSpreadData(
                    index_name=index_name,
                    spread_bps=current_value,
                    timestamp=datetime.utcnow(),
                    source='fred',
                    fred_series=config['fred_id'],
                    percentile_90d=percentile_90d,
                    avg_90d=avg_90d,
                    change_1d=change_1d
                )

                spreads.append(spread_data)
                logger.debug(f"  {index_name}: {current_value} bps (p90d: {percentile_90d})")

            except Exception as e:
                logger.error(f"Error fetching {index_name}: {e}")
                errors.append(f"{index_name}: {str(e)}")

        if not spreads:
            logger.error("No credit spread data fetched")
            return None

        update = CreditUpdate(
            spreads=spreads,
            timestamp=datetime.utcnow(),
            source='fred',
            success=len(errors) == 0,
            errors=errors
        )

        logger.info(f"Fetched {len(spreads)} credit spreads")
        return update

    def check_api_status(self) -> Dict[str, Any]:
        """Check FRED API status."""
        status = {
            'available': FRED_AVAILABLE,
            'configured': bool(self.api_key),
            'connected': False,
            'pandas_available': PANDAS_AVAILABLE
        }

        if self.fred:
            try:
                # Try to fetch a simple series to test connection
                test = self.fetch_series('BAMLC0A0CM')
                status['connected'] = test is not None
            except Exception as e:
                status['error'] = str(e)

        return status