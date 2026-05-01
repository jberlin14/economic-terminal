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

Two selection paths exist:

  - `fit_calibrator(raw, y)` — legacy. Fits both methods on the full OOF
    set and picks by in-sample Brier. Optimistically biased because the
    same set fits and scores. Kept for tests/back-compat.
  - `select_calibrator_cv(raw, y, n_splits=5)` — preferred. Uses a
    time-ordered K-fold split to score each method's held-out Brier,
    picks the winner by mean held-out Brier, then refits the chosen
    method on the full OOF set for production. Removes the in-sample
    optimism bias documented in the gap-closure plan (Phase 1 §1.1).
"""

from typing import Any, Dict, Tuple

import numpy as np
from loguru import logger
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import TimeSeriesSplit


# Standard thresholds reported in the operating-point table.
DEFAULT_OPERATING_POINT_THRESHOLDS = (
    0.10, 0.15, 0.20, 0.25, 0.30, 0.35,
    0.40, 0.45, 0.50, 0.55, 0.60, 0.70,
)

# Precision floor used by `select_default_threshold` to pick the published
# decision threshold for each horizon.
DEFAULT_PRECISION_TARGET = 0.60


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


def select_calibrator_cv(
    raw_probs: np.ndarray,
    y_true: np.ndarray,
    n_splits: int = 5,
) -> Tuple[Any, str, Dict[str, Any]]:
    """
    Time-ordered K-fold selection of Platt vs isotonic calibration.

    Each fold trains both calibrators on the inner-train slice and scores
    Brier on the inner-test slice. The method with the lower MEAN held-out
    Brier wins (tie -> isotonic). The chosen method is then refit on the
    full OOF set for production.

    This removes the in-sample optimism bias of `fit_calibrator`, which fit
    and scored on the same data.

    Args:
        raw_probs: Out-of-fold ensemble probabilities in [0, 1]. NaN entries
            are dropped (e.g. samples in the initial walk-forward train window).
        y_true: Binary labels aligned with raw_probs.
        n_splits: Number of TimeSeriesSplit folds. Reduced automatically if
            too few valid samples are available.

    Returns:
        (fitted_calibrator, method_name, comparison) where comparison includes:
          - raw: in-sample Brier of raw_probs vs y
          - platt_in_sample / isotonic_in_sample: legacy in-sample Briers
          - platt_cv_mean / isotonic_cv_mean: mean held-out Brier across folds
          - platt_cv_std  / isotonic_cv_std:  fold-to-fold std of held-out Brier
          - n_cv_folds: actual number of folds used
          - selection: 'cv' (normal path) or 'in_sample_fallback' if CV
            couldn't run (too few samples) or 'identity' (degenerate input).

    Special case: if there are fewer than 10 valid samples or only one class
    is present, returns an identity calibrator with method='identity'.
    """
    raw, y = _filter_nan(raw_probs, y_true)

    if len(raw) < 10 or len(np.unique(y)) < 2:
        logger.warning(
            f"select_calibrator_cv: degenerate input (n={len(raw)}, classes={np.unique(y)}). "
            f"Returning identity calibrator."
        )
        comp: Dict[str, Any] = {
            "raw": float("nan"),
            "platt_in_sample": float("nan"),
            "isotonic_in_sample": float("nan"),
            "platt_cv_mean": float("nan"),
            "isotonic_cv_mean": float("nan"),
            "platt_cv_std": float("nan"),
            "isotonic_cv_std": float("nan"),
            "n_cv_folds": 0,
            "selection": "identity",
        }
        return _identity_calibrator(), "identity", comp

    raw_brier = float(brier_score_loss(y, raw))

    # Cap n_splits so each test fold has at least 2 samples and at least
    # one positive label is achievable across folds.
    max_splits = max(2, min(n_splits, len(raw) // 2))
    actual_splits = min(n_splits, max_splits)

    platt_briers: list[float] = []
    iso_briers: list[float] = []

    if actual_splits >= 2:
        tscv = TimeSeriesSplit(n_splits=actual_splits)
        for train_idx, test_idx in tscv.split(raw):
            r_tr, r_te = raw[train_idx], raw[test_idx]
            y_tr, y_te = y[train_idx], y[test_idx]

            # Need both classes in train AND test to score Brier meaningfully.
            if len(np.unique(y_tr)) < 2 or len(np.unique(y_te)) == 0:
                continue

            try:
                p = _fit_platt(r_tr, y_tr)
                p_pred = _platt_predict(p, r_te)
                platt_briers.append(float(brier_score_loss(y_te, p_pred)))
            except Exception as e:
                logger.debug(f"select_calibrator_cv: platt fold failed: {e}")

            try:
                iso = _fit_isotonic(r_tr, y_tr)
                iso_pred = iso.predict(r_te)
                iso_briers.append(float(brier_score_loss(y_te, iso_pred)))
            except Exception as e:
                logger.debug(f"select_calibrator_cv: isotonic fold failed: {e}")

    # Always compute in-sample Brier for the legacy comparison columns.
    platt_full = _fit_platt(raw, y)
    iso_full = _fit_isotonic(raw, y)
    platt_in = float(brier_score_loss(y, _platt_predict(platt_full, raw)))
    iso_in = float(brier_score_loss(y, iso_full.predict(raw)))

    # Decision: prefer CV scores. If CV produced no usable folds for both
    # methods, fall back to in-sample comparison (with a warning).
    if platt_briers and iso_briers:
        platt_mean = float(np.mean(platt_briers))
        iso_mean = float(np.mean(iso_briers))
        platt_std = float(np.std(platt_briers))
        iso_std = float(np.std(iso_briers))
        selection = "cv"
        if platt_mean < iso_mean:
            method = "platt"
            chosen = platt_full
        else:
            method = "isotonic"
            chosen = iso_full
    else:
        logger.warning(
            "select_calibrator_cv: no usable CV folds, falling back to in-sample selection"
        )
        platt_mean = float("nan")
        iso_mean = float("nan")
        platt_std = float("nan")
        iso_std = float("nan")
        selection = "in_sample_fallback"
        if platt_in < iso_in:
            method = "platt"
            chosen = platt_full
        else:
            method = "isotonic"
            chosen = iso_full

    comparison = {
        "raw": round(raw_brier, 6),
        "platt_in_sample": round(platt_in, 6),
        "isotonic_in_sample": round(iso_in, 6),
        "platt_cv_mean": round(platt_mean, 6) if np.isfinite(platt_mean) else None,
        "isotonic_cv_mean": round(iso_mean, 6) if np.isfinite(iso_mean) else None,
        "platt_cv_std": round(platt_std, 6) if np.isfinite(platt_std) else None,
        "isotonic_cv_std": round(iso_std, 6) if np.isfinite(iso_std) else None,
        "n_cv_folds": min(len(platt_briers), len(iso_briers)),
        "selection": selection,
        # Back-compat aliases so older readers (and the existing UI panel)
        # still find `platt`/`isotonic` keys.
        "platt": round(platt_in, 6),
        "isotonic": round(iso_in, 6),
    }

    return chosen, method, comparison


def compute_operating_points(
    probs: np.ndarray,
    y_true: np.ndarray,
    thresholds: Tuple[float, ...] = DEFAULT_OPERATING_POINT_THRESHOLDS,
) -> list[Dict[str, Any]]:
    """
    Build a precision/recall/F1 table for the given thresholds against `probs`.

    Intended for use against walk-forward OOF probabilities (calibrated or raw)
    so the user can see how the published default threshold was chosen and
    pick their own operating point.

    NaN entries in `probs` are dropped before scoring.

    Returns:
        List of dicts, one per threshold:
          {threshold, precision, recall, f1, n_positive_predictions, support_positives}
        Empty list if not enough valid samples to score.
    """
    p = np.asarray(probs, dtype=float)
    y = np.asarray(y_true)
    mask = ~np.isnan(p)
    p, y = p[mask], y[mask]

    if len(p) == 0 or len(np.unique(y)) < 2:
        return []

    support_pos = int(np.sum(y == 1))
    out: list[Dict[str, Any]] = []
    for t in thresholds:
        pred = (p >= t).astype(int)
        n_pos_pred = int(pred.sum())
        prec = float(precision_score(y, pred, zero_division=0))
        rec = float(recall_score(y, pred, zero_division=0))
        f1 = float(f1_score(y, pred, zero_division=0))
        out.append({
            "threshold": round(float(t), 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "n_positive_predictions": n_pos_pred,
            "support_positives": support_pos,
        })
    return out


def select_default_threshold(
    operating_points: list[Dict[str, Any]],
    precision_target: float = DEFAULT_PRECISION_TARGET,
) -> Dict[str, Any]:
    """
    Pick a single default threshold from an operating-point table.

    Rule:
      1. Among thresholds with precision >= `precision_target` AND recall > 0,
         pick the one with the HIGHEST recall (tie-break: lowest threshold).
      2. If no threshold meets the precision target, fall back to the
         threshold with the highest F1 (tie-break: lowest threshold).
      3. If the table is empty, return a sentinel default of 0.5 with
         `selection='default_fallback'`.

    Returns:
        {threshold, precision, recall, f1, selection}
        where selection ∈ {'precision_target', 'max_f1', 'default_fallback'}.
    """
    if not operating_points:
        return {
            "threshold": 0.5,
            "precision": None,
            "recall": None,
            "f1": None,
            "selection": "default_fallback",
        }

    qualifying = [
        op for op in operating_points
        if op["precision"] >= precision_target and op["recall"] > 0
    ]
    if qualifying:
        # Highest recall; break ties by lower threshold (more recall-friendly).
        qualifying.sort(key=lambda op: (-op["recall"], op["threshold"]))
        chosen = qualifying[0]
        return {
            "threshold": chosen["threshold"],
            "precision": chosen["precision"],
            "recall": chosen["recall"],
            "f1": chosen["f1"],
            "selection": "precision_target",
        }

    # Fall back to max-F1 row.
    by_f1 = sorted(operating_points, key=lambda op: (-op["f1"], op["threshold"]))
    chosen = by_f1[0]
    return {
        "threshold": chosen["threshold"],
        "precision": chosen["precision"],
        "recall": chosen["recall"],
        "f1": chosen["f1"],
        "selection": "max_f1",
    }


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
