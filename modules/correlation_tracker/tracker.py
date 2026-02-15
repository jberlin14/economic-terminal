"""
Cross-Asset Correlation Tracker

Monitors key correlation pairs, computes rolling correlations,
and detects breakdowns that signal regime shifts.
"""

import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from loguru import logger

from pathlib import Path
from dotenv import load_dotenv
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / '.env')

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

from modules.utils.timezone import get_current_time


# Correlation pair definitions with normal ranges
CORRELATION_PAIRS = [
    {
        "id": "stocks_bonds",
        "name": "Stocks / Bonds",
        "asset_a": {"ticker": "SPY", "label": "S&P 500 (SPY)"},
        "asset_b": {"ticker": "TLT", "label": "Long-Term Treasuries (TLT)"},
        "normal_range": (-0.5, -0.1),
        "description": "Typically negative — bonds rally when stocks sell off (flight to safety).",
        "breakdown_meaning": "Positive correlation suggests both selling off (rate-driven) or both rallying (liquidity-driven).",
    },
    {
        "id": "stocks_vix",
        "name": "Stocks / VIX",
        "asset_a": {"ticker": "SPY", "label": "S&P 500 (SPY)"},
        "asset_b": {"ticker": "^VIX", "label": "VIX Index"},
        "normal_range": (-0.9, -0.6),
        "description": "Strongly negative — VIX spikes when stocks fall.",
        "breakdown_meaning": "Weakening correlation suggests complacency or structural vol selling.",
    },
    {
        "id": "dollar_gold",
        "name": "Dollar / Gold",
        "asset_a": {"ticker": "UUP", "label": "US Dollar (UUP)"},
        "asset_b": {"ticker": "GLD", "label": "Gold (GLD)"},
        "normal_range": (-0.6, -0.2),
        "description": "Typically negative — gold rises when dollar weakens.",
        "breakdown_meaning": "Both rising suggests global uncertainty driving safe-haven demand across assets.",
    },
    {
        "id": "2y_10y_yields",
        "name": "2Y / 10Y Treasury Yields",
        "asset_a": {"ticker": "^IRX", "label": "2Y Yield Proxy"},
        "asset_b": {"ticker": "^TNX", "label": "10Y Yield"},
        "normal_range": (0.7, 0.95),
        "description": "Highly correlated — both move with rate expectations.",
        "breakdown_meaning": "Divergence signals curve steepening/flattening beyond normal, often a recession signal.",
    },
    {
        "id": "oil_inflation",
        "name": "Oil / Inflation Expectations",
        "asset_a": {"ticker": "USO", "label": "Oil (USO)"},
        "asset_b": {"ticker": "TIP", "label": "TIPS (Inflation Expectations)"},
        "normal_range": (0.3, 0.7),
        "description": "Positively correlated — oil drives inflation expectations.",
        "breakdown_meaning": "Breakdown suggests demand destruction or supply-side distortion.",
    },
    {
        "id": "nasdaq_sp500",
        "name": "NASDAQ / S&P 500",
        "asset_a": {"ticker": "QQQ", "label": "NASDAQ (QQQ)"},
        "asset_b": {"ticker": "SPY", "label": "S&P 500 (SPY)"},
        "normal_range": (0.85, 0.98),
        "description": "Very highly correlated — both broad US equity indices.",
        "breakdown_meaning": "Divergence signals sector rotation (tech vs. value/cyclicals).",
    },
]


