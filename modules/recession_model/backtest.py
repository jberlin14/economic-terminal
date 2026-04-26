"""
Recession Model Walk-Forward Backtest Harness.

Produces genuine out-of-sample probability estimates by training and
evaluating across multiple time-ordered folds. Each fold:
  1. Carves a 20% inner-validation slice off the END of the train window.
  2. Refits StandardScaler on the inner training portion ONLY.
  3. Fits each MODEL_TYPES member, weights by inner-val AUC,
     produces a weighted-ensemble probability for the outer test window.
  4. Records fold-level f1 / auc / brier metrics.

The aggregated out-of-fold (OOF) probability array is the foundation for
downstream calibration (Phase 2A Task A2) — it must contain genuinely
out-of-sample predictions, never in-sample leakage.
"""

from typing import Any, Dict, Iterator, List, Tuple

import numpy as np
from loguru import logger
from sklearn.metrics import brier_score_loss, f1_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

from .training import MODEL_TYPES, create_model, find_optimal_threshold


# ──────────────────────────────────────────────
# Default fold geometry
# ──────────────────────────────────────────────

INITIAL_TRAIN_SIZE_RATIO = 0.5
STEP_MONTHS = 12
TEST_SIZE_MONTHS = 12
INNER_VAL_RATIO = 0.2


def walk_forward_folds(
    n_samples: int,
    initial_train_size: int,
    step: int,
    test_size: int,
) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
    """
    Yield (train_idx, test_idx) tuples in time order with no overlap.

    Expanding window: each fold's training set grows by `step` rows compared
    to the previous fold; the test window of length `test_size` sits
    immediately after the train window.
    """
    if initial_train_size <= 0 or test_size <= 0 or step <= 0:
        raise ValueError("initial_train_size, step, and test_size must be positive")
    if initial_train_size >= n_samples:
        return

    train_end = initial_train_size
    while train_end + test_size <= n_samples:
        train_idx = np.arange(0, train_end)
        # Final fold absorbs the remaining tail so every post-train sample
        # appears in some test window. Without this the last (n_samples -
        # initial_train_size) % step samples would never get an OOF prediction.
        next_train_end = train_end + step
        if next_train_end + test_size > n_samples:
            test_end = n_samples
        else:
            test_end = train_end + test_size
        test_idx = np.arange(train_end, test_end)
        yield train_idx, test_idx
        train_end = next_train_end


def _fold_auc_weights(
    aucs: Dict[str, float],
) -> Dict[str, float]:
    """AUC-weighted ensemble weights, falling back to equal weights when
    all AUCs are at or below 0.5 (matches model.py train() pattern)."""
    raw = {mt: max(aucs.get(mt, 0.5) - 0.5, 0.01) for mt in MODEL_TYPES}
    total = sum(raw.values())
    if total <= 0:
        # Should never happen given the 0.01 floor, but guard anyway.
        return {mt: 1.0 / len(MODEL_TYPES) for mt in MODEL_TYPES}
    return {mt: raw[mt] / total for mt in MODEL_TYPES}


def _equal_weights() -> Dict[str, float]:
    n = len(MODEL_TYPES)
    return {mt: 1.0 / n for mt in MODEL_TYPES}


def _model_probs(model: Any, X: np.ndarray) -> np.ndarray:
    """Mirror the probability-extraction logic used in training.train_single_model."""
    if hasattr(model, "predict_proba"):
        return model.predict_proba(X)[:, 1]
    if hasattr(model, "decision_function"):
        decisions = model.decision_function(X)
        return 1.0 / (1.0 + np.exp(-decisions))
    return model.predict(X).astype(float)


