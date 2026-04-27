"""Ensemble-level probability calibration.

Fits a calibrator on the walk-forward OOF probabilities so the published
`calibrated_ensemble` value is an honest probability — i.e. when the model
says "60%", historical OOF data shows roughly 60% of those samples were
recessions within the horizon.

Two calibrators are fit per horizon:

  - Platt scaling (sklearn.linear_model.LogisticRegression on the raw
    prob as a single feature). Parametric, learns sigmoid(a*raw + b).
    Works well when miscalibration is monotonic + sigmoidal.
  - Isotonic regression (sklearn.isotonic.IsotonicRegression with
    out_of_bounds='clip'). Non-parametric, fits any monotone shape but
    can overfit on small samples.

Selection: pick the calibrator with the lower Brier score on the same
OOF set used to fit them. Tie-break favors isotonic.
"""

from typing import Any, Dict, Tuple

import numpy as np
from loguru import logger
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss


def _filter_nan(raw_probs: np.ndarray, y_true: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Drop indices where raw_probs is NaN (initial train window had no OOF prediction)."""
    raw = np.asarray(raw_probs, dtype=float)
    y = np.asarray(y_true)
    mask = ~np.isnan(raw)
    return raw[mask], y[mask]


def _fit_platt(raw: np.ndarray, y: np.ndarray) -> LogisticRegression:
    """Fit a 1-D logistic regression. C=1e6 for minimal regularization
    (we want the sigmoid to fit the empirical mapping, not be pulled towards 0)."""
    lr = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000)
    lr.fit(raw.reshape(-1, 1), y)
    return lr


def _fit_isotonic(raw: np.ndarray, y: np.ndarray) -> IsotonicRegression:
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(raw, y)
    return iso


def _platt_predict(model: LogisticRegression, raw: np.ndarray) -> np.ndarray:
    return model.predict_proba(raw.reshape(-1, 1))[:, 1]


def _identity_calibrator() -> IsotonicRegression:
    """A no-op calibrator: fit on (x=[0,1], y=[0,1]) so apply() is identity."""
    identity = IsotonicRegression(out_of_bounds="clip")
    identity.fit(np.array([0.0, 1.0]), np.array([0.0, 1.0]))
    return identity


def fit_calibrator(
    raw_probs: np.ndarray,
    y_true: np.ndarray,
) -> Tuple[Any, str, Dict[str, float]]:
    """
    Fit Platt and isotonic calibrators on (raw_probs, y_true) and pick
    the one with the lower Brier score on the same OOF set.

    Tie-break: isotonic wins if Brier scores are equal.

    Returns (fitted_calibrator, method_name, brier_comparison).

    brier_comparison keys:
      - raw: Brier of raw_probs against y
      - platt: Brier after Platt scaling
      - isotonic: Brier after isotonic regression

    Special case: if there are fewer than 10 valid samples or only one
    class is present, returns an identity calibrator and method='identity'.
    """
    raw, y = _filter_nan(raw_probs, y_true)

    if len(raw) < 10 or len(np.unique(y)) < 2:
        logger.warning(
            f"fit_calibrator: degenerate input (n={len(raw)}, classes={np.unique(y)}). "
            f"Returning identity calibrator."
        )
        comp = {"raw": float("nan"), "platt": float("nan"), "isotonic": float("nan")}
        return _identity_calibrator(), "identity", comp

    raw_brier = float(brier_score_loss(y, raw))

    platt = _fit_platt(raw, y)
    platt_probs = _platt_predict(platt, raw)
    platt_brier = float(brier_score_loss(y, platt_probs))

    iso = _fit_isotonic(raw, y)
    iso_probs = iso.predict(raw)
    iso_brier = float(brier_score_loss(y, iso_probs))

    comparison = {
        "raw": round(raw_brier, 6),
        "platt": round(platt_brier, 6),
        "isotonic": round(iso_brier, 6),
    }

    # Pick the lower-Brier calibrator. Tie-break: isotonic.
    if platt_brier < iso_brier:
        return platt, "platt", comparison
    return iso, "isotonic", comparison


def apply_calibrator(calibrator: Any, raw_probs: np.ndarray) -> np.ndarray:
    """Apply the fitted calibrator. Output clipped to [0, 1].

    Accepts either a LogisticRegression (Platt) or IsotonicRegression
    (also covers the 'identity' case, which is just an isotonic fit on
    the diagonal). Unknown types pass through with a warning.
    """
    raw = np.asarray(raw_probs, dtype=float)
    if isinstance(calibrator, LogisticRegression):
        out = _platt_predict(calibrator, raw)
    elif isinstance(calibrator, IsotonicRegression):
        out = calibrator.predict(raw)
    else:
        logger.warning(
            f"apply_calibrator: unknown calibrator type {type(calibrator)}, "
            f"returning raw probabilities unchanged."
        )
        out = raw
    return np.clip(out, 0.0, 1.0)
