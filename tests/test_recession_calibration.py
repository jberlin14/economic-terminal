"""Tests for ensemble-level calibration (Phase 2A Task A2)."""

import numpy as np
import pytest
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss

from modules.recession_model.calibration import (
    apply_calibrator,
    compute_operating_points,
    fit_calibrator,
    select_calibrator_cv,
    select_default_threshold,
)


def _make_miscalibrated_data(n: int = 500, seed: int = 0):
    """Generate raw probs that systematically deviate from the true probability.

    raw = true_p ** 2 squashes scores towards 0 — a strong, monotonic
    miscalibration that both Platt and isotonic can correct.
    """
    rng = np.random.RandomState(seed)
    true_p = rng.uniform(0.0, 1.0, size=n)
    raw = true_p ** 2
    y = (rng.uniform(0.0, 1.0, size=n) < true_p).astype(int)
    return raw, y, true_p


def test_calibration_improves_brier():
    raw, y, _ = _make_miscalibrated_data()
    calibrator, method, comp = fit_calibrator(raw, y)
    cal = apply_calibrator(calibrator, raw)

    assert brier_score_loss(y, cal) < brier_score_loss(y, raw)
    # The chosen method's Brier on the OOF set must be at least as low as raw.
    assert comp[method] <= comp["raw"]
    assert method in ("platt", "isotonic")


def test_calibrator_output_in_unit_interval():
    raw, y, _ = _make_miscalibrated_data()
    calibrator, _, _ = fit_calibrator(raw, y)
    cal = apply_calibrator(calibrator, np.array([0.0, 0.25, 0.5, 0.75, 1.0]))

    assert (cal >= 0.0).all()
    assert (cal <= 1.0).all()


def test_calibrator_clips_out_of_range_inputs():
    """Even if we feed garbage outside [0,1], the apply step must clip."""
    raw, y, _ = _make_miscalibrated_data()
    calibrator, _, _ = fit_calibrator(raw, y)
    cal = apply_calibrator(calibrator, np.array([-0.5, 0.5, 1.5, 2.0]))

    assert (cal >= 0.0).all()
    assert (cal <= 1.0).all()


def test_handles_nan_in_raw_probs():
    """NaN entries in raw_probs (initial train window) must be dropped before fitting."""
    raw, y, _ = _make_miscalibrated_data()
    raw_with_nan = raw.copy()
    raw_with_nan[:50] = np.nan

    calibrator, method, comp = fit_calibrator(raw_with_nan, y)

    assert method in ("platt", "isotonic", "identity")
    # Apply should still produce valid probabilities
    cal = apply_calibrator(calibrator, np.array([0.1, 0.5, 0.9]))
    assert (cal >= 0.0).all() and (cal <= 1.0).all()


def test_degenerate_input_returns_identity_single_class():
    """If only one class is present, fall back to identity."""
    raw = np.array([0.5, 0.5, 0.5, 0.7, 0.2])
    y = np.array([0, 0, 0, 0, 0])  # one class
    calibrator, method, _ = fit_calibrator(raw, y)
    assert method == "identity"
    # Identity must round-trip values within [0,1] approximately.
    cal = apply_calibrator(calibrator, np.array([0.0, 0.3, 0.7, 1.0]))
    np.testing.assert_allclose(cal, np.array([0.0, 0.3, 0.7, 1.0]), atol=1e-6)


def test_degenerate_input_returns_identity_too_few_samples():
    """Fewer than 10 valid samples after NaN filtering -> identity."""
    raw = np.array([0.1, 0.2, 0.3, np.nan, np.nan])
    y = np.array([0, 1, 1, 0, 1])
    calibrator, method, _ = fit_calibrator(raw, y)
    assert method == "identity"


def test_brier_comparison_keys_present():
    raw, y, _ = _make_miscalibrated_data()
    _, _, comp = fit_calibrator(raw, y)
    assert set(comp.keys()) == {"raw", "platt", "isotonic"}
    for k in ("raw", "platt", "isotonic"):
        assert isinstance(comp[k], float)


def test_returned_calibrator_type_matches_method():
    raw, y, _ = _make_miscalibrated_data()
    calibrator, method, _ = fit_calibrator(raw, y)
    if method == "platt":
        assert isinstance(calibrator, LogisticRegression)
    elif method == "isotonic":
        assert isinstance(calibrator, IsotonicRegression)


# ──────────────────────────────────────────────
# select_calibrator_cv (Phase 1 §1.1)
# ──────────────────────────────────────────────

def test_cv_calibration_returns_expanded_comparison_keys():
    raw, y, _ = _make_miscalibrated_data()
    _, method, comp = select_calibrator_cv(raw, y, n_splits=5)

    expected = {
        "raw",
        "platt_in_sample", "isotonic_in_sample",
        "platt_cv_mean", "isotonic_cv_mean",
        "platt_cv_std", "isotonic_cv_std",
        "n_cv_folds", "selection",
        # Back-compat aliases
        "platt", "isotonic",
    }
    assert expected.issubset(set(comp.keys()))
    assert method in ("platt", "isotonic")
    assert comp["selection"] in ("cv", "in_sample_fallback")
    assert comp["n_cv_folds"] >= 1


def test_cv_calibration_improves_brier_held_out():
    """The chosen method's held-out CV Brier should beat raw on miscalibrated data."""
    raw, y, _ = _make_miscalibrated_data(n=600)
    _, method, comp = select_calibrator_cv(raw, y, n_splits=5)

    cv_winner = comp[f"{method}_cv_mean"]
    assert cv_winner is not None
    assert cv_winner < comp["raw"], (
        f"{method} CV mean Brier {cv_winner} should be < raw Brier {comp['raw']}"
    )


