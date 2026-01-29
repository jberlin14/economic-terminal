"""
Credit Spread Risk Detection Rules

Detects credit market stress through spread widening and percentile analysis.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from .config import ALERT_THRESHOLDS
from .models import RiskAlertData


def detect_credit_risks(
    spread_data: Dict[str, Dict[str, Any]]
) -> List[RiskAlertData]:
    """
    Detect credit spread risks based on percentile analysis.
    
    Args:
        spread_data: Dictionary of index_name -> spread data including percentiles
        
    Returns:
        List of RiskAlertData for detected risks
    """
    risks = []
    
    for index_name, data in spread_data.items():
        percentile_90d = data.get('percentile_90d')
        spread_bps = data.get('spread_bps')
        change_1d = data.get('change_1d')
        
        # Check percentile-based thresholds
        if percentile_90d is not None:
            if percentile_90d >= ALERT_THRESHOLDS['CREDIT_PERCENTILE_CRITICAL']:
                risks.append(RiskAlertData(
                    alert_type='CREDIT',
                    severity='CRITICAL',
                    title=f"{index_name} at Extreme Levels",
                    message=f"{index_name} spread at {spread_bps:.0f} bps ({percentile_90d:.0f}th percentile)",
                    related_entity=index_name,
                    related_value=spread_bps,
                    threshold_value=ALERT_THRESHOLDS['CREDIT_PERCENTILE_CRITICAL'],
                    country='US',
                    details={
                        'spread_bps': spread_bps,
                        'percentile_90d': percentile_90d,
                        'percentile_1y': data.get('percentile_1y'),
                        'avg_90d': data.get('avg_90d')
                    }
                ))
                logger.warning(f"CRITICAL: {index_name} at {percentile_90d:.0f}th percentile")
                
            elif percentile_90d >= ALERT_THRESHOLDS['CREDIT_PERCENTILE_HIGH']:
                risks.append(RiskAlertData(
                    alert_type='CREDIT',
                    severity='HIGH',
                    title=f"{index_name} Elevated",
                    message=f"{index_name} spread at {spread_bps:.0f} bps ({percentile_90d:.0f}th percentile)",
                    related_entity=index_name,
                    related_value=spread_bps,
                    threshold_value=ALERT_THRESHOLDS['CREDIT_PERCENTILE_HIGH'],
                    country='US',
                    details={
                        'spread_bps': spread_bps,
                        'percentile_90d': percentile_90d
                    }
                ))
        
        # Check for rapid widening
        if change_1d is not None:
            if abs(change_1d) >= ALERT_THRESHOLDS['CREDIT_WIDENING_CRITICAL']:
                direction = 'widening' if change_1d > 0 else 'tightening'
                risks.append(RiskAlertData(
                    alert_type='CREDIT',
                    severity='CRITICAL',
                    title=f"{index_name} Rapid {direction.title()}",
                    message=f"{index_name} {direction} {abs(change_1d):.0f} bps in 1 day",
                    related_entity=index_name,
                    related_value=spread_bps,
                    threshold_value=ALERT_THRESHOLDS['CREDIT_WIDENING_CRITICAL'],
                    country='US',
                    details={
                        'change_1d': change_1d,
                        'spread_bps': spread_bps,
                        'direction': direction
                    }
                ))
                
            elif abs(change_1d) >= ALERT_THRESHOLDS['CREDIT_WIDENING_HIGH']:
                direction = 'widening' if change_1d > 0 else 'tightening'
                risks.append(RiskAlertData(
                    alert_type='CREDIT',
                    severity='HIGH',
                    title=f"{index_name} {direction.title()}",
                    message=f"{index_name} {direction} {abs(change_1d):.0f} bps today",
                    related_entity=index_name,
                    related_value=spread_bps,
                    threshold_value=ALERT_THRESHOLDS['CREDIT_WIDENING_HIGH'],
                    country='US',
                    details={
                        'change_1d': change_1d,
                        'spread_bps': spread_bps
                    }
                ))
    
    return risks


def calculate_percentile(
    current_value: float,
    historical_values: List[float]
) -> float:
    """
    Calculate percentile rank of current value vs historical.
    
    Args:
        current_value: Current spread value
        historical_values: List of historical values
        
    Returns:
        Percentile (0-100)
    """
    if not historical_values:
        return 50.0
    
    count_below = sum(1 for v in historical_values if v < current_value)
    return (count_below / len(historical_values)) * 100


def assess_credit_conditions(
    spread_data: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Assess overall credit market conditions.
    
    Returns summary of credit market stress levels.
    """
    assessment = {
        'timestamp': datetime.utcnow().isoformat(),
        'stress_level': 'NORMAL',
        'ig_status': 'NORMAL',
        'hy_status': 'NORMAL',
        'alerts': []
    }
    
    # Check Investment Grade (spread vs 90-day average)
    ig_data = spread_data.get('US_IG') or spread_data.get('BBB_OAS')
    if ig_data:
        spread = ig_data.get('spread_bps')
        avg = ig_data.get('avg_90d')
        if spread is not None and avg is not None and avg > 0:
            ratio = spread / avg
            if ratio >= 1.3:  # 30%+ above 90d avg
                assessment['ig_status'] = 'STRESSED'
                assessment['stress_level'] = 'ELEVATED'
            elif ratio >= 1.15:  # 15%+ above 90d avg
                assessment['ig_status'] = 'ELEVATED'

    # Check High Yield (spread vs 90-day average)
    hy_data = spread_data.get('US_HY') or spread_data.get('HY_OAS')
    if hy_data:
        spread = hy_data.get('spread_bps')
        avg = hy_data.get('avg_90d')
        if spread is not None and avg is not None and avg > 0:
            ratio = spread / avg
            if ratio >= 1.3:
                assessment['hy_status'] = 'STRESSED'
                assessment['stress_level'] = 'HIGH'
            elif ratio >= 1.15:
                assessment['hy_status'] = 'ELEVATED'
                if assessment['stress_level'] == 'NORMAL':
                    assessment['stress_level'] = 'ELEVATED'
    
    return assessment
