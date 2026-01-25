"""
Yields Data Fetcher

Fetches Treasury yield data from FRED API.
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

from .config import YIELD_SERIES, TIPS_SERIES, INTERNATIONAL_YIELDS, get_fred_series_ids
from .models import YieldCurveData


class YieldsDataFetcher:
    """
    Fetches Treasury yield data from FRED API.
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
            series_id: FRED series ID (e.g., 'DGS10')
            start_date: Optional start date
            end_date: Optional end date
            
        Returns:
            Latest yield value or None
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
        if not self.fred:
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
    
    def fetch_yield_curve(self) -> Optional[YieldCurveData]:
        """
        Fetch complete US Treasury yield curve.
        
        Returns:
            YieldCurveData with all tenors
        """
        if not self.fred:
            logger.error("FRED client not available")
            return None
        
        logger.info("Fetching US Treasury yield curve from FRED...")
        
        # Fetch all tenors
        curve_data = {}
        for tenor, config in YIELD_SERIES.items():
            value = self.fetch_series(config['fred_id'])
            if value is not None:
                curve_data[tenor] = value
                logger.debug(f"  {tenor}: {value}%")
            else:
                logger.warning(f"  {tenor}: No data")
        
        if not curve_data:
            logger.error("No yield data fetched")
            return None
        
        # Fetch TIPS
        tips_data = {}
        for name, config in TIPS_SERIES.items():
            value = self.fetch_series(config['fred_id'])
            if value is not None:
                tips_data[name] = value
        
        # Create YieldCurveData
        yield_curve = YieldCurveData(
            country='US',
            timestamp=datetime.utcnow(),
            source='fred',
            tenor_1m=curve_data.get('1M'),
            tenor_3m=curve_data.get('3M'),
            tenor_6m=curve_data.get('6M'),
            tenor_1y=curve_data.get('1Y'),
            tenor_2y=curve_data.get('2Y'),
            tenor_5y=curve_data.get('5Y'),
            tenor_10y=curve_data.get('10Y'),
            tenor_20y=curve_data.get('20Y'),
            tenor_30y=curve_data.get('30Y'),
            tips_5y=tips_data.get('5Y_TIPS'),
            tips_10y=tips_data.get('10Y_TIPS'),
        )
        
        # Calculate spreads
        yield_curve.calculate_spreads()
        
        logger.info(f"Fetched yield curve: 10Y={yield_curve.tenor_10y}%, "
                   f"2Y={yield_curve.tenor_2y}%, "
                   f"10Y-2Y spread={yield_curve.spread_10y2y}%")
        
        return yield_curve
    
    def fetch_international_yields(self) -> Dict[str, float]:
        """
        Fetch international sovereign yields.
        
        Returns:
            Dictionary of country/tenor -> yield
        """
        if not self.fred:
            return {}
        
        yields = {}
        for name, config in INTERNATIONAL_YIELDS.items():
            value = self.fetch_series(config['fred_id'])
            if value is not None:
                yields[name] = value
        
        return yields
    
    def check_api_status(self) -> Dict[str, Any]:
        """Check FRED API status."""
        status = {
            'available': FRED_AVAILABLE,
            'configured': bool(self.api_key),
            'connected': False
        }
        
        if self.fred:
            try:
                # Try to fetch a simple series to test connection
                test = self.fetch_series('DGS10')
                status['connected'] = test is not None
            except Exception as e:
                status['error'] = str(e)
        
        return status


# Add pandas import for history function
try:
    import pandas as pd
except ImportError:
    pd = None
