"""
Yield Curve Risk Detection Rules

Detects yield curve inversions and rapid steepening/flattening.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from .config import ALERT_THRESHOLDS
from .models import RiskAlertData


def detect_yield_risks(
    yield_data: Dict[str, Any],
    previous_data: Optional[Dict[str, Any]] = None
) -> List[RiskAlertData]:
    """
    Detect yield curve risks.
    
    Args:
        yield_data: Current yield curve data
        previous_data: Previous yield curve for change detection
        
    Returns:
        List of RiskAlertData for detected risks
    """
    risks = []
    
    # Get key values
    yield_10y = yield_data.get('10Y') or yield_data.get('tenor_10y')
    yield_2y = yield_data.get('2Y') or yield_data.get('tenor_2y')
    yield_3m = yield_data.get('3M') or yield_data.get('tenor_3m')
    
    # Calculate 10Y-2Y spread
    if yield_10y is not None and yield_2y is not None:
        spread_10y2y = yield_10y - yield_2y
        spread_bps = spread_10y2y * 100
        
        # Check for inversion
        if spread_bps < ALERT_THRESHOLDS['YIELD_INVERSION_CRITICAL']:
            risks.append(RiskAlertData(
                alert_type='YIELDS',
                severity='CRITICAL',
                title="Deep Yield Curve Inversion",
                message=f"10Y-2Y spread at {spread_bps:.0f} bps - deep inversion signals recession risk",
                related_entity='10Y-2Y',
                related_value=spread_10y2y,
                threshold_value=ALERT_THRESHOLDS['YIELD_INVERSION_CRITICAL'],
                country='US',
                details={
                    'spread_bps': spread_bps,
                    'yield_10y': yield_10y,
                    'yield_2y': yield_2y,
                    'is_inverted': True
                }
            ))
            logger.warning(f"CRITICAL: 10Y-2Y spread at {spread_bps:.0f} bps")
            
        elif spread_bps < ALERT_THRESHOLDS['YIELD_INVERSION_HIGH']:
            risks.append(RiskAlertData(
                alert_type='YIELDS',
                severity='HIGH',
                title="Yield Curve Inverted",
                message=f"10Y-2Y spread inverted at {spread_bps:.0f} bps",
                related_entity='10Y-2Y',
                related_value=spread_10y2y,
                threshold_value=ALERT_THRESHOLDS['YIELD_INVERSION_HIGH'],
                country='US',
                details={
                    'spread_bps': spread_bps,
                    'yield_10y': yield_10y,
                    'yield_2y': yield_2y,
                    'is_inverted': True
                }
            ))
            logger.info(f"HIGH: Yield curve inverted at {spread_bps:.0f} bps")
    
    # Check for 10Y-3M inversion (alternative indicator)
    if yield_10y is not None and yield_3m is not None:
        spread_10y3m = yield_10y - yield_3m
        spread_bps = spread_10y3m * 100
        
        if spread_bps < ALERT_THRESHOLDS['YIELD_INVERSION_CRITICAL']:
            risks.append(RiskAlertData(
                alert_type='YIELDS',
                severity='HIGH',
                title="10Y-3M Spread Inverted",
                message=f"10Y-3M spread at {spread_bps:.0f} bps - alternative recession signal",
                related_entity='10Y-3M',
                related_value=spread_10y3m,
                country='US',
                details={
                    'spread_bps': spread_bps,
                    'yield_10y': yield_10y,
                    'yield_3m': yield_3m
                }
            ))
    
    # Check for rapid steepening/flattening (if we have previous data)
    if previous_data:
        prev_10y = previous_data.get('10Y') or previous_data.get('tenor_10y')
        prev_2y = previous_data.get('2Y') or previous_data.get('tenor_2y')
        
        if all([yield_10y, yield_2y, prev_10y, prev_2y]):
            current_spread = yield_10y - yield_2y
            prev_spread = prev_10y - prev_2y
            change_bps = (current_spread - prev_spread) * 100
            
            if abs(change_bps) >= ALERT_THRESHOLDS['YIELD_STEEPENING_CRITICAL']:
                direction = 'steepening' if change_bps > 0 else 'flattening'
                risks.append(RiskAlertData(
                    alert_type='YIELDS',
                    severity='CRITICAL',
                    title=f"Rapid Curve {direction.title()}",
                    message=f"10Y-2Y spread changed {change_bps:+.0f} bps - significant {direction}",
                    related_entity='10Y-2Y',
                    related_value=current_spread,
                    threshold_value=ALERT_THRESHOLDS['YIELD_STEEPENING_CRITICAL'],
                    country='US',
                    details={
                        'change_bps': change_bps,
                        'direction': direction,
                        'current_spread_bps': current_spread * 100,
                        'previous_spread_bps': prev_spread * 100
                    }
                ))
                
            elif abs(change_bps) >= ALERT_THRESHOLDS['YIELD_STEEPENING_HIGH']:
                direction = 'steepening' if change_bps > 0 else 'flattening'
                risks.append(RiskAlertData(
                    alert_type='YIELDS',
                    severity='HIGH',
                    title=f"Curve {direction.title()}",
                    message=f"10Y-2Y spread changed {change_bps:+.0f} bps",
                    related_entity='10Y-2Y',
                    related_value=current_spread,
                    threshold_value=ALERT_THRESHOLDS['YIELD_STEEPENING_HIGH'],
                    country='US',
                    details={
                        'change_bps': change_bps,
                        'direction': direction
                    }
                ))
    
    return risks


def analyze_curve_shape(
    yield_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Analyze the overall shape of the yield curve.
    
    Returns analysis including inversions, kinks, and classification.
    """
    tenors = ['1M', '3M', '6M', '1Y', '2Y', '5Y', '10Y', '20Y', '30Y']
    yields = []
    
    for tenor in tenors:
        val = yield_data.get(tenor) or yield_data.get(f'tenor_{tenor.lower()}')
        if val is not None:
            yields.append((tenor, val))
    
    if len(yields) < 3:
        return {'status': 'insufficient_data'}
    
    # Find inversions
    inversions = []
    for i in range(len(yields) - 1):
        if yields[i+1][1] < yields[i][1]:
            inversions.append((yields[i][0], yields[i+1][0]))
    
    # Classify curve shape
    if len(inversions) == 0:
        shape = 'NORMAL'
    elif len(inversions) >= 3:
        shape = 'DEEPLY_INVERTED'
    else:
        shape = 'PARTIALLY_INVERTED'
    
    return {
        'status': 'ok',
        'shape': shape,
        'inversions': inversions,
        'inversion_count': len(inversions),
        'is_inverted': len(inversions) > 0
    }
