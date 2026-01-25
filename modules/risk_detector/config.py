"""
Risk Detector Configuration

Defines risk hierarchies, thresholds, and alert settings.
"""

import os
from typing import Dict, List, Any

# =============================================================================
# RISK TYPE HIERARCHY (Detection Priority)
# =============================================================================

RISK_HIERARCHY = {
    'ECON': 1,      # Economic data surprises
    'FX': 2,        # Currency volatility
    'POLITICAL': 3, # Geopolitical developments
    'CREDIT': 4,    # Credit market stress
    'CAT': 5,       # Catastrophic events
}

# =============================================================================
# COUNTRY/REGION PRIORITY (Alert Routing)
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

# =============================================================================
# ALERT THRESHOLDS
# =============================================================================

ALERT_THRESHOLDS = {
    # FX Thresholds (1-hour percentage change)
    'FX_HIGH': float(os.getenv('FX_RISK_THRESHOLD_HIGH', 1.0)),
    'FX_CRITICAL': float(os.getenv('FX_RISK_THRESHOLD_CRITICAL', 2.0)),
    
    # Special FX thresholds for volatile currencies
    'FX_ARS_HIGH': 3.0,
    'FX_ARS_CRITICAL': 5.0,
    'FX_BRL_HIGH': 1.5,
    'FX_BRL_CRITICAL': 3.0,
    
    # Yield Spread Thresholds (basis points)
    'YIELD_INVERSION_HIGH': 0,
    'YIELD_INVERSION_CRITICAL': float(os.getenv('YIELD_INVERSION_CRITICAL', -50)),
    'YIELD_STEEPENING_HIGH': float(os.getenv('YIELD_STEEPENING_HIGH', 25)),
    'YIELD_STEEPENING_CRITICAL': 50,
    
    # Credit Spread Thresholds (percentile)
    'CREDIT_PERCENTILE_HIGH': float(os.getenv('CREDIT_PERCENTILE_HIGH', 90)),
    'CREDIT_PERCENTILE_CRITICAL': float(os.getenv('CREDIT_PERCENTILE_CRITICAL', 95)),
    'CREDIT_WIDENING_HIGH': 50,    # bps intraday
    'CREDIT_WIDENING_CRITICAL': 100,
    
    # Economic Surprise Thresholds (percentage miss vs consensus)
    'ECON_SURPRISE_HIGH': float(os.getenv('ECONOMIC_SURPRISE_THRESHOLD', 30)),
    'ECON_SURPRISE_CRITICAL': 50,
}

# =============================================================================
# CRITICAL KEYWORDS (for geopolitical/news detection)
# =============================================================================

CRITICAL_KEYWORDS = [
    # Military/Conflict
    'missile strike', 'nuclear', 'NATO article 5', 'declaration of war',
    'military escalation', 'invasion', 'bombing', 'troops deployed',
    'air strike', 'ground invasion', 'martial law',
    
    # Trade/Economic Policy
    '25% tariff', 'universal tariff', 'USMCA withdrawal', 'trade war escalation',
    'SCOTUS denies', 'IEEPA', 'emergency powers', 'executive order tariff',
    'blanket tariff', 'retaliatory tariff', 'trade embargo',
    
    # Central Bank/Fed
    'Fed independence threat', 'Powell fired', 'emergency rate cut',
    'extraordinary measures', 'quantitative easing restart', 'QE restart',
    'Fed chair removal', 'monetary policy interference',
    
    # Market Structure
    'trading halt', 'circuit breaker', 'market closure',
    'systemic risk', 'liquidity crisis', 'flash crash',
    'market suspended', 'clearing failure',
    
    # Catastrophic Events
    'major hurricane landfall', 'earthquake magnitude 7', 'tsunami warning',
    'terrorist attack', 'infrastructure failure', 'cyberattack',
    'category 5 hurricane', 'massive earthquake',
    
    # Political Crisis
    'government shutdown', 'debt ceiling breach', 'constitutional crisis',
    'impeachment', 'election contested', 'coup attempt',
]

HIGH_KEYWORDS = [
    # Trade
    'tariff announced', 'trade restriction', 'export ban', 'import ban',
    'sanctions expansion', 'trade negotiation breakdown',
    
    # Economic
    'recession indicator', 'GDP contraction', 'employment shock',
    'inflation surge', 'deflation warning',
    
    # Political
    'policy reversal', 'cabinet resignation', 'diplomatic incident',
    'embassy closure', 'sanctions announced',
    
    # Market
    'volatility spike', 'bond selloff', 'equity correction',
    'currency intervention', 'rate decision surprise',
]

# =============================================================================
# SOURCE CREDIBILITY
# =============================================================================

HIGH_CREDIBILITY_SOURCES = [
    'Bloomberg', 'Reuters', 'WSJ', 'Wall Street Journal', 'FT', 'Financial Times',
    'NYT', 'New York Times', 'AP', 'Associated Press', 'CNBC',
    'Federal Reserve', 'Treasury', 'BLS', 'ECB', 'BOJ', 'BOE',
]

MEDIUM_CREDIBILITY_SOURCES = [
    'MarketWatch', 'Barrons', 'Business Insider', 'Yahoo Finance',
    'Seeking Alpha', 'The Economist', 'Forbes',
]

# =============================================================================
# TRUMP SOCIAL MEDIA MONITORING
# =============================================================================

TRUMP_KEYWORDS = [
    'tariff', 'tariffs', 'trade', 'China', 'Fed', 'Powell',
    'interest rate', 'currency', 'dollar', 'USMCA', 'Mexico',
    'Canada', 'Japan', 'EU', 'Europe', 'trade deal',
]

# =============================================================================
# ALERT DEDUPLICATION
# =============================================================================

ALERT_COOLDOWN = {
    'FX': 3600,
    'YIELDS': 3600,
    'CREDIT': 3600,
    'POLITICAL': 1800,
    'ECON': 7200,
    'CAT': 3600,
}

MAX_ACTIVE_ALERTS = {
    'FX': 5,
    'YIELDS': 3,
    'CREDIT': 3,
    'POLITICAL': 10,
    'ECON': 5,
    'CAT': 5,
}


def get_fx_threshold(currency: str, level: str = 'HIGH') -> float:
    """Get FX threshold for a specific currency."""
    key = f"FX_{currency}_{level}"
    if key in ALERT_THRESHOLDS:
        return ALERT_THRESHOLDS[key]
    return ALERT_THRESHOLDS[f"FX_{level}"]


def get_cooldown(alert_type: str) -> int:
    """Get cooldown period for alert type."""
    return ALERT_COOLDOWN.get(alert_type, 3600)


def is_critical_keyword(text: str) -> bool:
    """Check if text contains critical keywords."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in CRITICAL_KEYWORDS)


def is_high_keyword(text: str) -> bool:
    """Check if text contains high-priority keywords."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in HIGH_KEYWORDS)


def get_source_credibility(source: str) -> str:
    """Get credibility level for a news source."""
    for s in HIGH_CREDIBILITY_SOURCES:
        if s.lower() in source.lower():
            return 'HIGH'
    for s in MEDIUM_CREDIBILITY_SOURCES:
        if s.lower() in source.lower():
            return 'MEDIUM'
    return 'LOW'


def is_trump_related(text: str) -> bool:
    """Check if text is Trump-related and market-relevant."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in TRUMP_KEYWORDS)
