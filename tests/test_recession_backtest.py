"""Tests for the walk-forward backtest harness."""

import numpy as np
import pytest

from modules.recession_model.backtest import (
    run_walk_forward,
    walk_forward_folds,
)


def test_walk_forward_folds_no_leakage():
    folds = list(walk_forward_folds(
        n_samples=100, initial_train_size=50, step=10, test_size=10,
    ))
    assert len(folds) > 0
    for train_idx, test_idx in folds:
        assert train_idx.max() < test_idx.min(), (
            "Test indices must be strictly later than train"
        )
        # Disjoint
        assert len(set(train_idx) & set(test_idx)) == 0


def test_walk_forward_folds_count():
    # n=100, init=50, step=10, test=10 → folds at [50:60], [60:70],
    # [70:80], [80:90], [90:100] = 5 folds
    folds = list(walk_forward_folds(
        n_samples=100, initial_train_size=50, step=10, test_size=10,
    ))
    assert len(folds) == 5


def test_walk_forward_folds_expanding_window():
    # The training window should grow each fold
    folds = list(walk_forward_folds(
        n_samples=100, initial_train_size=50, step=10, test_size=10,
    ))
    sizes = [len(t) for t, _ in folds]
    assert sizes == sorted(sizes)  # non-decreasing
    assert sizes[-1] > sizes[0]    # strictly grew


def test_run_walk_forward_smoke():
    # Synthetic data with weak signal
    rng = np.random.RandomState(0)
    n = 250
    X = rng.normal(size=(n, 8))
    y = ((X[:, 0] + 0.5 * rng.normal(size=n)) > 0.5).astype(int)
    feature_names = [f"f{i}" for i in range(8)]
    out = run_walk_forward(X, y, horizon=6, feature_names=feature_names)

    assert "oof_probs" in out
    assert out["oof_probs"].shape == (n,)
    # Initial train window has NaN
    assert np.isnan(out["oof_probs"][0])
    # Last sample (in some test fold) has a real value
    assert not np.isnan(out["oof_probs"][-1])

    agg = out["aggregate_metrics"]
    for k in ["f1_mean", "f1_std", "auc_mean", "auc_std", "brier_mean", "brier_std"]:
        assert k in agg
        assert np.isfinite(agg[k]), f"{k} = {agg[k]}"
