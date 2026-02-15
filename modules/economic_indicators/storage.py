"""
Economic Indicators Storage

Handles database operations for indicator data.
"""

from datetime import datetime, date, timedelta
from typing import List, Optional, Dict
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from loguru import logger

from ..data_storage.schema import EconomicIndicator, IndicatorValue
from ..data_storage.database import get_db_context
from ..utils.timezone import get_current_time
from .config import get_all_indicators
from .data_fetcher import IndicatorDataFetcher
from .transformer import DataTransformer


class IndicatorStorage:
    """
    Manages economic indicator storage and retrieval.
    """

    def __init__(self, db: Optional[Session] = None):
        self._db = db
        self.transformer = DataTransformer()

    def _get_db(self) -> Session:
        if self._db:
            return self._db
        raise RuntimeError("No database session")

    # ==================== Indicator Metadata ====================

    def initialize_indicators(self) -> int:
        """
        Initialize the economic_indicators table with all configured series.
        Call this once on setup.
        """
        db = self._get_db()
        all_indicators = get_all_indicators()
        count = 0

        for series_id, config in all_indicators.items():
            existing = db.query(EconomicIndicator).filter(
                EconomicIndicator.series_id == series_id
            ).first()

            if not existing:
                indicator = EconomicIndicator(
                    series_id=series_id,
                    name=config['name'],
                    report_group=config['report_group'],
                    category=config['category'],
                    units=config.get('units', ''),
                    frequency=config.get('frequency', 'monthly'),
                )
                db.add(indicator)
                count += 1

        db.commit()
        logger.info(f"Initialized {count} new indicators")
        return count

    def get_all_indicators(self) -> List[EconomicIndicator]:
        """Get all indicator metadata"""
        db = self._get_db()
        return db.query(EconomicIndicator).order_by(
            EconomicIndicator.report_group,
            EconomicIndicator.name
        ).all()

    def get_indicator(self, series_id: str) -> Optional[EconomicIndicator]:
        """Get single indicator metadata"""
        db = self._get_db()
        return db.query(EconomicIndicator).filter(
            EconomicIndicator.series_id == series_id
        ).first()

    def get_indicators_by_report(self, report_group: str) -> List[EconomicIndicator]:
        """Get all indicators for a report group"""
        db = self._get_db()
        return db.query(EconomicIndicator).filter(
            EconomicIndicator.report_group == report_group
        ).order_by(EconomicIndicator.name).all()

    def search_indicators(self, query: str) -> List[EconomicIndicator]:
        """Search indicators by name or series ID"""
        db = self._get_db()
        search = f"%{query}%"
        return db.query(EconomicIndicator).filter(
            (EconomicIndicator.name.ilike(search)) |
            (EconomicIndicator.series_id.ilike(search))
        ).order_by(EconomicIndicator.name).all()

    # ==================== Indicator Values ====================

    def store_values(self, series_id: str, df: pd.DataFrame, update_revised: bool = False):
        """
        Store historical values for a series.
        Handles duplicates by skipping existing dates (or updating if revised).

        Returns:
            tuple(new_count, revised_count) if update_revised=True, else int(new_count)
        """
        db = self._get_db()
        new_count = 0
        revised_count = 0

        for _, row in df.iterrows():
            # Check if exists
            existing = db.query(IndicatorValue).filter(
                and_(
                    IndicatorValue.series_id == series_id,
                    IndicatorValue.date == row['date']
                )
            ).first()

            if not existing:
                value = IndicatorValue(
                    series_id=series_id,
                    date=row['date'],
                    value=float(row['value'])
                )
                db.add(value)
                new_count += 1
            elif update_revised and abs(existing.value - float(row['value'])) > 1e-6:
                # FRED revised this data point — update it
                existing.value = float(row['value'])
                revised_count += 1

        db.commit()

        # Update indicator metadata
        if new_count > 0 or revised_count > 0:
            self._update_indicator_latest(series_id)

        if update_revised:
            return new_count, revised_count
        return new_count

    def _update_indicator_latest(self, series_id: str):
        """Update the latest value in indicator metadata"""
        db = self._get_db()

        latest = db.query(IndicatorValue).filter(
            IndicatorValue.series_id == series_id
        ).order_by(IndicatorValue.date.desc()).first()

        if latest:
            indicator = db.query(EconomicIndicator).filter(
                EconomicIndicator.series_id == series_id
            ).first()

            if indicator:
                indicator.latest_value = latest.value
                indicator.latest_date = latest.date
                indicator.last_updated = get_current_time()
                db.commit()

    def get_values(
        self,
        series_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """
        Get historical values for a series.

        Returns DataFrame with 'date' and 'value' columns.
        """
        db = self._get_db()

        query = db.query(IndicatorValue).filter(
            IndicatorValue.series_id == series_id
        )

        if start_date:
            query = query.filter(IndicatorValue.date >= start_date)
        if end_date:
            query = query.filter(IndicatorValue.date <= end_date)

        results = query.order_by(IndicatorValue.date.asc()).all()

        if not results:
            return pd.DataFrame(columns=['date', 'value'])

        data = [{'date': r.date, 'value': r.value} for r in results]
        return pd.DataFrame(data)

    def get_latest_value(self, series_id: str) -> Optional[Dict]:
        """Get most recent value for a series"""
        db = self._get_db()

        latest = db.query(IndicatorValue).filter(
            IndicatorValue.series_id == series_id
        ).order_by(IndicatorValue.date.desc()).first()

        if not latest:
            return None

        return {
            'series_id': series_id,
            'date': latest.date.isoformat(),
            'value': latest.value
        }

    @staticmethod
    def _lookback_days(transformations: List[str], frequency: str = 'monthly') -> int:
        """Calculate extra days of data needed before start_date for transforms."""
        days = 0
        for t in transformations:
            if t.startswith('yoy'):
                # Need 12+ months of prior data for YoY on monthly series
                freq_days = {
                    'daily': 370, 'weekly': 380, 'monthly': 400, 'quarterly': 400
                }
                days = max(days, freq_days.get(frequency, 400))
            elif t.startswith('mom'):
                days = max(days, 35)  # 1 extra month
            elif t.startswith('ma_'):
                try:
                    periods = int(t.split('_')[1])
                    # Estimate days based on frequency
                    freq_mult = {'daily': 1, 'weekly': 7, 'monthly': 31, 'quarterly': 92}
                    days = max(days, periods * freq_mult.get(frequency, 31) + 10)
                except ValueError:
                    pass
            elif t == 'annualized':
                days = max(days, 35)
        return days

    def get_values_with_transforms(
        self,
        series_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        transformations: List[str] = None
    ) -> pd.DataFrame:
        """Get values with calculated transformations."""
        if not transformations:
            return self.get_values(series_id, start_date, end_date)

        # Get frequency for YoY calculations
        indicator = self.get_indicator(series_id)
        frequency = indicator.frequency if indicator else 'monthly'

        # Fetch extra lookback data so transforms don't start with NaN
        lookback = self._lookback_days(transformations, frequency)
        fetch_start = (start_date - timedelta(days=lookback)) if start_date and lookback else start_date

        df = self.get_values(series_id, fetch_start, end_date)
        if df.empty:
            return df

        df = self.transformer.transform(df, transformations, frequency)

        # Trim back to originally requested date range
        if start_date and lookback:
            df = df[df['date'] >= start_date].reset_index(drop=True)

        return df

    def get_comparison_data(
        self,
        series_ids: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        transform: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get multiple series aligned for comparison.
        Returns DataFrame with date index and one column per series.
        """
        logger.info(f"get_comparison_data called with series: {series_ids}, start: {start_date}, end: {end_date}, transform: {transform}")
        all_data = {}

        for series_id in series_ids:
            # Check if indicator exists
            indicator = self.get_indicator(series_id)
            if not indicator:
                logger.warning(f"Indicator {series_id} not found in database")
                continue

            frequency = indicator.frequency if indicator else 'monthly'

            # Fetch extra lookback data so transforms don't start with NaN
            fetch_start = start_date
            lookback = 0
            if transform and start_date:
                lookback = self._lookback_days([transform], frequency)
                fetch_start = start_date - timedelta(days=lookback) if lookback else start_date

            logger.debug(f"Fetching data for {series_id}")
            df = self.get_values(series_id, fetch_start, end_date)
            logger.debug(f"Retrieved {len(df)} rows for {series_id}")

            if not df.empty:
                if transform:
                    logger.debug(f"Applying transform '{transform}' to {series_id} (frequency: {frequency})")
                    df = self.transformer.transform(df, [transform], frequency)

                    # Use transformed column
                    if transform in df.columns:
                        df['value'] = df[transform]
                    else:
                        logger.warning(f"Transform column '{transform}' not found in DataFrame for {series_id}")

                # Trim back to originally requested date range
                if lookback and start_date:
                    df = df[df['date'] >= start_date]

                df = df.set_index('date')
                all_data[series_id] = df['value']
                logger.debug(f"Added {series_id} to comparison with {len(df)} data points")
            else:
                logger.warning(f"No data found for series {series_id} in date range {start_date} to {end_date}")

        if not all_data:
            logger.error(f"No data available for any of the series: {series_ids}")
            return pd.DataFrame()

        result = pd.DataFrame(all_data)
        result = result.sort_index()
        logger.info(f"Comparison result: {len(result)} rows, {len(result.columns)} series")
        return result

    def get_value_count(self, series_id: str) -> int:
        """Get number of stored values for a series"""
        db = self._get_db()
        return db.query(func.count(IndicatorValue.id)).filter(
            IndicatorValue.series_id == series_id
        ).scalar()

    def get_date_range(self, series_id: str) -> Optional[Dict]:
        """Get the date range of stored data for a series"""
        db = self._get_db()

        result = db.query(
            func.min(IndicatorValue.date),
            func.max(IndicatorValue.date)
        ).filter(IndicatorValue.series_id == series_id).first()

        if result and result[0]:
            return {
                'start_date': result[0],
                'end_date': result[1]
            }
        return None


def fetch_and_store_all_indicators(years_back: int = 10, progress_callback=None) -> Dict:
    """
    Convenience function to fetch and store all indicators.
    Used by initialization script.

    Returns:
        {'fetched': 75, 'stored': 75, 'errors': ['SERIES1', 'SERIES2']}
    """
    fetcher = IndicatorDataFetcher()

    if not fetcher.is_available():
        logger.error("FRED API not available")
        return {'fetched': 0, 'stored': 0, 'errors': ['FRED_UNAVAILABLE']}

    results = {'fetched': 0, 'stored': 0, 'errors': []}
    all_indicators = get_all_indicators()
    total = len(all_indicators)

    with get_db_context() as db:
        storage = IndicatorStorage(db)

        # Initialize indicator metadata
        storage.initialize_indicators()

        for i, (series_id, config) in enumerate(all_indicators.items()):
            if progress_callback:
                progress_callback(i + 1, total, series_id, config['name'])

            try:
                df = fetcher.fetch_series(series_id, years_back=years_back)

                if df is not None and not df.empty:
                    results['fetched'] += 1
                    count = storage.store_values(series_id, df)
                    if count > 0:
                        results['stored'] += 1
                        logger.debug(f"Stored {count} values for {series_id}")
                else:
                    results['errors'].append(series_id)

            except Exception as e:
                logger.error(f"Error processing {series_id}: {e}")
                results['errors'].append(series_id)

    return results