def run_walk_forward(
    X: np.ndarray,
    y: np.ndarray,
    horizon: int,
    feature_names: List[str],
) -> Dict[str, Any]:
    """
    Run an expanding-window walk-forward backtest for a single horizon.

    For each fold:
      - Inner validation is a 20% slice carved off the END of the train window.
      - Scaler is fit on inner train only (no leakage into inner val or outer test).
      - Each MODEL_TYPES member is fit on inner train, scored on inner val.
      - Inner-val AUCs determine the per-model ensemble weights.
      - The optimal threshold is chosen on weighted ensemble probs over the
        inner val slice, then applied to the outer test slice.
    """
    n_samples = len(X)
    initial_train_size = int(n_samples * INITIAL_TRAIN_SIZE_RATIO)

    oof_probs = np.full(n_samples, np.nan)
    oof_predictions = np.full(n_samples, np.nan)
    fold_metrics: List[Dict[str, Any]] = []

    folds = list(walk_forward_folds(
        n_samples=n_samples,
        initial_train_size=initial_train_size,
        step=STEP_MONTHS,
        test_size=TEST_SIZE_MONTHS,
    ))

    if not folds:
        logger.warning(
            f"No walk-forward folds for horizon={horizon}m "
            f"(n_samples={n_samples}, initial_train={initial_train_size})"
        )

    for fold_idx, (train_idx, test_idx) in enumerate(folds):
        X_train_full = X[train_idx]
        y_train_full = y[train_idx]
        X_test = X[test_idx]
        y_test = y[test_idx]

        # Inner-val split: last 20% of the training window
        inner_val_size = max(1, int(len(train_idx) * INNER_VAL_RATIO))
        inner_train_size = len(train_idx) - inner_val_size
        if inner_train_size <= 0:
            logger.warning(
                f"Fold {fold_idx} (horizon={horizon}m): training window too small "
                f"for inner-val split, skipping"
            )
            continue

        X_inner_train_raw = X_train_full[:inner_train_size]
        y_inner_train = y_train_full[:inner_train_size]
        X_inner_val_raw = X_train_full[inner_train_size:]
        y_inner_val = y_train_full[inner_train_size:]

        if len(np.unique(y_inner_train)) < 2:
            logger.warning(
                f"Fold {fold_idx} (horizon={horizon}m): inner train has only one class, skipping"
            )
            continue

        scaler = StandardScaler()
        X_inner_train = scaler.fit_transform(X_inner_train_raw)
        X_inner_val = scaler.transform(X_inner_val_raw)
        X_test_scaled = scaler.transform(X_test)

        per_model_inner_val_probs: Dict[str, np.ndarray] = {}
        per_model_test_probs: Dict[str, np.ndarray] = {}
        per_model_inner_aucs: Dict[str, float] = {}

        inner_val_has_two_classes = len(np.unique(y_inner_val)) > 1

        for model_type in MODEL_TYPES:
            try:
                model = create_model(model_type)
                model.fit(X_inner_train, y_inner_train)
                inner_val_probs = _model_probs(model, X_inner_val)
                test_probs = _model_probs(model, X_test_scaled)
                per_model_inner_val_probs[model_type] = inner_val_probs
                per_model_test_probs[model_type] = test_probs

                if inner_val_has_two_classes:
                    per_model_inner_aucs[model_type] = float(
                        roc_auc_score(y_inner_val, inner_val_probs)
                    )
                else:
                    per_model_inner_aucs[model_type] = 0.5
            except Exception as e:
                logger.warning(
                    f"Fold {fold_idx} (horizon={horizon}m) {model_type} fit failed: {e}"
                )

        if not per_model_test_probs:
            logger.warning(
                f"Fold {fold_idx} (horizon={horizon}m): no models trained, skipping"
            )
            continue

        if inner_val_has_two_classes:
            weights = _fold_auc_weights(per_model_inner_aucs)
        else:
            logger.warning(
                f"Fold {fold_idx} (horizon={horizon}m): inner val has one class, "
                f"using equal weights"
            )
            weights = _equal_weights()

        # Re-normalize weights across only the models we actually have
        active_total = sum(weights[mt] for mt in per_model_test_probs)
        if active_total <= 0:
            active_weights = {
                mt: 1.0 / len(per_model_test_probs) for mt in per_model_test_probs
            }
        else:
            active_weights = {
                mt: weights[mt] / active_total for mt in per_model_test_probs
            }

        # Weighted ensemble probabilities
        weighted_inner_val = np.zeros_like(y_inner_val, dtype=float)
        weighted_test = np.zeros_like(y_test, dtype=float)
        for mt, w in active_weights.items():
            weighted_inner_val += w * per_model_inner_val_probs[mt]
            weighted_test += w * per_model_test_probs[mt]

        # Per-fold optimal threshold from inner val (fallback to 0.5 if degenerate)
        if inner_val_has_two_classes:
            threshold = find_optimal_threshold(y_inner_val, weighted_inner_val)
        else:
            threshold = 0.5

        test_predictions = (weighted_test >= threshold).astype(int)

        # Record fold metrics
        if len(np.unique(y_test)) > 1:
            fold_auc = float(roc_auc_score(y_test, weighted_test))
        else:
            fold_auc = float("nan")
        fold_f1 = float(f1_score(y_test, test_predictions, zero_division=0))
        fold_brier = float(brier_score_loss(y_test, weighted_test))

        fold_metrics.append({
            "fold": fold_idx,
            "train_start": int(train_idx[0]),
            "train_end": int(train_idx[-1]),
            "test_start": int(test_idx[0]),
            "test_end": int(test_idx[-1]),
            "n_train": int(len(train_idx)),
            "n_test": int(len(test_idx)),
            "n_inner_train": int(inner_train_size),
            "n_inner_val": int(inner_val_size),
            "threshold": round(float(threshold), 4),
            "weights": {mt: round(float(w), 4) for mt, w in active_weights.items()},
            "f1": round(fold_f1, 4),
            "auc_roc": round(fold_auc, 4) if np.isfinite(fold_auc) else None,
            "brier": round(fold_brier, 4),
        })

        oof_probs[test_idx] = weighted_test
        oof_predictions[test_idx] = test_predictions

    # Aggregate
    f1_vals = np.array([fm["f1"] for fm in fold_metrics], dtype=float)
    auc_vals = np.array(
        [fm["auc_roc"] for fm in fold_metrics if fm["auc_roc"] is not None],
        dtype=float,
    )
    brier_vals = np.array([fm["brier"] for fm in fold_metrics], dtype=float)

    def _safe_mean(arr: np.ndarray) -> float:
        return float(np.mean(arr)) if arr.size else float("nan")

    def _safe_std(arr: np.ndarray) -> float:
        return float(np.std(arr)) if arr.size else float("nan")

    aggregate_metrics = {
        "f1_mean": round(_safe_mean(f1_vals), 4),
        "f1_std": round(_safe_std(f1_vals), 4),
        "auc_mean": round(_safe_mean(auc_vals), 4),
        "auc_std": round(_safe_std(auc_vals), 4),
        "brier_mean": round(_safe_mean(brier_vals), 4),
        "brier_std": round(_safe_std(brier_vals), 4),
    }

    return {
        "oof_probs": oof_probs,
        "oof_predictions": oof_predictions,
        "fold_metrics": fold_metrics,
        "aggregate_metrics": aggregate_metrics,
    }
