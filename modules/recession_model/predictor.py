"""
Recession Model Predictor

Generates live recession probabilities using current FRED data,
matching the exact feature engineering used in training.

The predictor fetches recent data directly from FRED (not the local DB)
to ensure feature values are consistent with the training pipeline.
Features are cached for 1 hour to avoid FRED rate limiting.
"""

import time
from datetime import datetime
from typing import Dict, Any, Optional

import pandas as pd
from loguru import logger
from sqlalchemy.orm import Session

from .model import RecessionModel
from .data_builder import RecessionDataBuilder
from .drift import compute_feature_drift

# Module-level cache for live features (avoids re-fetching from FRED on every page load)
_feature_cache: Dict[str, Any] = {
    "features": None,
    "timestamp": 0,
    "ttl": 3600,  # 1 hour
}


def _get_cached_features(feature_names) -> Optional[Dict[str, float]]:
    """Return cached features if fresh, otherwise fetch from FRED and cache."""
    now = time.time()
    if (
        _feature_cache["features"] is not None
        and (now - _feature_cache["timestamp"]) < _feature_cache["ttl"]
    ):
        logger.debug("Using cached FRED features for recession prediction")
        return _feature_cache["features"]

    try:
        builder = RecessionDataBuilder()
        features = builder.build_current_features(feature_names)
        if features:
            _feature_cache["features"] = features
            _feature_cache["timestamp"] = now
            logger.info("Refreshed FRED feature cache for recession prediction")
        return features
    except Exception as e:
        logger.error(f"Failed to gather current features: {e}", exc_info=True)
        # Return stale cache if available
        if _feature_cache["features"] is not None:
            logger.warning("Returning stale cached features after FRED error")
            return _feature_cache["features"]
        return None


class RecessionPredictor:
    """Generates live recession probabilities from current FRED data."""

    def __init__(self, db: Session):
        self.db = db
        self.model = RecessionModel()

    def get_current_probability(self) -> Dict[str, Any]:
        """Compute current recession probabilities."""
        if not self.model.load():
            return {
                "trained": False,
                "message": "Model not trained. Use the Train Model button to train.",
            }

        features = _get_cached_features(self.model.feature_names)

        if not features:
            return {"trained": True, "error": "Could not gather current indicator data from FRED"}

        probabilities = self.model.predict(features)

        # Phase 2 §2.5: feature drift score against training-window quantiles.
        # Restrict to the top-20 features by importance to keep the report
        # manageable; fall back to all features if importance metadata is
        # missing.
        top_features = self._top_features_by_importance(limit=20)
        drift = compute_feature_drift(
            features,
            getattr(self.model, "training_quantiles", {}) or {},
            top_features=top_features,
        )

        prob_6m_pct = probabilities.get("ensemble", {}).get("6m", 0)

        # Default threshold for the 6m horizon comes from the calibrated
        # OOF operating-point table (Phase 1 §1.3). The published threshold
        # is in [0,1]; ensemble probabilities are in percent — multiply by 100.
        default_threshold_info = (getattr(self.model, "default_threshold", {}) or {}).get(6, {})
        default_threshold_pct = float(default_threshold_info.get("threshold", 0.5)) * 100
        # "Moderate" band straddles the default threshold by half its distance
        # to zero, with a hard floor at 15% so we don't dilute the "low" band.
        moderate_floor_pct = max(15.0, default_threshold_pct * 0.5)

        if prob_6m_pct >= default_threshold_pct:
            signal, signal_label = "high", "Elevated"
        elif prob_6m_pct >= moderate_floor_pct:
            signal, signal_label = "moderate", "Moderate"
        else:
            signal, signal_label = "low", "Low"

        return {
            "trained": True,
            # `probabilities` is the calibrated ensemble (canonical).
            # `raw_probabilities` is the AUC-weighted raw average for
            # transparency — frontend can show both side-by-side.
            "probabilities": probabilities.get("ensemble", {}),
            "raw_probabilities": probabilities.get("raw_ensemble", {}),
            "model_probabilities": probabilities.get("models", {}),
            "uncertainty": probabilities.get("uncertainty", {}),
            "signal": signal,
            "signal_label": signal_label,
            "decision_threshold_6m": {
                "threshold_pct": round(default_threshold_pct, 1),
                "moderate_floor_pct": round(moderate_floor_pct, 1),
                "selection": default_threshold_info.get("selection"),
                "precision": default_threshold_info.get("precision"),
                "recall": default_threshold_info.get("recall"),
                "f1": default_threshold_info.get("f1"),
            },
            "feature_snapshot": {
                k: round(v, 4) if isinstance(v, float) else v
                for k, v in features.items()
            },
            "drift": drift,
            "model_info": self.model.get_model_info(),
        }

    def _top_features_by_importance(self, limit: int = 20) -> list:
        """Pull the top-K feature names from the random-forest importance
        list at the 6m horizon (the canonical horizon for the page banner).
        Falls back to logistic coefficients, then to all features."""
        metrics_6m = (self.model.metrics or {}).get(6, {})
        for mt in ("random_forest", "gradient_boosting", "logistic"):
            entry = metrics_6m.get(mt) or {}
            fi = entry.get("feature_importance")
            if isinstance(fi, list) and fi:
                names = [r.get("feature") for r in fi[:limit] if r.get("feature")]
                if names:
                    return names
        return list(self.model.feature_names or [])[:limit]

    def get_historical_probabilities(self) -> Dict[str, Any]:
        """Generate historical probability series for charting.

        Appends the current live prediction to the end of the training history
        so the chart bridges from the training data cutoff to the present.
        """
        if not self.model.load():
            return {"trained": False}

        try:
            builder = RecessionDataBuilder()
            df, _ = builder.build_dataset()
            history = self.model.predict_history(df)

            dates = [d.isoformat() for d in history.index]
            prob_3m = history["prob_3m"].tolist()
            prob_6m = history["prob_6m"].tolist()
            prob_12m = history["prob_12m"].tolist()
            actual_recession = (
                history.get("actual_recession", pd.Series(dtype=float))
                .fillna(0)
                .astype(int)
                .tolist()
            )

            # Bridge the gap: append current live prediction as latest data point
            try:
                live_features = _get_cached_features(self.model.feature_names)
                if live_features:
                    live_probs = self.model.predict(live_features)
                    ensemble = live_probs.get("ensemble", {})
                    if ensemble:
                        today = datetime.now().strftime("%Y-%m-%d")
                        # Only append if the live date is after the last history date
                        if not dates or today > dates[-1]:
                            dates.append(today)
                            prob_3m.append(ensemble.get("3m", 0))
                            prob_6m.append(ensemble.get("6m", 0))
                            prob_12m.append(ensemble.get("12m", 0))
                            actual_recession.append(0)  # No official NBER call yet
            except Exception as e:
                logger.warning(f"Could not append live prediction to history: {e}")

            return {
                "trained": True,
                "dates": dates,
                "prob_3m": prob_3m,
                "prob_6m": prob_6m,
                "prob_12m": prob_12m,
                "actual_recession": actual_recession,
            }
        except Exception as e:
            logger.error(f"Failed to generate historical probabilities: {e}")
            return {"trained": True, "error": str(e)}
