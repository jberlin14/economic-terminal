"""
FX Rate Calculator

Handles rate conversions, change calculations, and sparkline generation.
Ensures all rates follow USD/XXX convention.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
import numpy as np
from loguru import logger

from .config import FX_PAIRS, DXY_CONFIG, get_decimal_places


class RateCalculator:
    """
    Calculator for FX rate conversions and analytics.
    """
    
    @staticmethod
    def invert_rate(rate: float) -> float:
        """
        Invert a rate (for converting XXX/USD to USD/XXX).
        
        Args:
            rate: The original rate (e.g., EUR/USD = 1.0845)
            
        Returns:
            Inverted rate (e.g., USD/EUR = 0.9221)
        """
        if rate == 0:
            raise ValueError("Cannot invert zero rate")
        return 1.0 / rate
    
    @staticmethod
    def convert_to_usd_base(
        pair: str,
        market_rate: float
    ) -> Tuple[str, float]:
        """
        Convert a market rate to USD/XXX convention.
        
        Args:
            pair: The pair identifier (e.g., 'USD/EUR')
            market_rate: The raw rate from the data source
            
        Returns:
            Tuple of (standardized_pair, converted_rate)
        """
        if pair not in FX_PAIRS:
            if pair == 'USDX':
                return pair, market_rate
            raise ValueError(f"Unknown pair: {pair}")
        
        config = FX_PAIRS[pair]
        
        if config['invert']:
            converted = RateCalculator.invert_rate(market_rate)
        else:
            converted = market_rate
        
        # Round to appropriate decimal places
        decimals = get_decimal_places(pair)
        return pair, round(converted, decimals)
    
    @staticmethod
    def calculate_change(
        current: float,
        previous: float
    ) -> Optional[float]:
        """
        Calculate percentage change between two rates.
        
        Args:
            current: Current rate
            previous: Previous rate
            
        Returns:
            Percentage change (e.g., 1.5 for +1.5%) or None if invalid
        """
        if previous == 0 or current is None or previous is None:
            return None
        
        change = ((current - previous) / previous) * 100
        return round(change, 4)
    
    @staticmethod
    def calculate_all_changes(
        current_rate: float,
        rate_1h_ago: Optional[float],
        rate_24h_ago: Optional[float],
        rate_1w_ago: Optional[float],
        rate_ytd_start: Optional[float]
    ) -> Dict[str, Optional[float]]:
        """
        Calculate all change percentages for a rate.
        
        Args:
            current_rate: Current exchange rate
            rate_1h_ago: Rate 1 hour ago
            rate_24h_ago: Rate 24 hours ago
            rate_1w_ago: Rate 1 week ago
            rate_ytd_start: Rate at start of year
            
        Returns:
            Dictionary with all change percentages
        """
        return {
            'change_1h': RateCalculator.calculate_change(current_rate, rate_1h_ago),
            'change_24h': RateCalculator.calculate_change(current_rate, rate_24h_ago),
            'change_1w': RateCalculator.calculate_change(current_rate, rate_1w_ago),
            'change_ytd': RateCalculator.calculate_change(current_rate, rate_ytd_start),
        }
    
    @staticmethod
    def generate_sparkline(
        rates: List[Tuple[datetime, float]],
        hours: int = 24,
        interval_minutes: int = 15
    ) -> List[float]:
        """
        Generate sparkline data from historical rates.
        
        Args:
            rates: List of (timestamp, rate) tuples, ordered by time
            hours: Number of hours to include
            interval_minutes: Minutes between sparkline points
            
        Returns:
            List of rate values for sparkline chart
        """
        if not rates:
            return []
        
        # Calculate expected number of points
        num_points = hours * 60 // interval_minutes
        
        # Get time boundaries
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        # Create time buckets
        sparkline = []
        current_time = start_time
        rate_idx = 0
        
        while current_time <= end_time and len(sparkline) < num_points:
            # Find the closest rate at or before current_time
            closest_rate = None
            
            while rate_idx < len(rates):
                ts, rate = rates[rate_idx]
                if ts <= current_time:
                    closest_rate = rate
                    rate_idx += 1
                else:
                    break
            
            if closest_rate is not None:
                sparkline.append(closest_rate)
            elif sparkline:
                # Forward fill with last known rate
                sparkline.append(sparkline[-1])
            
            current_time += timedelta(minutes=interval_minutes)
        
        return sparkline
    
    @staticmethod
    def interpolate_sparkline(
        sparkline: List[float],
        target_length: int
    ) -> List[float]:
        """
        Interpolate sparkline to a target number of points.
        
        Args:
            sparkline: Original sparkline data
            target_length: Desired number of points
            
        Returns:
            Interpolated sparkline
        """
        if not sparkline:
            return []
        
        if len(sparkline) == target_length:
            return sparkline
        
        # Use numpy interpolation
        x_original = np.linspace(0, 1, len(sparkline))
        x_new = np.linspace(0, 1, target_length)
        return list(np.interp(x_new, x_original, sparkline))
    
    @staticmethod
    def detect_risk(
        pair: str,
        change_1h: Optional[float],
        threshold_high: float = 1.0,
        threshold_critical: float = 2.0
    ) -> Optional[str]:
        """
        Detect risk level based on 1-hour change.
        
        Args:
            pair: Currency pair
            change_1h: 1-hour percentage change
            threshold_high: Threshold for HIGH risk
            threshold_critical: Threshold for CRITICAL risk
            
        Returns:
            'CRITICAL', 'HIGH', or None
        """
        if change_1h is None:
            return None
        
        abs_change = abs(change_1h)
        
        if abs_change >= threshold_critical:
            return 'CRITICAL'
        elif abs_change >= threshold_high:
            return 'HIGH'
        
        return None
    
    @staticmethod
    def rank_pairs_by_change(
        rates: Dict[str, Dict],
        change_key: str = 'change_24h'
    ) -> List[Tuple[str, float]]:
        """
        Rank currency pairs by their change percentage.
        
        Args:
            rates: Dictionary of pair -> rate data
            change_key: Which change metric to rank by
            
        Returns:
            List of (pair, change) tuples sorted by change
        """
        changes = []
        for pair, data in rates.items():
            change = data.get(change_key)
            if change is not None:
                changes.append((pair, change))
        
        return sorted(changes, key=lambda x: x[1], reverse=True)
    
    @staticmethod
    def calculate_volatility(
        rates: List[float],
        window: int = 20
    ) -> float:
        """
        Calculate rolling volatility of rates.
        
        Args:
            rates: List of historical rates
            window: Rolling window size
            
        Returns:
            Annualized volatility percentage
        """
        if len(rates) < window:
            return 0.0
        
        # Calculate log returns
        returns = np.diff(np.log(rates))
        
        if len(returns) < window:
            return 0.0
        
        # Rolling standard deviation
        std = np.std(returns[-window:])
        
        # Annualize (assuming 5-minute intervals, ~250 trading days)
        # 250 days * 24 hours * 12 intervals/hour = 72,000 intervals
        annualized = std * np.sqrt(72000) * 100
        
        return round(annualized, 2)
    
    @staticmethod
    def format_rate(
        pair: str,
        rate: float
    ) -> str:
        """
        Format a rate for display with appropriate decimal places.
        
        Args:
            pair: Currency pair
            rate: Exchange rate
            
        Returns:
            Formatted string
        """
        decimals = get_decimal_places(pair)
        return f"{rate:.{decimals}f}"
    
    @staticmethod
    def format_change(change: Optional[float]) -> str:
        """
        Format a percentage change for display.
        
        Args:
            change: Percentage change
            
        Returns:
            Formatted string with sign
        """
        if change is None:
            return "N/A"
        
        sign = '+' if change >= 0 else ''
        return f"{sign}{change:.2f}%"
