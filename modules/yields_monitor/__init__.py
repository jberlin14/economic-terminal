"""
Yields Monitor Module - Treasury Yield Curve Tracking

This module provides:
- FRED API integration for Treasury yields
- Yield curve construction and visualization
- Spread calculations (10Y-2Y, 10Y-3M)
- Inversion detection and alerts

Data source: FRED (Federal Reserve Economic Data)
"""

from .config import YIELD_SERIES, SPREAD_THRESHOLDS
from .data_fetcher import YieldsDataFetcher
from .curve_builder import CurveBuilder
from .models import YieldCurveData, YieldSpread
from .storage import YieldsStorage

__all__ = [
    'YIELD_SERIES',
    'SPREAD_THRESHOLDS',
    'YieldsDataFetcher',
    'CurveBuilder',
    'YieldCurveData',
    'YieldSpread',
    'YieldsStorage'
]
