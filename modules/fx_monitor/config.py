"""
FX Monitor Configuration

Defines currency pairs, update intervals, and risk thresholds.
All rates are displayed as USD/XXX (how many units of foreign currency per 1 USD).
"""

import os
from typing import Dict, Any

# =============================================================================
# API CONFIGURATION
# =============================================================================

ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_KEY', '')
UPDATE_INTERVAL = int(os.getenv('FX_UPDATE_INTERVAL', 300))  # 5 minutes default

# Alpha Vantage rate limits: 500 calls/day on free tier
# With 11 pairs, we can update every ~3 minutes during 16 trading hours
MAX_DAILY_CALLS = 500

# =============================================================================
# CURRENCY PAIRS CONFIGURATION
# =============================================================================

# All pairs standardized to USD/XXX convention
# 'invert': True means market quotes as XXX/USD (need to calculate 1/rate)
# 'invert': False means market quotes as USD/XXX (use directly)

FX_PAIRS: Dict[str, Dict[str, Any]] = {
    # G10 Currencies
    'USD/EUR': {
        'source_pair': 'EUR/USD',
        'invert': True,
        'alpha_vantage': 'EUR',
        'yahoo': 'EURUSD=X',
        'priority': 1,  # Based on Jake's country hierarchy
        'description': 'US Dollar / Euro'
    },
    'USD/GBP': {
        'source_pair': 'GBP/USD',
        'invert': True,
        'alpha_vantage': 'GBP',
        'yahoo': 'GBPUSD=X',
        'priority': 8,
        'description': 'US Dollar / British Pound'
    },
    'USD/JPY': {
        'source_pair': 'USD/JPY',
        'invert': False,
        'alpha_vantage': 'JPY',
        'yahoo': 'JPY=X',
        'priority': 2,
        'description': 'US Dollar / Japanese Yen'
    },
    'USD/CAD': {
        'source_pair': 'USD/CAD',
        'invert': False,
        'alpha_vantage': 'CAD',
        'yahoo': 'CAD=X',
        'priority': 3,
        'description': 'US Dollar / Canadian Dollar'
    },
    'USD/AUD': {
        'source_pair': 'AUD/USD',
        'invert': True,
        'alpha_vantage': 'AUD',
        'yahoo': 'AUDUSD=X',
        'priority': 9,
        'description': 'US Dollar / Australian Dollar'
    },
    'USD/NZD': {
        'source_pair': 'NZD/USD',
        'invert': True,
        'alpha_vantage': 'NZD',
        'yahoo': 'NZDUSD=X',
        'priority': 10,
        'description': 'US Dollar / New Zealand Dollar'
    },
    
    # Americas (Emerging)
    'USD/MXN': {
        'source_pair': 'USD/MXN',
        'invert': False,
        'alpha_vantage': 'MXN',
        'yahoo': 'MXN=X',
        'priority': 4,
        'description': 'US Dollar / Mexican Peso'
    },
    'USD/BRL': {
        'source_pair': 'USD/BRL',
        'invert': False,
        'alpha_vantage': 'BRL',
        'yahoo': 'BRL=X',
        'priority': 6,
        'description': 'US Dollar / Brazilian Real'
    },
    'USD/ARS': {
        'source_pair': 'USD/ARS',
        'invert': False,
        'alpha_vantage': 'ARS',
        'yahoo': 'ARS=X',
        'priority': 7,
        'description': 'US Dollar / Argentine Peso'
    },
    
    # Asia (Emerging)
    'USD/TWD': {
        'source_pair': 'USD/TWD',
        'invert': False,
        'alpha_vantage': 'TWD',
        'yahoo': 'TWD=X',
        'priority': 11,
        'description': 'US Dollar / Taiwan Dollar'
    },
}

# Dollar Index (DXY) - special handling
DXY_CONFIG = {
    'name': 'USDX',
    'description': 'US Dollar Index (DXY)',
    'yahoo': 'DX-Y.NYB',
    'priority': 0,  # Always show first
}

