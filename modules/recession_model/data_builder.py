"""
Recession Model Data Builder

Fetches ~65 years of FRED data and engineers 80+ features for training
multi-model recession probability classifiers.

Uses USREC (NBER recession indicator) as the label source and builds
forward-looking targets for 3-month, 6-month, and 12-month horizons.

Smart NaN handling: features are grouped by availability era so
pre-1986 data (which lacks some series) is preserved with
forward-fill and era-aware imputation.

Feature engineering and FRED series configuration live in `features.py` —
this module orchestrates fetch → resample → engineer → target-build.
"""

import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from fredapi import Fred
from loguru import logger

from .features import (
    FEATURE_SERIES,
    RECESSION_SERIES,
    START_DATE,
    HORIZONS,
    CORE_REQUIRED,
    engineer_features,
    get_feature_columns,
)


class RecessionDataBuilder:
    """Fetches FRED data and engineers features for recession model training."""

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.getenv("FRED_API_KEY")
        if not key:
            raise ValueError("FRED_API_KEY required for data building")
        self.fred = Fred(api_key=key)

    def build_dataset(self) -> Tuple[pd.DataFrame, Dict]:
        """
        Build the full training dataset.

        Returns:
            (DataFrame with features + targets, metadata dict)
        """
        logger.info("Building recession model dataset from FRED...")

        raw = self._fetch_all_series()
        recession = self._fetch_recession_indicator()

        df = self._merge_to_monthly(raw, recession)
        df = engineer_features(df)
        df = self._build_targets(df)

        feature_cols = get_feature_columns(df)

        # Smart NaN handling: forward-fill then fill remaining with 0
        # This preserves pre-1986 rows where Tier 3/4 series don't exist yet
        for col in feature_cols:
            df[col] = df[col].ffill()
            df[col] = df[col].fillna(0)

        target_cols = [f"recession_{h}m" for h in HORIZONS]

        # Only require core features + targets to be non-null
        core_engineered = []
        for col in feature_cols:
            base = col.split("_")[0] if "_" in col else col
            if base in CORE_REQUIRED or col in CORE_REQUIRED:
                core_engineered.append(col)

        # Drop rows where targets are NaN (end of series) or core features missing
        drop_cols = target_cols + (core_engineered[:5] if core_engineered else [])
        df = df.dropna(subset=drop_cols)

        # Final safety: replace any remaining NaN/inf
        df[feature_cols] = df[feature_cols].replace([np.inf, -np.inf], 0).fillna(0)

        metadata = {
            "start_date": df.index.min().isoformat(),
            "end_date": df.index.max().isoformat(),
            "n_samples": len(df),
            "n_features": len(feature_cols),
            "feature_names": feature_cols,
            "target_columns": target_cols,
            "recession_rate": {
                f"{h}m": float(df[f"recession_{h}m"].mean())
                for h in HORIZONS
            },
            "series_fetched": list(raw.keys()),
            "series_missing": [s for s in FEATURE_SERIES if s not in raw],
        }

        logger.success(
            f"Dataset built: {len(df)} samples, {len(feature_cols)} features, "
            f"date range {metadata['start_date']} to {metadata['end_date']}"
        )

        return df, metadata

    def _fetch_all_series(self) -> Dict[str, pd.Series]:
        """Fetch all feature series from FRED."""
        raw = {}
        for series_id, name in FEATURE_SERIES.items():
            try:
                data = self.fred.get_series(
                    series_id,
                    observation_start=START_DATE,
                )
                if data is not None and len(data) > 0:
                    raw[series_id] = data
                    logger.debug(
                        f"Fetched {series_id} ({name}): {len(data)} obs "
                        f"from {data.index.min().date()}"
                    )
                else:
                    logger.warning(f"Empty data for {series_id}")
            except Exception as e:
                logger.warning(f"Failed to fetch {series_id}: {e}")
        return raw

    def _fetch_recession_indicator(self) -> pd.Series:
        """Fetch NBER recession dates."""
        data = self.fred.get_series(RECESSION_SERIES, observation_start=START_DATE)
        logger.debug(f"Fetched USREC: {len(data)} observations")
        return data

    def _merge_to_monthly(
        self, raw: Dict[str, pd.Series], recession: pd.Series
    ) -> pd.DataFrame:
        """Resample all series to monthly frequency and merge."""
        monthly = {}

        for series_id, data in raw.items():
            s = data.dropna()
            if s.empty:
                continue
            # Quarterly data gets forward-filled to monthly
            if series_id in ("BOGZ1FL072052006Q",):
                resampled = s.resample("ME").ffill()
            else:
                resampled = s.resample("ME").last()
            monthly[series_id] = resampled

        df = pd.DataFrame(monthly)

        # Add recession indicator
        rec_monthly = recession.resample("ME").max()
        df["USREC"] = rec_monthly

        return df

    def _build_targets(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build forward-looking recession targets."""
        rec = df["USREC"]
        for h in HORIZONS:
            # Was there a recession in any of the next h months?
            df[f"recession_{h}m"] = (
                rec.rolling(window=h, min_periods=1)
                .max()
                .shift(-h)
            )
        return df

    def build_current_features(self, feature_names: List[str]) -> Optional[Dict[str, float]]:
        """
        Fetch recent FRED data and engineer features for the latest month.

        Uses the same pipeline as training (fetch → resample → engineer) but
        only pulls the last 15 months of data per series. This guarantees
        feature values match what the model was trained on.

        Args:
            feature_names: The feature names the trained model expects.

        Returns:
            Dict mapping feature name → value for the most recent month,
            or None if core features couldn't be built.
        """
        from datetime import datetime, timedelta

        # 72 months covers 60-month z-score rolling windows + 12-month
        # lookbacks with buffer. Some series (like OECD LEI) lag by
        # 1-2 years on FRED, so a long lookback ensures we capture them.
        lookback_start = (
            datetime.now() - timedelta(days=72 * 31)
        ).strftime("%Y-%m-%d")

        logger.info(f"Fetching recent FRED data from {lookback_start} for live prediction...")

        import time as _time

        raw: Dict[str, pd.Series] = {}
        for i, series_id in enumerate(FEATURE_SERIES):
            # Rate limit: FRED allows 120 req/min, pace at ~2 req/sec
            if i > 0 and i % 10 == 0:
                _time.sleep(1.0)
            try:
                data = self.fred.get_series(
                    series_id, observation_start=lookback_start
                )
                if data is not None and len(data) > 0:
                    raw[series_id] = data
            except Exception as e:
                logger.warning(f"Failed to fetch {series_id} for live prediction: {e}")

        if not raw:
            logger.error("No FRED data fetched for live prediction")
            return None

        # Check core series are present
        core_missing = CORE_REQUIRED - set(raw.keys())
        if core_missing:
            logger.error(f"Missing core series for prediction: {core_missing}")
            return None

        # Build a monthly DataFrame — same logic as training
        monthly: Dict[str, pd.Series] = {}
        for series_id, data in raw.items():
            s = data.dropna()
            if s.empty:
                continue
            if series_id in ("BOGZ1FL072052006Q",):
                resampled = s.resample("ME").ffill()
            else:
                resampled = s.resample("ME").last()
            monthly[series_id] = resampled

        df = pd.DataFrame(monthly)

        # Engineer features — exact same function as training
        df = engineer_features(df)

        # Forward-fill then zero-fill, same as training
        for col in df.columns:
            df[col] = df[col].ffill()
            df[col] = df[col].fillna(0)

        # Take the latest row
        if df.empty:
            logger.error("Empty DataFrame after feature engineering")
            return None

        latest = df.iloc[-1]
        features: Dict[str, float] = {}
        for f in feature_names:
            val = latest.get(f, 0.0)
            if isinstance(val, (int, float, np.integer, np.floating)):
                val = float(val)
            else:
                val = 0.0
            if not np.isfinite(val):
                val = 0.0
            features[f] = val

        n_populated = sum(1 for v in features.values() if v != 0.0)
        logger.info(
            f"Live features built: {n_populated}/{len(feature_names)} non-zero "
            f"(latest month: {df.index[-1].date()})"
        )

        return features