class CorrelationTracker:
    """Tracks cross-asset correlations and detects breakdowns."""

    # Cache: {cache_key: (result, timestamp)}
    _cache: Dict[str, tuple] = {}
    _cache_ttl_minutes = 60

    def __init__(self):
        pass

    def analyze(self) -> Dict[str, Any]:
        """Compute correlations for all monitored pairs."""
        if not PANDAS_AVAILABLE:
            return {"error": "pandas not available", "pairs": []}
        if not YFINANCE_AVAILABLE:
            return {"error": "yfinance not available", "pairs": []}

        # Check cache
        cache_key = "correlations"
        if cache_key in self._cache:
            cached_result, cached_time = self._cache[cache_key]
            age = (get_current_time() - cached_time).total_seconds() / 60
            if age < self._cache_ttl_minutes:
                cached_result["from_cache"] = True
                cached_result["cache_age_minutes"] = round(age, 1)
                return cached_result

        start = time.time()
        pairs_results = []
        breakdowns_detected = 0

        for pair_def in CORRELATION_PAIRS:
            try:
                result = self._compute_pair(pair_def)
                if result:
                    if result.get("breakdown_detected"):
                        breakdowns_detected += 1
                    pairs_results.append(result)
            except Exception as e:
                logger.warning(f"Correlation computation failed for {pair_def['id']}: {e}")
                pairs_results.append({
                    "id": pair_def["id"],
                    "name": pair_def["name"],
                    "error": str(e),
                })

        result = {
            "pairs": pairs_results,
            "breakdowns_detected": breakdowns_detected,
            "total_pairs": len(CORRELATION_PAIRS),
            "analyzed_at": get_current_time().isoformat(),
            "elapsed_ms": round((time.time() - start) * 1000),
            "from_cache": False,
        }

        self._cache[cache_key] = (result, get_current_time())
        return result

    def _extract_close_series(self, data: 'pd.DataFrame', ticker: str) -> 'pd.Series':
        """Extract Close price series from yfinance DataFrame, handling multi-level columns."""
        # yfinance may return multi-level columns like (Close, SPY)
        if isinstance(data.columns, pd.MultiIndex):
            # Try (Close, ticker) or just flatten
            if ("Close", ticker) in data.columns:
                return data[("Close", ticker)]
            # Try getting Close level
            if "Close" in data.columns.get_level_values(0):
                close_df = data["Close"]
                if isinstance(close_df, pd.DataFrame):
                    return close_df.iloc[:, 0]
                return close_df
        # Single-level columns
        if "Close" in data.columns:
            col = data["Close"]
            if isinstance(col, pd.DataFrame):
                return col.iloc[:, 0]
            return col
        # Fallback: first column
        return data.iloc[:, 0]

    def _compute_pair(self, pair_def: Dict) -> Optional[Dict[str, Any]]:
        """Compute correlation for a single pair."""
        ticker_a = pair_def["asset_a"]["ticker"]
        ticker_b = pair_def["asset_b"]["ticker"]

        # Fetch 100 days of data (enough for 90-day rolling)
        try:
            data_a = yf.download(ticker_a, period="100d", progress=False, auto_adjust=True)
            data_b = yf.download(ticker_b, period="100d", progress=False, auto_adjust=True)
        except Exception as e:
            logger.warning(f"yfinance download failed for {ticker_a}/{ticker_b}: {e}")
            return None

        if len(data_a) == 0 or len(data_b) == 0:
            return None

        # Extract close price series (handles multi-level columns)
        close_a = self._extract_close_series(data_a, ticker_a)
        close_b = self._extract_close_series(data_b, ticker_b)

        returns_a = close_a.pct_change().dropna()
        returns_b = close_b.pct_change().dropna()

        # Align on common dates
        common_idx = returns_a.index.intersection(returns_b.index)
        if len(common_idx) < 30:
            return None

        ra = returns_a.loc[common_idx]
        rb = returns_b.loc[common_idx]

        # Compute rolling correlations (ensure scalar results)
        corr_30d = float(ra.tail(30).corr(rb.tail(30)))
        corr_90d = float(ra.tail(90).corr(rb.tail(90))) if len(common_idx) >= 90 else None

        # Check for breakdown
        normal_low, normal_high = pair_def["normal_range"]
        breakdown = False
        status = "normal"

        if not np.isnan(corr_30d):
            if corr_30d < normal_low or corr_30d > normal_high:
                breakdown = True
                deviation = min(abs(corr_30d - normal_low), abs(corr_30d - normal_high))
                status = "breakdown" if deviation > 0.3 else "warning"

        return {
            "id": pair_def["id"],
            "name": pair_def["name"],
            "asset_a": pair_def["asset_a"]["label"],
            "asset_b": pair_def["asset_b"]["label"],
            "corr_30d": round(float(corr_30d), 3) if not np.isnan(corr_30d) else None,
            "corr_90d": round(float(corr_90d), 3) if corr_90d is not None and not np.isnan(corr_90d) else None,
            "normal_range": list(pair_def["normal_range"]),
            "status": status,
            "breakdown_detected": breakdown,
            "description": pair_def["description"],
            "breakdown_meaning": pair_def["breakdown_meaning"] if breakdown else None,
        }
