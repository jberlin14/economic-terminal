"""
FX Risk Detection Rules

Detects currency volatility and large moves.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from .config import ALERT_THRESHOLDS, get_fx_threshold, COUNTRY_PRIORITY
from .models import RiskAlertData


def detect_fx_risks(
    fx_data: Dict[str, Dict[str, Any]],
    threshold_high: Optional[float] = None,
    threshold_critical: Optional[float] = None
) -> List[RiskAlertData]:
    """
    Detect FX risks based on price movements.
    
    Args:
        fx_data: Dictionary of pair -> rate data with change percentages
        threshold_high: Override for HIGH threshold
        threshold_critical: Override for CRITICAL threshold
        
    Returns:
        List of RiskAlertData for detected risks
    """
    risks = []
    
    for pair, data in fx_data.items():
        change_1h = data.get('change_1h')
        
        if change_1h is None:
            continue
        
        abs_change = abs(change_1h)
        
        # Get currency code for specific thresholds
        currency = pair.split('/')[1] if '/' in pair else pair
        
        # Use provided thresholds or get from config
        t_high = threshold_high or get_fx_threshold(currency, 'HIGH')
        t_critical = threshold_critical or get_fx_threshold(currency, 'CRITICAL')
        
        # Check thresholds
        if abs_change >= t_critical:
            severity = 'CRITICAL'
            threshold = t_critical
        elif abs_change >= t_high:
            severity = 'HIGH'
            threshold = t_high
        else:
            continue
        
        # Determine direction
        direction = 'strengthened' if change_1h < 0 else 'weakened'
        # For USD/XXX, negative change means USD strengthened (less foreign currency per USD)
        # Actually for USD/XXX: positive = USD weakened, negative = USD strengthened
        # Wait - if USD/JPY goes UP, USD weakened (buys more JPY)
        # If USD/JPY goes DOWN, USD strengthened (buys less JPY)
        # So: positive change_1h = rate went up = USD weakened
        direction = 'weakened' if change_1h > 0 else 'strengthened'
        
        # Get country priority
        country = _currency_to_country(currency)
        priority = COUNTRY_PRIORITY.get(country, 99)
        
        risk = RiskAlertData(
            alert_type='FX',
            severity=severity,
            title=f"{pair} {severity} Move",
            message=f"{pair} {direction} {abs_change:.2f}% in 1 hour",
            related_entity=pair,
            related_value=data.get('rate'),
            threshold_value=threshold,
            country=country,
            details={
                'change_1h': change_1h,
                'change_24h': data.get('change_24h'),
                'rate': data.get('rate'),
                'direction': direction,
                'country_priority': priority
            }
        )
        
        risks.append(risk)
        logger.info(f"FX Risk detected: {pair} moved {change_1h:.2f}% ({severity})")
    
    # Sort by country priority
    risks.sort(key=lambda r: r.details.get('country_priority', 99))
    
    return risks


def _currency_to_country(currency: str) -> str:
    """Map currency code to country code."""
    mapping = {
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
    return mapping.get(currency, 'US')


def check_fx_volatility(
    rates_history: List[Dict[str, Any]],
    window_hours: int = 24
) -> Dict[str, float]:
    """
    Calculate FX volatility metrics.
    
    Args:
        rates_history: List of historical rate data
        window_hours: Hours to calculate volatility over
        
    Returns:
        Dictionary of pair -> volatility percentage
    """
    # Implementation would calculate rolling volatility
    # This is a placeholder for the full implementation
    return {}
