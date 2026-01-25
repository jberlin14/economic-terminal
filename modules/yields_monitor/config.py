"""
Yields Monitor Configuration

Defines FRED series for Treasury yields and spread thresholds.
"""

import os
from typing import Dict, Any

# =============================================================================
# API CONFIGURATION
# =============================================================================

FRED_API_KEY = os.getenv('FRED_API_KEY', '')
UPDATE_INTERVAL = int(os.getenv('YIELDS_UPDATE_INTERVAL', 300))  # 5 minutes

# =============================================================================
# US TREASURY YIELD SERIES (FRED)
# =============================================================================

YIELD_SERIES: Dict[str, Dict[str, Any]] = {
    # Short-term
    '1M': {
        'fred_id': 'DGS1MO',
        'name': '1-Month Treasury',
        'order': 1
    },
    '3M': {
        'fred_id': 'DGS3MO',
        'name': '3-Month Treasury',
        'order': 2
    },
    '6M': {
        'fred_id': 'DGS6MO',
        'name': '6-Month Treasury',
        'order': 3
    },
    
    # Medium-term
    '1Y': {
        'fred_id': 'DGS1',
        'name': '1-Year Treasury',
        'order': 4
    },
    '2Y': {
        'fred_id': 'DGS2',
        'name': '2-Year Treasury',
        'order': 5
    },
    '5Y': {
        'fred_id': 'DGS5',
        'name': '5-Year Treasury',
        'order': 6
    },
    
    # Long-term
    '10Y': {
        'fred_id': 'DGS10',
        'name': '10-Year Treasury',
        'order': 7
    },
    '20Y': {
        'fred_id': 'DGS20',
        'name': '20-Year Treasury',
        'order': 8
    },
    '30Y': {
        'fred_id': 'DGS30',
        'name': '30-Year Treasury',
        'order': 9
    },
}

# =============================================================================
# TIPS (INFLATION-PROTECTED) SERIES
# =============================================================================

TIPS_SERIES: Dict[str, Dict[str, Any]] = {
    '5Y_TIPS': {
        'fred_id': 'DFII5',
        'name': '5-Year TIPS Yield',
    },
    '10Y_TIPS': {
        'fred_id': 'DFII10',
        'name': '10-Year TIPS Yield',
    },
}

# =============================================================================
# INTERNATIONAL SOVEREIGN YIELDS
# =============================================================================

INTERNATIONAL_YIELDS: Dict[str, Dict[str, Any]] = {
    'DE_10Y': {
        'fred_id': 'IRLTLT01DEM156N',
        'name': 'Germany 10-Year Bund',
        'country': 'Germany'
    },
    'JP_10Y': {
        'fred_id': 'IRLTLT01JPM156N',
        'name': 'Japan 10-Year JGB',
        'country': 'Japan'
    },
    'GB_10Y': {
        'fred_id': 'IRLTLT01GBM156N',
        'name': 'UK 10-Year Gilt',
        'country': 'United Kingdom'
    },
    'CA_10Y': {
        'fred_id': 'IRLTLT01CAM156N',
        'name': 'Canada 10-Year',
        'country': 'Canada'
    },
    'AU_10Y': {
        'fred_id': 'IRLTLT01AUM156N',
        'name': 'Australia 10-Year',
        'country': 'Australia'
    },
}

# =============================================================================
# SPREAD DEFINITIONS
# =============================================================================

SPREAD_CALCULATIONS = {
    '10Y-2Y': {
        'long': '10Y',
        'short': '2Y',
        'description': 'Classic recession indicator',
        'critical_threshold': -50,  # basis points
    },
    '10Y-3M': {
        'long': '10Y',
        'short': '3M',
        'description': 'Alternative recession indicator',
        'critical_threshold': -50,
    },
    '30Y-10Y': {
        'long': '30Y',
        'short': '10Y',
        'description': 'Long-end steepness',
        'critical_threshold': None,  # No inversion warning
    },
}

# =============================================================================
# RISK THRESHOLDS
# =============================================================================

SPREAD_THRESHOLDS = {
    # Yield curve inversion thresholds (basis points)
    'INVERSION_HIGH': 0,      # Any inversion is noteworthy
    'INVERSION_CRITICAL': float(os.getenv('YIELD_INVERSION_CRITICAL', -50)),
    
    # Steepening thresholds (intraday basis point change)
    'STEEPENING_HIGH': float(os.getenv('YIELD_STEEPENING_HIGH', 25)),
    'STEEPENING_CRITICAL': 50,
    
    # Absolute yield move thresholds (daily basis point change)
    'YIELD_MOVE_HIGH': 10,      # 10 bps move
    'YIELD_MOVE_CRITICAL': 20,  # 20 bps move
}

# =============================================================================
# DISPLAY SETTINGS
# =============================================================================

# Decimal places for yields
YIELD_DECIMALS = 2

# Chart colors
CHART_COLORS = {
    'current_curve': '#60a5fa',      # Blue
    'historical_curve': '#8b92b0',   # Dim gray
    'inversion_zone': '#dc2626',     # Red
    'positive_spread': '#10b981',    # Green
    'negative_spread': '#ef4444',    # Red
}


def get_tenor_order() -> list:
    """Get tenors in correct order for curve display."""
    sorted_tenors = sorted(YIELD_SERIES.items(), key=lambda x: x[1]['order'])
    return [t[0] for t in sorted_tenors]


def get_fred_series_ids() -> Dict[str, str]:
    """Get mapping of tenor to FRED series ID."""
    return {tenor: config['fred_id'] for tenor, config in YIELD_SERIES.items()}


def get_all_series_ids() -> list:
    """Get all FRED series IDs for bulk fetching."""
    series = [config['fred_id'] for config in YIELD_SERIES.values()]
    series += [config['fred_id'] for config in TIPS_SERIES.values()]
    return series
