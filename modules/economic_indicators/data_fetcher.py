"""
Economic Indicators Data Fetcher

Fetches historical data from FRED API.
"""

import os
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import pandas as pd
from loguru import logger

try:
    from fredapi import Fred
    FRED_AVAILABLE = True
except ImportError:
    FRED_AVAILABLE = False
    logger.warning("fredapi not installed")

from .config import get_all_indicators


class IndicatorDataFetcher:
    """
    Fetches economic indicator data from FRED.
    Handles rate limiting (120 requests/minute).
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('FRED_API_KEY')
        self._fred = None
        self._request_count = 0
        self._last_request_time = None

        if FRED_AVAILABLE and self.api_key:
            try:
                self._fred = Fred(api_key=self.api_key)
                logger.info("FRED client initialized for indicators")
            except Exception as e:
                logger.error(f"Failed to initialize FRED: {e}")

    def is_available(self) -> bool:
        return self._fred is not None

    def _rate_limit(self):
        """Ensure we don't exceed 120 requests/minute"""
        self._request_count += 1

        if self._request_count >= 100:
            if self._last_request_time:
                elapsed = (datetime.now() - self._last_request_time).total_seconds()
                if elapsed < 60:
                    sleep_time = 60 - elapsed + 1
                    logger.info(f"Rate limiting: sleeping {sleep_time:.0f}s")
                    time.sleep(sleep_time)
            self._request_count = 0
            self._last_request_time = datetime.now()

    def fetch_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        years_back: int = 10
    ) -> Optional[pd.DataFrame]:
        """
        Fetch a single series from FRED.

        Args:
            series_id: FRED series ID (e.g., 'PAYEMS')
            start_date: Start date (YYYY-MM-DD), defaults to years_back from today
            end_date: End date (YYYY-MM-DD), defaults to today
            years_back: Years of history if start_date not specified

        Returns:
            DataFrame with 'date' and 'value' columns, or None if failed
        """
        if not self.is_available():
            logger.error("FRED not available")
            return None

        self._rate_limit()

        if not start_date:
            start_date = (datetime.now() - timedelta(days=years_back*365)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        try:
            data = self._fred.get_series(
                series_id,
                observation_start=start_date,
                observation_end=end_date
            )

            if data is None or data.empty:
                logger.warning(f"No data for {series_id}")
                return None

            # Convert to DataFrame
            df = data.reset_index()
            df.columns = ['date', 'value']
            df['date'] = pd.to_datetime(df['date']).dt.date
            df = df.dropna()

            logger.debug(f"Fetched {len(df)} rows for {series_id}")
            return df

        except Exception as e:
            logger.error(f"Error fetching {series_id}: {e}")
            return None

    def fetch_series_info(self, series_id: str) -> Optional[Dict]:
        """Fetch metadata about a series from FRED"""
        if not self.is_available():
            return None

        self._rate_limit()

        try:
            info = self._fred.get_series_info(series_id)
            return {
                'series_id': series_id,
                'title': info.get('title', ''),
                'units': info.get('units', ''),
                'frequency': info.get('frequency', ''),
                'seasonal_adjustment': info.get('seasonal_adjustment', ''),
                'last_updated': info.get('last_updated', ''),
            }
        except Exception as e:
            logger.error(f"Error fetching info for {series_id}: {e}")
            return None

    def fetch_latest_value(self, series_id: str) -> Optional[Dict]:
        """Fetch just the most recent value for a series"""
        df = self.fetch_series(series_id, years_back=1)

        if df is None or df.empty:
            return None

        latest = df.iloc[-1]
        return {
            'series_id': series_id,
            'date': latest['date'],
            'value': float(latest['value'])
        }

    def fetch_multiple_series(
        self,
        series_ids: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        years_back: int = 10,
        progress_callback=None
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch multiple series with progress tracking.

        Args:
            series_ids: List of FRED series IDs
            progress_callback: Optional function(current, total, series_id) for progress

        Returns:
            Dict mapping series_id to DataFrame
        """
        results = {}
        total = len(series_ids)

        for i, series_id in enumerate(series_ids):
            if progress_callback:
                progress_callback(i + 1, total, series_id)

            df = self.fetch_series(series_id, start_date, end_date, years_back)
            if df is not None:
                results[series_id] = df

            # Small delay to be nice to FRED
            time.sleep(0.1)

        logger.info(f"Fetched {len(results)}/{total} series successfully")
        return results

    def fetch_all_indicators(
        self,
        years_back: int = 10,
        progress_callback=None
    ) -> Dict[str, pd.DataFrame]:
        """Fetch all configured indicators"""
        all_indicators = get_all_indicators()
        series_ids = list(all_indicators.keys())

        return self.fetch_multiple_series(
            series_ids,
            years_back=years_back,
            progress_callback=progress_callback
        )
