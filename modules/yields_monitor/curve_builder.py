"""
Yield Curve Builder

Handles yield curve interpolation, spread calculations, and risk detection.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any
import numpy as np
from loguru import logger

from .config import SPREAD_CALCULATIONS, SPREAD_THRESHOLDS, get_tenor_order
from .models import YieldCurveData, YieldSpread, YieldCurveChange, YieldAlert


class CurveBuilder:
    """
    Builder for yield curve analysis and visualization.
    """
    
    # Tenor to years mapping for interpolation
    TENOR_YEARS = {
        '1M': 1/12,
        '3M': 0.25,
        '6M': 0.5,
        '1Y': 1.0,
        '2Y': 2.0,
        '5Y': 5.0,
        '10Y': 10.0,
        '20Y': 20.0,
        '30Y': 30.0,
    }
    
    @staticmethod
    def calculate_spread(
        curve: YieldCurveData,
        spread_name: str
    ) -> Optional[YieldSpread]:
        """
        Calculate a specific spread from the yield curve.
        
        Args:
            curve: YieldCurveData with tenor values
            spread_name: Spread to calculate (e.g., '10Y-2Y')
            
        Returns:
            YieldSpread object or None
        """
        if spread_name not in SPREAD_CALCULATIONS:
            logger.error(f"Unknown spread: {spread_name}")
            return None
        
        config = SPREAD_CALCULATIONS[spread_name]
        long_tenor = config['long']
        short_tenor = config['short']
        
        # Get yields from curve
        curve_dict = curve.curve_dict
        long_yield = curve_dict.get(long_tenor)
        short_yield = curve_dict.get(short_tenor)
        
        if long_yield is None or short_yield is None:
            return None
        
        spread_value = long_yield - short_yield
        
        return YieldSpread(
            name=spread_name,
            value=spread_value,
            value_bps=spread_value * 100,
            long_tenor=long_tenor,
            short_tenor=short_tenor,
            long_yield=long_yield,
            short_yield=short_yield,
            is_inverted=spread_value < 0,
            timestamp=curve.timestamp
        )
    
    @staticmethod
    def calculate_all_spreads(
        curve: YieldCurveData
    ) -> Dict[str, YieldSpread]:
        """
        Calculate all configured spreads.
        
        Args:
            curve: YieldCurveData
            
        Returns:
            Dictionary of spread_name -> YieldSpread
        """
        spreads = {}
        for spread_name in SPREAD_CALCULATIONS.keys():
            spread = CurveBuilder.calculate_spread(curve, spread_name)
            if spread:
                spreads[spread_name] = spread
        return spreads
    
    @staticmethod
    def detect_inversion(curve: YieldCurveData) -> List[YieldAlert]:
        """
        Detect yield curve inversions.
        
        Args:
            curve: YieldCurveData
            
        Returns:
            List of YieldAlert for any inversions detected
        """
        alerts = []
        
        # Check 10Y-2Y spread (primary indicator)
        if curve.spread_10y2y is not None:
            spread_bps = curve.spread_10y2y * 100
            
            if spread_bps < SPREAD_THRESHOLDS['INVERSION_CRITICAL']:
                alerts.append(YieldAlert(
                    severity='CRITICAL',
                    category='INVERSION',
                    message=f"Yield curve deeply inverted: 10Y-2Y spread at {spread_bps:.0f} bps",
                    spread_name='10Y-2Y',
                    spread_value=curve.spread_10y2y,
                    threshold_breached=SPREAD_THRESHOLDS['INVERSION_CRITICAL'],
                    timestamp=curve.timestamp
                ))
            elif spread_bps < SPREAD_THRESHOLDS['INVERSION_HIGH']:
                alerts.append(YieldAlert(
                    severity='HIGH',
                    category='INVERSION',
                    message=f"Yield curve inverted: 10Y-2Y spread at {spread_bps:.0f} bps",
                    spread_name='10Y-2Y',
                    spread_value=curve.spread_10y2y,
                    threshold_breached=SPREAD_THRESHOLDS['INVERSION_HIGH'],
                    timestamp=curve.timestamp
                ))
        
        # Check 10Y-3M spread (alternative indicator)
        if curve.spread_10y3m is not None:
            spread_bps = curve.spread_10y3m * 100
            
            if spread_bps < SPREAD_THRESHOLDS['INVERSION_CRITICAL']:
                alerts.append(YieldAlert(
                    severity='CRITICAL',
                    category='INVERSION',
                    message=f"10Y-3M spread deeply inverted at {spread_bps:.0f} bps",
                    spread_name='10Y-3M',
                    spread_value=curve.spread_10y3m,
                    threshold_breached=SPREAD_THRESHOLDS['INVERSION_CRITICAL'],
                    timestamp=curve.timestamp
                ))
        
        return alerts
    
    @staticmethod
    def detect_steepening(
        current: YieldCurveData,
        previous: YieldCurveData
    ) -> List[YieldAlert]:
        """
        Detect rapid steepening or flattening.
        
        Args:
            current: Current yield curve
            previous: Previous yield curve
            
        Returns:
            List of YieldAlert for significant changes
        """
        alerts = []
        
        if current.spread_10y2y is None or previous.spread_10y2y is None:
            return alerts
        
        # Calculate change in spread (basis points)
        change_bps = (current.spread_10y2y - previous.spread_10y2y) * 100
        
        if abs(change_bps) >= SPREAD_THRESHOLDS['STEEPENING_CRITICAL']:
            direction = 'steepening' if change_bps > 0 else 'flattening'
            alerts.append(YieldAlert(
                severity='CRITICAL',
                category='STEEPENING',
                message=f"Rapid curve {direction}: {abs(change_bps):.0f} bps change in 10Y-2Y spread",
                spread_name='10Y-2Y',
                spread_value=current.spread_10y2y,
                threshold_breached=SPREAD_THRESHOLDS['STEEPENING_CRITICAL'],
                timestamp=current.timestamp
            ))
        elif abs(change_bps) >= SPREAD_THRESHOLDS['STEEPENING_HIGH']:
            direction = 'steepening' if change_bps > 0 else 'flattening'
            alerts.append(YieldAlert(
                severity='HIGH',
                category='STEEPENING',
                message=f"Significant curve {direction}: {abs(change_bps):.0f} bps change",
                spread_name='10Y-2Y',
                spread_value=current.spread_10y2y,
                threshold_breached=SPREAD_THRESHOLDS['STEEPENING_HIGH'],
                timestamp=current.timestamp
            ))
        
        return alerts
    
    @staticmethod
    def interpolate_curve(
        curve: YieldCurveData,
        num_points: int = 100
    ) -> List[Dict[str, float]]:
        """
        Interpolate the yield curve for smooth charting.
        
        Args:
            curve: YieldCurveData with tenor values
            num_points: Number of interpolation points
            
        Returns:
            List of {years, yield} points
        """
        # Get available data points
        curve_dict = curve.curve_dict
        data_points = []
        
        for tenor, yield_val in curve_dict.items():
            if yield_val is not None and tenor in CurveBuilder.TENOR_YEARS:
                years = CurveBuilder.TENOR_YEARS[tenor]
                data_points.append((years, yield_val))
        
        if len(data_points) < 2:
            return []
        
        # Sort by years
        data_points.sort(key=lambda x: x[0])
        
        x_data = np.array([p[0] for p in data_points])
        y_data = np.array([p[1] for p in data_points])
        
        # Interpolate
        x_interp = np.linspace(x_data.min(), x_data.max(), num_points)
        y_interp = np.interp(x_interp, x_data, y_data)
        
        return [
            {'years': float(x), 'yield': float(y)}
            for x, y in zip(x_interp, y_interp)
        ]
    
    @staticmethod
    def compare_curves(
        current: YieldCurveData,
        historical: YieldCurveData
    ) -> YieldCurveChange:
        """
        Compare two yield curves.
        
        Args:
            current: Current curve
            historical: Historical curve for comparison
            
        Returns:
            YieldCurveChange with differences
        """
        time_delta = (current.timestamp - historical.timestamp).total_seconds() / 3600
        
        change = YieldCurveChange(
            current=current,
            previous=historical,
            time_delta_hours=time_delta
        )
        
        # Calculate specific changes
        if current.tenor_10y is not None and historical.tenor_10y is not None:
            change.change_10y = (current.tenor_10y - historical.tenor_10y) * 100
        
        if current.tenor_2y is not None and historical.tenor_2y is not None:
            change.change_2y = (current.tenor_2y - historical.tenor_2y) * 100
        
        if current.spread_10y2y is not None and historical.spread_10y2y is not None:
            change.change_spread = (current.spread_10y2y - historical.spread_10y2y) * 100
        
        return change
    
    @staticmethod
    def find_inversion_points(curve: YieldCurveData) -> List[Tuple[str, str]]:
        """
        Find any points where the curve inverts.
        
        Args:
            curve: YieldCurveData
            
        Returns:
            List of (short_tenor, long_tenor) tuples where inversion occurs
        """
        curve_dict = curve.curve_dict
        tenors = get_tenor_order()
        inversions = []
        
        for i in range(len(tenors) - 1):
            short_tenor = tenors[i]
            long_tenor = tenors[i + 1]
            
            short_yield = curve_dict.get(short_tenor)
            long_yield = curve_dict.get(long_tenor)
            
            if short_yield is not None and long_yield is not None:
                if long_yield < short_yield:
                    inversions.append((short_tenor, long_tenor))
        
        return inversions
    
    @staticmethod
    def get_curve_summary(curve: YieldCurveData) -> Dict[str, Any]:
        """
        Get a summary of the yield curve for dashboard display.
        
        Args:
            curve: YieldCurveData
            
        Returns:
            Summary dictionary
        """
        spreads = CurveBuilder.calculate_all_spreads(curve)
        inversions = CurveBuilder.find_inversion_points(curve)
        
        return {
            'timestamp': curve.timestamp.isoformat(),
            'tenors': curve.curve_dict,
            'spreads': {
                name: {
                    'value': s.value,
                    'value_bps': s.value_bps,
                    'is_inverted': s.is_inverted
                }
                for name, s in spreads.items()
            },
            'is_inverted': curve.is_inverted,
            'inversion_depth_bps': curve.inversion_depth,
            'inversion_points': inversions,
            'tips': {
                '5Y': curve.tips_5y,
                '10Y': curve.tips_10y
            }
        }
