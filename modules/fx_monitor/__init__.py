"""
FX Monitor Module - Currency Rate Tracking

This module provides:
- Real-time FX rate fetching from multiple sources
- USD/XXX convention standardization
- Change percentage calculations
- Sparkline data generation
- Risk detection for large moves

Primary data source: Alpha Vantage (free tier)
Fallback: Yahoo Finance (yfinance)
"""

from .config import FX_PAIRS, RISK_THRESHOLDS
from .data_fetcher import FXDataFetcher
from .rate_calculator import RateCalculator
from .models import FXRateData, FXUpdate
from .storage import FXStorage

__all__ = [
    'FX_PAIRS',
    'RISK_THRESHOLDS',
    'FXDataFetcher',
    'RateCalculator',
    'FXRateData',
    'FXUpdate',
    'FXStorage'
]