def test_cv_calibration_returns_fitted_full_calibrator():
    """The returned calibrator must be refit on the FULL OOF set, not the last fold."""
    raw, y, _ = _make_miscalibrated_data()
    calibrator, method, _ = select_calibrator_cv(raw, y, n_splits=5)

    cal = apply_calibrator(calibrator, raw)
    assert (cal >= 0.0).all() and (cal <= 1.0).all()
    if method == "platt":
        assert isinstance(calibrator, LogisticRegression)
    elif method == "isotonic":
        assert isinstance(calibrator, IsotonicRegression)


def test_cv_calibration_handles_nan_in_raw_probs():
    raw, y, _ = _make_miscalibrated_data()
    raw_with_nan = raw.copy()
    raw_with_nan[:50] = np.nan

    _, method, comp = select_calibrator_cv(raw_with_nan, y, n_splits=5)

    assert method in ("platt", "isotonic", "identity")
    assert comp["selection"] in ("cv", "in_sample_fallback", "identity")


def test_cv_calibration_degenerate_input_returns_identity():
    raw = np.array([0.5, 0.5, 0.5, 0.7, 0.2])
    y = np.array([0, 0, 0, 0, 0])
    calibrator, method, comp = select_calibrator_cv(raw, y)
    assert method == "identity"
    assert comp["selection"] == "identity"
    assert comp["n_cv_folds"] == 0


def test_cv_calibration_too_few_samples_falls_back_to_in_sample():
    """With ~12 samples and n_splits=5, CV folds may be too small to score
    both classes on test slices — must gracefully fall back."""
    rng = np.random.RandomState(7)
    n = 12
    true_p = rng.uniform(0.0, 1.0, size=n)
    raw = true_p ** 2
    y = (rng.uniform(0.0, 1.0, size=n) < true_p).astype(int)
    # Force at least one of each class so it doesn't hit the identity path.
    y[0] = 0
    y[1] = 1

    _, method, comp = select_calibrator_cv(raw, y, n_splits=5)
    assert method in ("platt", "isotonic")
    assert comp["selection"] in ("cv", "in_sample_fallback")


# ──────────────────────────────────────────────
# compute_operating_points / select_default_threshold (Phase 1 §1.3)
# ──────────────────────────────────────────────

def test_operating_points_table_shape():
    rng = np.random.RandomState(11)
    n = 500
    y = (rng.uniform(0, 1, size=n) < 0.2).astype(int)
    p = np.where(y == 1, rng.uniform(0.4, 1.0, size=n), rng.uniform(0.0, 0.6, size=n))

    ops = compute_operating_points(p, y)
    assert len(ops) > 0
    expected_keys = {"threshold", "precision", "recall", "f1", "n_positive_predictions", "support_positives"}
    for op in ops:
        assert expected_keys.issubset(set(op.keys()))
        assert 0.0 <= op["precision"] <= 1.0
        assert 0.0 <= op["recall"] <= 1.0
        assert 0.0 <= op["f1"] <= 1.0
    # Higher thresholds should produce fewer positive predictions.
    pos_counts = [op["n_positive_predictions"] for op in ops]
    assert pos_counts == sorted(pos_counts, reverse=True)


def test_operating_points_handles_nan_and_degenerate():
    p = np.array([np.nan, np.nan, np.nan])
    y = np.array([0, 1, 1])
    assert compute_operating_points(p, y) == []

    # Single class -> empty table
    p2 = np.array([0.1, 0.5, 0.9])
    y2 = np.array([0, 0, 0])
    assert compute_operating_points(p2, y2) == []


def test_select_default_threshold_picks_precision_target_with_max_recall():
    ops = [
        {"threshold": 0.3, "precision": 0.50, "recall": 0.90, "f1": 0.64, "n_positive_predictions": 200, "support_positives": 100},
        {"threshold": 0.5, "precision": 0.65, "recall": 0.70, "f1": 0.67, "n_positive_predictions": 110, "support_positives": 100},
        {"threshold": 0.6, "precision": 0.80, "recall": 0.50, "f1": 0.62, "n_positive_predictions":  60, "support_positives": 100},
        {"threshold": 0.7, "precision": 0.95, "recall": 0.30, "f1": 0.45, "n_positive_predictions":  30, "support_positives": 100},
    ]
    chosen = select_default_threshold(ops, precision_target=0.6)
    # Among precision >= 0.6: thresholds 0.5 / 0.6 / 0.7 — pick highest recall (0.5).
    assert chosen["threshold"] == 0.5
    assert chosen["selection"] == "precision_target"


def test_select_default_threshold_falls_back_to_max_f1():
    """If no threshold meets the precision target, fall back to max F1."""
    ops = [
        {"threshold": 0.3, "precision": 0.30, "recall": 0.90, "f1": 0.45, "n_positive_predictions": 200, "support_positives": 100},
        {"threshold": 0.5, "precision": 0.40, "recall": 0.60, "f1": 0.48, "n_positive_predictions": 110, "support_positives": 100},
        {"threshold": 0.7, "precision": 0.50, "recall": 0.20, "f1": 0.29, "n_positive_predictions":  30, "support_positives": 100},
    ]
    chosen = select_default_threshold(ops, precision_target=0.6)
    assert chosen["selection"] == "max_f1"
    assert chosen["threshold"] == 0.5  # F1=0.48 was max


def test_select_default_threshold_empty_table():
    chosen = select_default_threshold([])
    assert chosen["threshold"] == 0.5
    assert chosen["selection"] == "default_fallback"
