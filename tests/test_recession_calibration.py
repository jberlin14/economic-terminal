"""Tests for ensemble-level calibration (Phase 2A Task A2)."""

import numpy as np
import pytest
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss

from modules.recession_model.calibration import apply_calibrator, fit_calibrator


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
