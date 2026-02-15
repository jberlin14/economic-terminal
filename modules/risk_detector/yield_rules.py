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

    Classification logic:
    - STEEP: 10Y-2Y spread > +100bps (strongly upward sloping)
    - NORMAL: 10Y-2Y spread > 0 and no significant inversions in key segments
    - FLAT: 10Y-2Y spread between -10bps and +25bps
    - PARTIALLY_INVERTED: 10Y-2Y inverted, or 2+ key-segment inversions
    - DEEPLY_INVERTED: 10Y-2Y deeply inverted (<-50bps) or 3+ key-segment inversions

    Key segments are: 2Y→5Y, 5Y→10Y, 2Y→10Y, 3M→10Y. Minor inversions
    in the long end (20Y vs 30Y) or very short end are common and do NOT
    indicate meaningful inversion on their own.
    """
    tenors = ['1M', '3M', '6M', '1Y', '2Y', '5Y', '10Y', '20Y', '30Y']
    yields = []

    for tenor in tenors:
        val = yield_data.get(tenor) or yield_data.get(f'tenor_{tenor.lower()}')
        if val is not None:
            yields.append((tenor, val))

    if len(yields) < 3:
        return {'status': 'insufficient_data'}

    # Build lookup
    yield_map = {t: v for t, v in yields}

    # Find all consecutive inversions (for reporting)
    all_inversions = []
    for i in range(len(yields) - 1):
        if yields[i+1][1] < yields[i][1]:
            all_inversions.append((yields[i][0], yields[i+1][0]))

    # Key spread: 10Y-2Y (the canonical recession indicator)
    spread_10y2y = None
    if '10Y' in yield_map and '2Y' in yield_map:
        spread_10y2y = yield_map['10Y'] - yield_map['2Y']

    # Key spread: 10Y-3M (alternative recession indicator)
    spread_10y3m = None
    if '10Y' in yield_map and '3M' in yield_map:
        spread_10y3m = yield_map['10Y'] - yield_map['3M']

    # Count KEY-SEGMENT inversions (not minor long-end kinks)
    key_inversions = []
    key_pairs = [('2Y', '5Y'), ('5Y', '10Y'), ('2Y', '10Y'), ('3M', '2Y'), ('3M', '10Y')]
    for short, long in key_pairs:
        if short in yield_map and long in yield_map:
            if yield_map[long] < yield_map[short]:
                key_inversions.append((short, long))

    # Classify based on the 10Y-2Y spread (primary) and key inversions (secondary)
    if spread_10y2y is not None:
        spread_bps = spread_10y2y * 100
        if spread_bps < -50 or len(key_inversions) >= 3:
            shape = 'DEEPLY_INVERTED'
        elif spread_bps < -10 or len(key_inversions) >= 2:
            shape = 'PARTIALLY_INVERTED'
        elif spread_bps < 25:
            shape = 'FLAT'
        elif spread_bps < 100:
            shape = 'NORMAL'
        else:
            shape = 'STEEP'
    else:
        # Fallback if 10Y or 2Y missing
        if len(key_inversions) >= 3:
            shape = 'DEEPLY_INVERTED'
        elif len(key_inversions) >= 2:
            shape = 'PARTIALLY_INVERTED'
        elif len(all_inversions) == 0:
            shape = 'NORMAL'
        else:
            shape = 'FLAT'

    # is_inverted only true for meaningful inversions, not minor kinks
    is_inverted = shape in ('PARTIALLY_INVERTED', 'DEEPLY_INVERTED')

    return {
        'status': 'ok',
        'shape': shape,
        'inversions': all_inversions,
        'key_inversions': key_inversions,
        'inversion_count': len(all_inversions),
        'key_inversion_count': len(key_inversions),
        'is_inverted': is_inverted,
        'spread_10y2y': spread_10y2y,
        'spread_10y3m': spread_10y3m,
    }
