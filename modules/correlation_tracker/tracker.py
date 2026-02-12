"""
Cross-Asset Correlation Tracker

Computes rolling correlations between asset classes and detects
breakdowns that signal regime shifts.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from loguru import logger

from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / '.env')

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

from modules.utils.timezone import get_current_time


# Correlation pairs to monitor
CORRELATION_PAIRS = {
    "stocks_bonds": {
        "name": "Stocks / Bonds",
        "series_a": "SP500",
        "series_b": "DGS10",
        "description": "S&P 500 vs 10Y Treasury Yield",
        "normal_correlation": 0.3,
        "breakdown_explanation": "Negative stock-bond correlation = flight to quality. Positive = inflation/growth regime.",
        "inversion_significance": "When stocks and bonds sell off together, it signals inflation fears dominating growth fears.",
    },
    "stocks_vix": {
        "name": "Stocks / VIX",
        "series_a": "SP500",
        "series_b": "VIXCLS",
        "description": "S&P 500 vs VIX (inverse expected)",
        "normal_correlation": -0.7,
        "breakdown_explanation": "VIX usually moves inversely to stocks. Positive correlation = regime breakdown.",
        "inversion_significance": "If stocks rise alongside VIX, it suggests hedging demand despite rally — smart money is nervous.",
    },
    "dollar_gold": {
        "name": "Dollar / Gold",
        "series_a": "DTWEXBGS",
        "series_b": "GOLDAMGBD228NLBM",
        "description": "USD Index vs Gold Price",
        "normal_correlation": -0.4,
        "breakdown_explanation": "Dollar and gold typically move inversely. Both rising = extreme uncertainty.",
        "inversion_significance": "Dollar and gold rising together signals global safe-haven demand from different investor bases.",
    },
    "yields_2y_10y": {
        "name": "2Y / 10Y Yield",
        "series_a": "DGS2",
        "series_b": "DGS10",
        "description": "2Y vs 10Y Treasury Yield co-movement",
        "normal_correlation": 0.9,
        "breakdown_explanation": "Short and long yields usually move together. Divergence = policy vs growth disconnect.",
        "inversion_significance": "When 2Y rises but 10Y falls, market expects tight policy will cause recession.",
    },
    "oil_inflation_expectations": {
        "name": "Oil / Breakevens",
        "series_a": "DCOILWTICO",
        "series_b": "T5YIE",
        "description": "WTI Crude vs 5Y Breakeven Inflation",
        "normal_correlation": 0.5,
        "breakdown_explanation": "Oil and inflation expectations usually co-move. Divergence signals supply vs demand dynamics.",
        "inversion_significance": "Rising breakevens without oil support suggests services/shelter inflation driving expectations.",
    },
    "nasdaq_sp500": {
        "name": "NASDAQ / S&P 500",
        "series_a": "NASDAQCOM",
        "series_b": "SP500",
        "description": "NASDAQ vs S&P 500 (breadth indicator)",
        "normal_correlation": 0.95,
        "breakdown_explanation": "Divergence signals rotation between growth and value sectors.",
        "inversion_significance": "NASDAQ underperforming S&P signals rotation from growth to value — often happens late in rate hiking cycles.",
    },
}


class CorrelationResult:
    """A single correlation computation result."""

    def __init__(
        self,
        pair_id: str,
        name: str,
        description: str,
        correlation_30d: Optional[float],
        correlation_90d: Optional[float],
        normal_correlation: float,
        deviation_30d: Optional[float],
        is_breakdown: bool,
        data_points: int,
        series_a_change: Optional[float] = None,
        series_b_change: Optional[float] = None,
    ):
        self.pair_id = pair_id
        self.name = name
        self.description = description
        self.correlation_30d = correlation_30d
        self.correlation_90d = correlation_90d
        self.normal_correlation = normal_correlation
        self.deviation_30d = deviation_30d
        self.is_breakdown = is_breakdown
        self.data_points = data_points
        self.series_a_change = series_a_change
        self.series_b_change = series_b_change

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "name": self.name,
            "description": self.description,
            "correlation_30d": round(self.correlation_30d, 3) if self.correlation_30d is not None else None,
            "correlation_90d": round(self.correlation_90d, 3) if self.correlation_90d is not None else None,
            "normal_correlation": self.normal_correlation,
            "deviation_30d": round(self.deviation_30d, 3) if self.deviation_30d is not None else None,
            "is_breakdown": self.is_breakdown,
            "data_points": self.data_points,
            "series_a_change_30d": round(self.series_a_change, 2) if self.series_a_change is not None else None,
            "series_b_change_30d": round(self.series_b_change, 2) if self.series_b_change is not None else None,
        }


class CorrelationTracker:
    """
    Monitors cross-asset correlations and detects breakdowns.
    """

    # Threshold for considering a correlation "broken"
    BREAKDOWN_THRESHOLD = 0.5  # deviation from normal > 0.5

    def __init__(self, db: Session):
        self.db = db

    def _get_series_data(self, series_id: str, days: int = 120) -> Optional[Any]:
        """Fetch indicator time series data."""
        try:
            from modules.economic_indicators import IndicatorStorage
            storage = IndicatorStorage(self.db)

            start = datetime.utcnow().date() - timedelta(days=days)
            df = storage.get_values(series_id, start_date=start)
            return df
        except Exception as e:
            logger.debug(f"Could not fetch {series_id}: {e}")
            return None

    def _compute_correlation(
        self,
        values_a: Any,
        values_b: Any,
        window: int = 30,
    ) -> Optional[float]:
        """Compute rolling correlation over a window."""
        if not NUMPY_AVAILABLE:
            return None

        try:
            # Align by date
            import pandas as pd

            df_a = values_a.set_index('date')['value'].rename('a')
            df_b = values_b.set_index('date')['value'].rename('b')

            merged = pd.concat([df_a, df_b], axis=1).dropna()

            if len(merged) < max(10, window // 2):
                return None

            # Use last `window` data points
            recent = merged.tail(window)

            if len(recent) < 10:
                return None

            corr = float(recent['a'].corr(recent['b']))
            return corr if not np.isnan(corr) else None

        except Exception as e:
            logger.debug(f"Correlation computation error: {e}")
            return None

    def _compute_change(self, values: Any, days: int = 30) -> Optional[float]:
        """Compute percentage change over a period."""
        try:
            if values is None or values.empty or len(values) < 2:
                return None
            vals = values['value'].values
            if len(vals) >= days:
                start_val = float(vals[-days])
                end_val = float(vals[-1])
            else:
                start_val = float(vals[0])
                end_val = float(vals[-1])

            if abs(start_val) > 0.001:
                return ((end_val - start_val) / abs(start_val)) * 100
            return None
        except Exception:
            return None

    def compute_all_correlations(self) -> Dict[str, Any]:
        """Compute correlations for all monitored pairs."""
        results = []
        breakdowns = []

        for pair_id, config in CORRELATION_PAIRS.items():
            series_a_data = self._get_series_data(config["series_a"])
            series_b_data = self._get_series_data(config["series_b"])

            if series_a_data is None or series_b_data is None:
                continue

            if series_a_data.empty or series_b_data.empty:
                continue

            corr_30d = self._compute_correlation(series_a_data, series_b_data, window=30)
            corr_90d = self._compute_correlation(series_a_data, series_b_data, window=90)

            change_a = self._compute_change(series_a_data, days=30)
            change_b = self._compute_change(series_b_data, days=30)

            normal = config["normal_correlation"]
            deviation = None
            is_breakdown = False

            if corr_30d is not None:
                deviation = corr_30d - normal
                # Check for sign flip or large deviation
                is_breakdown = abs(deviation) > self.BREAKDOWN_THRESHOLD

                # Sign flip is always a breakdown
                if normal > 0 and corr_30d < -0.1:
                    is_breakdown = True
                elif normal < 0 and corr_30d > 0.1:
                    is_breakdown = True

            data_points = min(
                len(series_a_data) if series_a_data is not None else 0,
                len(series_b_data) if series_b_data is not None else 0,
            )

            result = CorrelationResult(
                pair_id=pair_id,
                name=config["name"],
                description=config["description"],
                correlation_30d=corr_30d,
                correlation_90d=corr_90d,
                normal_correlation=normal,
                deviation_30d=deviation,
                is_breakdown=is_breakdown,
                data_points=data_points,
                series_a_change=change_a,
                series_b_change=change_b,
            )

            results.append(result)
            if is_breakdown:
                breakdowns.append({
                    "pair": config["name"],
                    "pair_id": pair_id,
                    "correlation_30d": corr_30d,
                    "normal": normal,
                    "deviation": deviation,
                    "explanation": config["breakdown_explanation"],
                    "significance": config["inversion_significance"],
                })

        return {
            "correlations": [r.to_dict() for r in results],
            "breakdowns": breakdowns,
            "breakdown_count": len(breakdowns),
            "pairs_tracked": len(results),
            "timestamp": get_current_time().isoformat(),
        }

    def get_breakdown_alerts(self) -> List[Dict[str, Any]]:
        """Get only the correlation breakdowns (for alert integration)."""
        result = self.compute_all_correlations()
        return result.get("breakdowns", [])
