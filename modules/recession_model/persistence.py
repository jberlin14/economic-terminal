"""
Recession Model Persistence — save/load helpers.

Pure module-level functions that handle disk I/O for the recession model:
serializing fitted scalers, per-horizon model artifacts, and metadata JSON.
Carved out of `RecessionModel` so the orchestrator in `model.py` focuses on
training/prediction logic, not file paths and joblib calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import joblib
import numpy as np
from loguru import logger

from .features import HORIZONS
from .training import MODEL_TYPES

if TYPE_CHECKING:
    from .model import RecessionModel


MODEL_DIR = Path("data/recession_model")


def save_model(model: "RecessionModel") -> None:
    """Save all model artifacts to disk."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    for horizon in HORIZONS:
        # Save scaler
        joblib.dump(
            model.scalers[horizon],
            MODEL_DIR / f"scaler_{horizon}m.joblib",
        )
        # Save each model type
        for model_type in MODEL_TYPES:
            if model_type in model.models.get(horizon, {}):
                joblib.dump(
                    model.models[horizon][model_type],
                    MODEL_DIR / f"model_{model_type}_{horizon}m.joblib",
                )

    # Save out-of-fold probability arrays as .npy files (too large for JSON)
    oof_summary = {}
    walk_forward_metrics_meta = {}
    if getattr(model, "walk_forward_metrics", None):
        for horizon in HORIZONS:
            wf = model.walk_forward_metrics.get(horizon)
            if wf:
                walk_forward_metrics_meta[str(horizon)] = wf
            arr = model.oof_probs.get(horizon) if model.oof_probs else None
            if arr is not None:
                np.save(MODEL_DIR / f"oof_probs_{horizon}m.npy", arr)
                n_total = int(arr.shape[0])
                n_predicted = int(np.sum(~np.isnan(arr)))
                oof_summary[str(horizon)] = {
                    "n_predicted": n_predicted,
                    "n_total": n_total,
                }

    meta = {
        "feature_names": model.feature_names,
        "metrics": {
            str(h): {mt: m for mt, m in mts.items()}
            for h, mts in model.metrics.items()
        },
        "confusion_matrices": {
            str(h): {mt: cm for mt, cm in cms.items()}
            for h, cms in model.confusion_matrices.items()
        },
        "best_model": {str(k): v for k, v in model.best_model.items()},
        "decision_tree_rules": {
            str(k): v for k, v in model.decision_tree_rules.items()
        },
        "optimal_thresholds": {
            str(h): {mt: t for mt, t in thresholds.items()}
            for h, thresholds in model.optimal_thresholds.items()
        },
        "ensemble_weights": {
            str(h): {mt: w for mt, w in weights.items()}
            for h, weights in model.ensemble_weights.items()
        },
        "training_metadata": model.training_metadata,
        "model_types": list(MODEL_TYPES.keys()),
        "walk_forward_metrics": walk_forward_metrics_meta,
        "oof_summary": oof_summary,
    }
    with open(MODEL_DIR / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

    logger.success(f"Multi-model ensemble saved to {MODEL_DIR}")


def load_model(model: "RecessionModel") -> bool:
    """Load model artifacts from disk into the given model instance."""
    meta_path = MODEL_DIR / "metadata.json"
    if not meta_path.exists():
        logger.debug("No saved recession model found")
        return False

    try:
        with open(meta_path) as f:
            meta = json.load(f)

        model.feature_names = meta["feature_names"]
        model.training_metadata = meta.get("training_metadata", {})

        # Load metrics
        stored_metrics = meta.get("metrics", {})
        model.metrics = {}
        for h_str, model_metrics in stored_metrics.items():
            h = int(h_str)
            model.metrics[h] = model_metrics

        # Load confusion matrices
        stored_cms = meta.get("confusion_matrices", {})
        model.confusion_matrices = {}
        for h_str, cms in stored_cms.items():
            model.confusion_matrices[int(h_str)] = cms

        model.best_model = {
            int(k): v for k, v in meta.get("best_model", {}).items()
        }
        model.decision_tree_rules = {
            int(k): v for k, v in meta.get("decision_tree_rules", {}).items()
        }
        model.optimal_thresholds = {
            int(k): v for k, v in meta.get("optimal_thresholds", {}).items()
        }
        model.ensemble_weights = {
            int(k): v for k, v in meta.get("ensemble_weights", {}).items()
        }

        # Walk-forward metrics + OOF probs (added in Phase 2A Task A1).
        # Backwards-compat: missing keys/files are tolerated.
        stored_wf = meta.get("walk_forward_metrics", {}) or {}
        model.walk_forward_metrics = {
            int(k): v for k, v in stored_wf.items()
        }
        model.oof_probs = {}
        for horizon in HORIZONS:
            oof_path = MODEL_DIR / f"oof_probs_{horizon}m.npy"
            if oof_path.exists():
                try:
                    model.oof_probs[horizon] = np.load(oof_path)
                except Exception as e:
                    logger.warning(f"Failed to load oof_probs for {horizon}m: {e}")
                    model.oof_probs[horizon] = None
            else:
                model.oof_probs[horizon] = None

        # Determine which model types to load
        model_types = meta.get("model_types", list(MODEL_TYPES.keys()))

        # Load models and scalers
        model.models = {}
        model.scalers = {}

        for horizon in HORIZONS:
            scaler_path = MODEL_DIR / f"scaler_{horizon}m.joblib"
            if not scaler_path.exists():
                # Backwards compat: try old single-model format
                return _load_legacy(model)
            model.scalers[horizon] = joblib.load(scaler_path)

            model.models[horizon] = {}
            for model_type in model_types:
                model_path = MODEL_DIR / f"model_{model_type}_{horizon}m.joblib"
                if model_path.exists():
                    model.models[horizon][model_type] = joblib.load(model_path)

            if not model.models[horizon]:
                logger.warning(f"No models loaded for {horizon}m horizon")
                return False

        model._loaded = True
        logger.info(f"Multi-model recession ensemble loaded ({len(model_types)} model types)")
        return True

    except Exception as e:
        logger.error(f"Failed to load recession model: {e}")
        return False


def _load_legacy(model: "RecessionModel") -> bool:
    """Load old single-model format for backwards compatibility."""
    try:
        meta_path = MODEL_DIR / "metadata.json"
        with open(meta_path) as f:
            meta = json.load(f)

        model.feature_names = meta["feature_names"]
        model.training_metadata = meta.get("training_metadata", {})

        # Old format had metrics keyed by horizon directly
        old_metrics = meta.get("metrics", {})
        model.metrics = {}
        for h_str, m in old_metrics.items():
            h = int(h_str)
            # Wrap in logistic key
            model.metrics[h] = {"logistic": m}

        model.models = {}
        model.scalers = {}

        for horizon in HORIZONS:
            # Old format: model_{horizon}m.joblib, scaler_{horizon}m.joblib
            model_path = MODEL_DIR / f"model_{horizon}m.joblib"
            scaler_path = MODEL_DIR / f"scaler_{horizon}m.joblib"
            if not model_path.exists() or not scaler_path.exists():
                return False

            model.scalers[horizon] = joblib.load(scaler_path)
            model.models[horizon] = {"logistic": joblib.load(model_path)}

        model.best_model = {h: "logistic" for h in HORIZONS}
        model.walk_forward_metrics = {}
        model.oof_probs = {h: None for h in HORIZONS}
        model._loaded = True
        logger.info("Loaded legacy single-model recession model")
        return True

    except Exception as e:
        logger.error(f"Failed to load legacy model: {e}")
        return False
