"""Tests for feature drift monitoring (Phase 2 §2.5)."""
import numpy as np
import pandas as pd

from modules.recession_model.drift import (
    compute_feature_drift,
    compute_training_quantiles,
)


def _quantiles_from_normal(mean: float = 0.0, sd: float = 1.0, n: int = 1000):
    rng = np.random.RandomState(0)
    s = pd.Series(rng.normal(mean, sd, size=n))
    return {
        "q01": float(s.quantile(0.01)),
        "q25": float(s.quantile(0.25)),
        "q50": float(s.quantile(0.50)),
        "q75": float(s.quantile(0.75)),
        "q99": float(s.quantile(0.99)),
        "std": float(s.std()),
    }


def test_drift_in_distribution_value_scores_zero():
    q = _quantiles_from_normal(0, 1)
    result = compute_feature_drift(
        live_features={"x": 0.0},
        training_quantiles={"x": q},
    )
    assert len(result["per_feature"]) == 1
    assert result["per_feature"][0]["tail_distance"] == 0.0
    assert result["per_feature"][0]["out_of_bounds"] is False
    assert result["level"] == "ok"
    assert result["drift_score"] == 0.0


def test_drift_far_tail_value_scores_high():
    q = _quantiles_from_normal(0, 1)
    # Value far above q99
    result = compute_feature_drift(
        live_features={"x": 10.0},
        training_quantiles={"x": q},
    )
    pf = result["per_feature"][0]
    assert pf["tail_distance"] == 1.0
    assert pf["out_of_bounds"] is True
    assert result["n_out_of_bounds"] == 1
    assert result["level"] == "alert"


def test_drift_alert_threshold_aggregates_correctly():
    q = _quantiles_from_normal(0, 1)
    # Two features: one extreme, one in-distribution. Mean drift should be ~0.5
    result = compute_feature_drift(
        live_features={"a": 10.0, "b": 0.0},
        training_quantiles={"a": q, "b": q},
    )
    assert result["drift_score"] >= 0.4
    # Sort order: most-drifted first
    assert result["per_feature"][0]["feature"] == "a"
    assert result["per_feature"][1]["feature"] == "b"


def test_drift_top_features_filter():
    q = _quantiles_from_normal(0, 1)
    result = compute_feature_drift(
        live_features={"a": 10.0, "b": 0.0, "c": 5.0},
        training_quantiles={"a": q, "b": q, "c": q},
        top_features=["a", "b"],  # exclude "c"
    )
    feature_names = {pf["feature"] for pf in result["per_feature"]}
    assert feature_names == {"a", "b"}


def test_drift_handles_missing_quantiles_gracefully():
    result = compute_feature_drift(
        live_features={"a": 1.0},
        training_quantiles={},  # no quantiles available
    )
    assert result["drift_score"] == 0.0
    assert result["level"] == "ok"
    assert result["per_feature"] == []


def test_compute_training_quantiles_shape():
    rng = np.random.RandomState(0)
    df = pd.DataFrame({
        "f1": rng.normal(0, 1, size=200),
        "f2": rng.normal(5, 2, size=200),
        "USREC": rng.choice([0, 1], size=200),
    })
    q = compute_training_quantiles(df, ["f1", "f2", "missing_feature"])
    assert "f1" in q
    assert "f2" in q
    assert "missing_feature" not in q
    expected_keys = {"q01", "q25", "q50", "q75", "q99", "std"}
    for f in ("f1", "f2"):
        assert expected_keys.issubset(set(q[f].keys()))
        # Sanity: q25 < q50 < q75
        assert q[f]["q25"] < q[f]["q50"] < q[f]["q75"]