# =============================================================================
# RISK THRESHOLDS
# =============================================================================

RISK_THRESHOLDS = {
    # FX move thresholds (1-hour percentage change)
    'FX_HIGH': float(os.getenv('FX_RISK_THRESHOLD_HIGH', 1.0)),
    'FX_CRITICAL': float(os.getenv('FX_RISK_THRESHOLD_CRITICAL', 2.0)),
    
    # Specific currency thresholds (some are more volatile)
    'ARS_HIGH': 3.0,    # Argentine Peso is more volatile
    'ARS_CRITICAL': 5.0,
    'BRL_HIGH': 1.5,
    'BRL_CRITICAL': 3.0,
}

# =============================================================================
# DATA STORAGE SETTINGS
# =============================================================================

# Sparkline configuration
SPARKLINE_HOURS = 24          # Hours of history for sparkline
SPARKLINE_INTERVAL = 15       # Minutes between sparkline points
SPARKLINE_POINTS = SPARKLINE_HOURS * 60 // SPARKLINE_INTERVAL  # 96 points

# Historical data retention
HISTORY_DAYS = 90             # Days of detailed data to retain

# =============================================================================
# MARKET HOURS
# =============================================================================

# FX market is 24/5: Sunday 5 PM ET to Friday 5 PM ET
MARKET_OPEN_HOUR = 17         # 5 PM ET Sunday
MARKET_CLOSE_HOUR = 17        # 5 PM ET Friday
MARKET_TIMEZONE = 'America/New_York'

# =============================================================================
# COUNTRY PRIORITY MAPPING (for alert routing)
# =============================================================================

COUNTRY_PRIORITY = {
    'US': 1,
    'JP': 2,
    'CA': 3,
    'MX': 4,
    'EU': 5,
    'BR': 6,
    'AR': 7,
    'GB': 8,
    'AU': 9,
    'NZ': 10,
    'TW': 11,
}

# Map currency codes to countries
CURRENCY_TO_COUNTRY = {
    'EUR': 'EU',
    'GBP': 'GB',
    'JPY': 'JP',
    'CAD': 'CA',
    'AUD': 'AU',
    'NZD': 'NZ',
    'MXN': 'MX',
    'BRL': 'BR',
    'ARS': 'AR',
    'TWD': 'TW',
}

# =============================================================================
# DISPLAY FORMATTING
# =============================================================================

# Decimal places for display
DECIMAL_PLACES = {
    'USD/EUR': 4,
    'USD/GBP': 4,
    'USD/JPY': 2,
    'USD/CAD': 4,
    'USD/AUD': 4,
    'USD/NZD': 4,
    'USD/MXN': 4,
    'USD/BRL': 4,
    'USD/ARS': 2,
    'USD/TWD': 3,
    'USDX': 3,
}


def get_all_pairs() -> list:
    """Get list of all configured FX pairs including DXY."""
    pairs = list(FX_PAIRS.keys())
    pairs.insert(0, 'USDX')  # DXY first
    return pairs


def get_pair_config(pair: str) -> dict:
    """Get configuration for a specific pair."""
    if pair == 'USDX':
        return DXY_CONFIG
    return FX_PAIRS.get(pair, {})


def get_decimal_places(pair: str) -> int:
    """Get decimal places for formatting a pair."""
    return DECIMAL_PLACES.get(pair, 4)


def get_risk_threshold(pair: str, level: str = 'HIGH') -> float:
    """Get risk threshold for a specific pair."""
    # Check for pair-specific threshold
    currency = pair.split('/')[1] if '/' in pair else pair
    specific_key = f"{currency}_{level}"
    
    if specific_key in RISK_THRESHOLDS:
        return RISK_THRESHOLDS[specific_key]
    
    # Fall back to default
    return RISK_THRESHOLDS.get(f'FX_{level}', 1.0)
