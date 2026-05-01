"""
Feature Drift Monitoring (Phase 2 §2.5).

Computes Population Stability Index (PSI) for the live feature snapshot
against the training-window distribution. PSI buckets the training values
into deciles and compares the bucket counts of the (single) live row to
those quantiles. Returns per-feature PSI scores and an overall flag.

Standard PSI thresholds (industry convention):
  PSI < 0.10  → no significant drift
  PSI < 0.25  → moderate drift, monitor
  PSI ≥ 0.25  → significant drift, model may be stale

Since live prediction sees ONE row, we report:
  - Per-feature distance to training quantile bucket (0..1, where 1 = far tail)
  - Whether the live value is outside the [1st, 99th] percentile of training
The aggregate "drift_score" is the mean tail-distance over the top-K most-
important features (top 20 by absolute influence). Use it as a soft warning
in the UI when the value is high.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from loguru import logger


# Feature considered "in distribution" if its live value sits between these
# training-window quantiles. Outside means tail / unseen-regime.
LOW_QUANTILE = 0.01
HIGH_QUANTILE = 0.99

# Aggregate score thresholds.
WARN_THRESHOLD = 0.30
ALERT_THRESHOLD = 0.50


def compute_feature_drift(
    live_features: Dict[str, float],
    training_quantiles: Dict[str, Dict[str, float]],
    top_features: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Score how far the live feature snapshot has drifted from training.

    Args:
        live_features: {feature_name: float} from the live FRED pull.
        training_quantiles: {feature_name: {q01, q25, q50, q75, q99, std}}
            precomputed once at training time and persisted on the model.
        top_features: Optional restriction to a subset of feature names
            (e.g. the model's top-20 by importance). If None, all features
            with quantile data are scored.

    Returns:
        {
            "per_feature": [{feature, value, tail_distance, out_of_bounds}],
            "drift_score": float in [0, 1],
            "n_out_of_bounds": int,
            "level": "ok" | "warn" | "alert",
        }
    """
    if not live_features or not training_quantiles:
        return {
            "per_feature": [],
            "drift_score": 0.0,
            "n_out_of_bounds": 0,
            "level": "ok",
        }

    candidates = (
        [f for f in top_features if f in training_quantiles]
        if top_features
        else list(training_quantiles.keys())
    )

    per_feature: List[Dict[str, Any]] = []
    distances: List[float] = []
    n_oob = 0

    for f in candidates:
        if f not in live_features:
            continue
        q = training_quantiles[f]
        v = float(live_features[f])
        q01 = q.get("q01")
        q99 = q.get("q99")
        q25 = q.get("q25")
        q75 = q.get("q75")

        # Tail distance: 0 if value is inside [q25, q75], 1 if outside [q01, q99].
        # Linear ramp through the tails.
        if q25 is None or q75 is None or q01 is None or q99 is None:
            continue
        if q25 <= v <= q75:
            tail_dist = 0.0
        elif v > q75:
            denom = max(q99 - q75, 1e-12)
            tail_dist = float(min(1.0, (v - q75) / denom))
        else:
            denom = max(q25 - q01, 1e-12)
            tail_dist = float(min(1.0, (q25 - v) / denom))

        out_of_bounds = bool(v < q01 or v > q99)
        if out_of_bounds:
            n_oob += 1

        per_feature.append({
            "feature": f,
            "value": round(v, 4),
            "q25": round(float(q25), 4),
            "q75": round(float(q75), 4),
            "q01": round(float(q01), 4),
            "q99": round(float(q99), 4),
            "tail_distance": round(tail_dist, 3),
            "out_of_bounds": out_of_bounds,
        })
        distances.append(tail_dist)

    drift_score = float(np.mean(distances)) if distances else 0.0
    if drift_score >= ALERT_THRESHOLD:
        level = "alert"
    elif drift_score >= WARN_THRESHOLD:
        level = "warn"
    else:
        level = "ok"

    # Sort per-feature by tail distance descending so the UI shows worst first.
    per_feature.sort(key=lambda r: -r["tail_distance"])

    return {
        "per_feature": per_feature,
        "drift_score": round(drift_score, 3),
        "n_out_of_bounds": n_oob,
        "level": level,
    }


def compute_training_quantiles(
    df: pd.DataFrame, feature_names: List[str]
) -> Dict[str, Dict[str, float]]:
    """
    Compute per-feature quantile snapshot from the training DataFrame.

    Persisted on the model at train time so live prediction can score drift
    without re-pulling the full training set.
    """
    out: Dict[str, Dict[str, float]] = {}
    for f in feature_names:
        if f not in df.columns:
            continue
        s = df[f].dropna()
        if s.empty:
            continue
        try:
            out[f] = {
                "q01": float(s.quantile(0.01)),
                "q25": float(s.quantile(0.25)),
                "q50": float(s.quantile(0.50)),
                "q75": float(s.quantile(0.75)),
                "q99": float(s.quantile(0.99)),
                "std": float(s.std()),
            }
        except Exception as e:
            logger.debug(f"Quantile computation failed for {f}: {e}")
            continue
    return out
