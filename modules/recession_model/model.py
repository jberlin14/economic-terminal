"""
Recession Probability Model — Multi-Model Ensemble

Trains 4 model types on ~60 years of FRED data, each across 3 horizons (3/6/12 months):
  - Logistic Regression (balanced class weights)
  - K-Nearest Neighbors (distance-weighted)
  - Random Forest (balanced class weights, decision tree ensemble)
  - Gradient Boosting (handles imbalanced data well, replaces Ridge)

Produces AUC-weighted ensemble probabilities and per-model comparison metrics.
Includes per-model optimal threshold tuning for recession detection.
"""

import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

import numpy as np
import pandas as pd
from loguru import logger

from sklearn.preprocessing import StandardScaler

from .backtest import run_walk_forward
from .calibration import (
    apply_calibrator,
    compute_operating_points,
    select_calibrator_cv,
    select_default_threshold,
)
from .data_builder import RecessionDataBuilder
from .drift import compute_training_quantiles
from .features import HORIZONS
from .persistence import save_model, load_model
from .training import (
    HORIZONS_LABELS,
    MODEL_TYPES,
    create_model,
    train_single_model,
    find_optimal_threshold,
    extract_tree_rules,
    _balanced_sample_weights,
    _undersample_majority,
)


class RecessionModel:
    """
    Multi-model, multi-horizon recession probability model.

    Trains 4 model types x 3 horizons = 12 models total.
    Ensemble prediction averages across model types.
    """

    def __init__(self):
        # models[horizon][model_type] = fitted model
        self.models: Dict[int, Dict[str, Any]] = {}
        # scalers[horizon] = fitted StandardScaler (shared across model types)
        self.scalers: Dict[int, StandardScaler] = {}
        self.feature_names: List[str] = []
        # metrics[horizon][model_type] = dict of metrics
        self.metrics: Dict[int, Dict[str, Dict[str, Any]]] = {}
        # confusion_matrices[horizon][model_type] = [[TN,FP],[FN,TP]]
        self.confusion_matrices: Dict[int, Dict[str, List]] = {}
        # best_model[horizon] = model_type with highest f1
        self.best_model: Dict[int, str] = {}
        # decision tree rules for explainability
        self.decision_tree_rules: Dict[int, List[Dict]] = {}
        # optimal thresholds[horizon][model_type] = float (threshold that maximizes F1)
        self.optimal_thresholds: Dict[int, Dict[str, float]] = {}
        # ensemble_weights[horizon][model_type] = float (AUC-based weight, sums to 1)
        self.ensemble_weights: Dict[int, Dict[str, float]] = {}
        # walk-forward backtest results: walk_forward_metrics[horizon] = {
        #   "aggregate_metrics": {...}, "fold_metrics": [...], "n_folds": int
        # }
        self.walk_forward_metrics: Dict[int, Dict[str, Any]] = {}
        # oof_probs[horizon] = np.ndarray of length n_samples (NaN where untested),
        # or None if not populated (e.g. legacy load)
        self.oof_probs: Dict[int, Optional[np.ndarray]] = {}
        # calibrators[horizon] = fitted Platt/Isotonic calibrator (or None for
        # legacy loads / un-trained horizons). Calibrators are fit on the
        # walk-forward OOF probabilities and applied at predict time so the
        # published `calibrated_ensemble` is an honest probability.
        self.calibrators: Dict[int, Any] = {}
        self.calibration_method: Dict[int, str] = {}
        self.calibration_brier: Dict[int, Dict[str, float]] = {}
        # operating_points[horizon] = list[{threshold, precision, recall, f1, ...}]
        # computed against the calibrated walk-forward OOF probs (Phase 1 §1.3).
        self.operating_points: Dict[int, List[Dict[str, Any]]] = {}
        # default_threshold[horizon] = {threshold, precision, recall, f1, selection}
        # the published decision threshold per horizon (precision-target rule).
        self.default_threshold: Dict[int, Dict[str, Any]] = {}
        # Per-feature training-window quantiles for live drift scoring
        # (Phase 2 §2.5). Populated at train() time, surfaced via
        # `predictor.get_current_probability` as a soft warning chip.
        self.training_quantiles: Dict[str, Dict[str, float]] = {}
        self.training_metadata: Dict[str, Any] = {}
        self._loaded = False

    @property
    def is_trained(self) -> bool:
        return self._loaded and len(self.models) == len(HORIZONS)

    def train(self, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Train all models from scratch using FRED data."""
        logger.info("Starting multi-model recession training...")

        builder = RecessionDataBuilder(api_key=api_key)
        df, data_meta = builder.build_dataset()

        self.feature_names = data_meta["feature_names"]
        X = df[self.feature_names].values

        # Use 60/40 train/test split (time-ordered, no shuffle)
        split_idx = int(len(X) * 0.6)

        results = {}

        for horizon in HORIZONS:
            target_col = f"recession_{horizon}m"
            y = df[target_col].values.astype(int)

            logger.info(
                f"Training {horizon}-month models: {len(y)} samples, "
                f"{y.sum()} positive ({y.mean()*100:.1f}%)"
            )

            # Fit scaler on full training set
            X_train_raw, X_test_raw = X[:split_idx], X[split_idx:]
            y_train, y_test = y[:split_idx], y[split_idx:]

            scaler = StandardScaler()
            X_train = scaler.fit_transform(X_train_raw)
            X_test = scaler.transform(X_test_raw)

            self.scalers[horizon] = scaler
            self.models[horizon] = {}
            self.metrics[horizon] = {}
            self.confusion_matrices[horizon] = {}
            self.optimal_thresholds[horizon] = {}

            horizon_results = {}
            best_f1 = -1
            best_type = "logistic"

            for model_type, model_name in MODEL_TYPES.items():
                logger.info(f"  Training {model_name} for {horizon}m...")

                try:
                    model_metrics, fitted_model, threshold = train_single_model(
                        model_type, X_train, y_train, X_test, y_test,
                        self.feature_names,
                    )

                    self.models[horizon][model_type] = fitted_model
                    self.metrics[horizon][model_type] = model_metrics
                    self.optimal_thresholds[horizon][model_type] = threshold
                    # Reconstruct raw confusion matrix [[TN,FP],[FN,TP]] from metrics
                    cm_named = model_metrics["confusion_matrix"]
                    self.confusion_matrices[horizon][model_type] = [
                        [cm_named["true_negatives"], cm_named["false_positives"]],
                        [cm_named["false_negatives"], cm_named["true_positives"]],
                    ]
                    horizon_results[model_type] = model_metrics

                    if model_metrics.get("f1", 0) > best_f1:
                        best_f1 = model_metrics["f1"]
                        best_type = model_type

                    logger.success(
                        f"  {model_name} {horizon}m: "
                        f"F1={model_metrics['f1']:.3f}, "
                        f"AUC={model_metrics.get('auc_roc', 0):.3f}, "
                        f"Threshold={model_metrics.get('optimal_threshold', 0.5):.2f}"
                    )

                except Exception as e:
                    logger.error(f"  Failed to train {model_name} for {horizon}m: {e}")
                    horizon_results[model_type] = {"error": str(e)}

            self.best_model[horizon] = best_type

            # Compute AUC-weighted ensemble weights
            auc_scores = {}
            for model_type in MODEL_TYPES:
                auc = self.metrics[horizon].get(model_type, {}).get("auc_roc", 0.5)
                # Only give weight to models that beat random (AUC > 0.5)
                auc_scores[model_type] = max(auc - 0.5, 0.01)
            total_auc = sum(auc_scores.values())
            self.ensemble_weights[horizon] = {
                mt: round(score / total_auc, 4) for mt, score in auc_scores.items()
            }
            logger.info(f"  Ensemble weights for {horizon}m: {self.ensemble_weights[horizon]}")

            # Extract decision tree rules from random forest
            if "random_forest" in self.models[horizon]:
                self.decision_tree_rules[horizon] = extract_tree_rules(
                    self.models[horizon]["random_forest"], self.feature_names
                )

            # Now refit all models on FULL data for production predictions
            scaler_full = StandardScaler()
            X_full = scaler_full.fit_transform(X)
            self.scalers[horizon] = scaler_full

            for model_type in MODEL_TYPES:
                if model_type in self.models[horizon]:
                    try:
                        full_model = create_model(model_type)
                        # Mirror the per-model imbalance handling used during
                        # the held-out fit (Phase 2 §2.1): KNN gets majority
                        # under-sampling; GB gets balanced sample weights;
                        # logistic + RF rely on class_weight='balanced'.
                        if model_type == "knn":
                            X_fit, y_fit = _undersample_majority(X_full, y)
                            full_model.fit(X_fit, y_fit)
                        elif model_type == "gradient_boosting":
                            full_model.fit(X_full, y, sample_weight=_balanced_sample_weights(y))
                        else:
                            full_model.fit(X_full, y)
                        self.models[horizon][model_type] = full_model
                    except Exception as e:
                        logger.warning(f"Failed to refit {model_type} on full data: {e}")

            # Re-extract tree rules from full-data random forest
            if "random_forest" in self.models[horizon]:
                rf = self.models[horizon]["random_forest"]
                if hasattr(rf, 'estimators_'):
                    self.decision_tree_rules[horizon] = extract_tree_rules(
                        rf, self.feature_names
                    )

            results[f"{horizon}m"] = horizon_results

        # Walk-forward backtest — produces genuine out-of-sample probabilities
        # per horizon. Feeds the calibration step (Phase 2A Task A2) downstream.
        logger.info("Running walk-forward backtest across horizons...")
        for horizon in HORIZONS:
            target_col = f"recession_{horizon}m"
            y_h = df[target_col].values.astype(int)
            wf = run_walk_forward(X, y_h, horizon, self.feature_names)
            self.walk_forward_metrics[horizon] = {
                "aggregate_metrics": wf["aggregate_metrics"],
                "fold_metrics": wf["fold_metrics"],
                "n_folds": len(wf["fold_metrics"]),
            }
            self.oof_probs[horizon] = wf["oof_probs"]
            agg = wf["aggregate_metrics"]
            logger.success(
                f"  Walk-forward {horizon}m: F1={agg['f1_mean']:.3f}±{agg['f1_std']:.3f}, "
                f"AUC={agg['auc_mean']:.3f}±{agg['auc_std']:.3f}, "
                f"Brier={agg['brier_mean']:.3f}±{agg['brier_std']:.3f} "
                f"({len(wf['fold_metrics'])} folds)"
            )

        # Fit per-horizon calibrators on the OOF probs from the walk-forward
        # backtest. Uses time-ordered CV to pick Platt vs isotonic by mean
        # held-out Brier — removes the in-sample optimism bias of fitting
        # and scoring on the same OOF set (Phase 1 §1.1).
        logger.info("Fitting per-horizon ensemble calibrators (Platt vs isotonic by held-out CV Brier)...")
        for horizon in HORIZONS:
            oof = self.oof_probs.get(horizon)
            if oof is None:
                logger.warning(f"  No OOF probs for {horizon}m — skipping calibrator fit")
                self.calibrators[horizon] = None
                continue
            target_col = f"recession_{horizon}m"
            y_h = df[target_col].values.astype(int)
            calibrator, method, brier_comparison = select_calibrator_cv(oof, y_h)
            self.calibrators[horizon] = calibrator
            self.calibration_method[horizon] = method
            self.calibration_brier[horizon] = brier_comparison
            cv_winner = brier_comparison.get(f"{method}_cv_mean")
            logger.success(
                f"  Calibrator {horizon}m: method={method} via {brier_comparison.get('selection')}, "
                f"brier raw={brier_comparison['raw']}, "
                f"in-sample={brier_comparison.get(f'{method}_in_sample', 'n/a')}, "
                f"cv-mean={cv_winner if cv_winner is not None else 'n/a'} "
                f"({brier_comparison.get('n_cv_folds', 0)} folds)"
            )

        # Compute ensemble operating points + default threshold against the
        # CALIBRATED walk-forward OOF probabilities (Phase 1 §1.3). The
        # default threshold replaces hard-coded 25/50% banding in predictor.
        logger.info("Computing ensemble operating points + default thresholds per horizon...")
        for horizon in HORIZONS:
            oof = self.oof_probs.get(horizon)
            if oof is None:
                self.operating_points[horizon] = []
                self.default_threshold[horizon] = {
                    "threshold": 0.5, "precision": None, "recall": None,
                    "f1": None, "selection": "default_fallback",
                }
                continue
            target_col = f"recession_{horizon}m"
            y_h = df[target_col].values.astype(int)

            calibrator = self.calibrators.get(horizon)
            if calibrator is not None:
                # Apply the calibrator only to non-NaN entries; keep NaN
                # in the same positions so compute_operating_points filters.
                calibrated_oof = np.full_like(oof, np.nan, dtype=float)
                mask = ~np.isnan(oof)
                if mask.any():
                    calibrated_oof[mask] = apply_calibrator(calibrator, oof[mask])
            else:
                calibrated_oof = oof

            ops = compute_operating_points(calibrated_oof, y_h)
            self.operating_points[horizon] = ops
            self.default_threshold[horizon] = select_default_threshold(ops)
            sel = self.default_threshold[horizon]
            logger.success(
                f"  Operating points {horizon}m: default threshold={sel['threshold']} "
                f"(P={sel['precision']}, R={sel['recall']}, F1={sel['f1']}, "
                f"selection={sel['selection']}, {len(ops)} operating points)"
            )

        # Persist per-feature training quantiles for live drift scoring
        # (Phase 2 §2.5). Computed once here so predictor.get_current_probability
        # can compare the live snapshot against this baseline cheaply.
        try:
            self.training_quantiles = compute_training_quantiles(df, self.feature_names)
            logger.info(f"Computed training quantiles for {len(self.training_quantiles)} features")
        except Exception as e:
            logger.warning(f"Failed to compute training quantiles: {e}")
            self.training_quantiles = {}

        self.training_metadata = {
            "trained_at": datetime.utcnow().isoformat(),
            "data_start": data_meta["start_date"],
            "data_end": data_meta["end_date"],
            "n_samples": data_meta["n_samples"],
            "n_features": data_meta["n_features"],
            "feature_names": self.feature_names,
            "recession_rates": data_meta["recession_rate"],
            "train_size": split_idx,
            "test_size": len(X) - split_idx,
            "model_types": list(MODEL_TYPES.keys()),
            "best_models": {str(k): v for k, v in self.best_model.items()},
            "walk_forward": {
                f"{h}m": self.walk_forward_metrics[h]["aggregate_metrics"]
                for h in HORIZONS
                if h in self.walk_forward_metrics
            },
        }

        self._loaded = True
        self.save()

        return {
            "status": "trained",
            "metadata": self.training_metadata,
            "metrics": results,
        }

    def predict(self, features: Dict[str, float]) -> Dict[str, Any]:
        """
        Generate recession probabilities from current feature values.
        Returns ensemble and per-model probabilities.
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() or load() first.")

        X = np.array([[features.get(f, 0.0) for f in self.feature_names]])

        model_probs: Dict[str, Dict[str, float]] = {}
        raw_ensemble: Dict[str, float] = {}
        calibrated_ensemble: Dict[str, float] = {}

        for horizon in HORIZONS:
            X_scaled = self.scalers[horizon].transform(X)
            horizon_probs = []
            horizon_weights = []
            weights = self.ensemble_weights.get(horizon, {})

            for model_type in MODEL_TYPES:
                if model_type not in self.models.get(horizon, {}):
                    continue

                model = self.models[horizon][model_type]

                try:
                    if hasattr(model, "predict_proba"):
                        prob = model.predict_proba(X_scaled)[0, 1]
                    elif hasattr(model, "decision_function"):
                        decision = model.decision_function(X_scaled)[0]
                        prob = 1 / (1 + np.exp(-decision))
                    else:
                        prob = float(model.predict(X_scaled)[0])

                    prob_pct = round(float(prob * 100), 1)

                    if model_type not in model_probs:
                        model_probs[model_type] = {}
                    model_probs[model_type][f"{horizon}m"] = prob_pct
                    horizon_probs.append(prob_pct)
                    horizon_weights.append(weights.get(model_type, 0.25))

                except Exception as e:
                    logger.warning(f"Prediction failed for {model_type}/{horizon}m: {e}")

            if horizon_probs and horizon_weights:
                w = np.array(horizon_weights)
                w = w / w.sum()  # re-normalize in case a model was skipped
                # horizon_probs are already in percent (0-100). Convert to
                # [0,1] for the calibrator and back to percent for output.
                raw_avg_pct = float(np.average(horizon_probs, weights=w))
                raw_avg = raw_avg_pct / 100.0
                calibrator = self.calibrators.get(horizon)
                if calibrator is not None:
                    calibrated = float(apply_calibrator(calibrator, np.array([raw_avg]))[0])
                else:
                    calibrated = raw_avg
                raw_ensemble[f"{horizon}m"] = round(raw_avg_pct, 1)
                calibrated_ensemble[f"{horizon}m"] = round(calibrated * 100, 1)
            else:
                raw_ensemble[f"{horizon}m"] = 0.0
                calibrated_ensemble[f"{horizon}m"] = 0.0

        # Phase 2 §2.4: probability uncertainty bands.
        # We use the spread of per-model probabilities at predict time as a
        # cheap, honest proxy for ensemble uncertainty. This isn't a true
        # bootstrap CI (would require keeping fold-models or running a
        # bootstrap at fit time), but it's a reasonable signal: when the
        # 4 model heads disagree, the band is wide; when they agree, narrow.
        uncertainty_bands: Dict[str, Dict[str, float]] = {}
        for horizon in HORIZONS:
            per_model_for_horizon = [
                model_probs[mt][f"{horizon}m"]
                for mt in MODEL_TYPES
                if mt in model_probs and f"{horizon}m" in model_probs[mt]
            ]
            if len(per_model_for_horizon) >= 2:
                arr = np.array(per_model_for_horizon, dtype=float)
                uncertainty_bands[f"{horizon}m"] = {
                    "p25": round(float(np.percentile(arr, 25)), 1),
                    "p50": round(float(np.percentile(arr, 50)), 1),
                    "p75": round(float(np.percentile(arr, 75)), 1),
                    "min": round(float(arr.min()), 1),
                    "max": round(float(arr.max()), 1),
                    "iqr": round(float(np.percentile(arr, 75) - np.percentile(arr, 25)), 1),
                    "n_models": len(per_model_for_horizon),
                }
            else:
                uncertainty_bands[f"{horizon}m"] = {}

        return {
            # `ensemble` aliases the calibrated value — callers that read
            # `result["ensemble"][<horizon>]` get the canonical probability.
            "ensemble": calibrated_ensemble,
            "raw_ensemble": raw_ensemble,
            "calibrated_ensemble": calibrated_ensemble,
            "models": model_probs,
            "uncertainty": uncertainty_bands,
        }

    def explain_prediction(
        self,
        features: Dict[str, float],
        top_k: int = 10,
    ) -> Dict[str, Any]:
        """
        Phase 4.1: Per-prediction explanation using L1 logistic coefficients.

        For each horizon, computes per-feature contribution to the logit:
            contribution_i = coef_i * scaled_value_i
        Then ranks by absolute contribution and returns the top-K positive
        (pushing recession probability UP) and top-K negative (pulling it
        DOWN). Logistic is the cleanest base for this because L1 already
        zeroed irrelevant features at training time (Phase 2.2).

        Returns:
          {
            "<horizon>m": {
              "model_used": "logistic",
              "logit": float,
              "intercept": float,
              "top_pushing_up":   [{feature, value, scaled_value, coefficient, contribution}, ...],
              "top_pulling_down": [{feature, value, scaled_value, coefficient, contribution}, ...],
            }
          }
        Returns empty dict if the model isn't trained or logistic isn't
        present (e.g. legacy single-model artifact).
        """
        if not self.is_trained:
            return {}

        out: Dict[str, Any] = {}
        x_raw = np.array([[features.get(f, 0.0) for f in self.feature_names]])

        for horizon in HORIZONS:
            scaler = self.scalers.get(horizon)
            logistic = (self.models.get(horizon) or {}).get("logistic")
            if scaler is None or logistic is None or not hasattr(logistic, "coef_"):
                continue

            x_scaled = scaler.transform(x_raw)[0]
            coefs = logistic.coef_[0] if logistic.coef_.ndim > 1 else logistic.coef_
            intercept = float(logistic.intercept_[0]) if hasattr(logistic, "intercept_") else 0.0

            contributions = coefs * x_scaled
            # Build the feature list with everything we need for the UI.
            entries = []
            for i, name in enumerate(self.feature_names):
                if abs(coefs[i]) < 1e-12:
                    continue  # L1-zeroed feature; not meaningful to display
                entries.append({
                    "feature": name,
                    "value": round(float(features.get(name, 0.0)), 4),
                    "scaled_value": round(float(x_scaled[i]), 3),
                    "coefficient": round(float(coefs[i]), 4),
                    "contribution": round(float(contributions[i]), 4),
                })

            entries_pos = [e for e in entries if e["contribution"] > 0]
            entries_neg = [e for e in entries if e["contribution"] < 0]
            entries_pos.sort(key=lambda e: -e["contribution"])
            entries_neg.sort(key=lambda e: e["contribution"])

            out[f"{horizon}m"] = {
                "model_used": "logistic",
                "logit": round(float(np.sum(contributions) + intercept), 4),
                "intercept": round(intercept, 4),
                "top_pushing_up": entries_pos[:top_k],
                "top_pulling_down": entries_neg[:top_k],
                "n_active_features": len(entries),
            }
        return out

    def predict_history(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate historical ensemble probability series for charting.
        """
        if not self.is_trained:
            raise ValueError("Model not trained.")

        X = df[self.feature_names].values
        result = pd.DataFrame(index=df.index)

        for horizon in HORIZONS:
            X_scaled = self.scalers[horizon].transform(X)
            all_probs = []
            all_weights = []
            weights = self.ensemble_weights.get(horizon, {})

            for model_type in MODEL_TYPES:
                if model_type not in self.models.get(horizon, {}):
                    continue

                model = self.models[horizon][model_type]
                try:
                    if hasattr(model, "predict_proba"):
                        probs = model.predict_proba(X_scaled)[:, 1]
                    elif hasattr(model, "decision_function"):
                        decisions = model.decision_function(X_scaled)
                        probs = 1 / (1 + np.exp(-decisions))
                    else:
                        probs = model.predict(X_scaled).astype(float)
                    all_probs.append(probs)
                    all_weights.append(weights.get(model_type, 0.25))
                except Exception as e:
                    logger.warning(f"History prediction failed for {model_type}/{horizon}m: {e}")

            if all_probs:
                w = np.array(all_weights)
                w = w / w.sum()
                # Per-model probs are in [0,1]. Weighted average gives the
                # raw ensemble in [0,1]. Apply the calibrator (if any) on
                # the raw [0,1] values; both columns published in percent.
                ensemble_raw = np.average(all_probs, axis=0, weights=w)
                calibrator = self.calibrators.get(horizon)
                if calibrator is not None:
                    ensemble_cal = apply_calibrator(calibrator, ensemble_raw)
                else:
                    ensemble_cal = ensemble_raw
                result[f"prob_{horizon}m"] = (ensemble_cal * 100).round(1)
                result[f"prob_{horizon}m_raw"] = (ensemble_raw * 100).round(1)
            else:
                result[f"prob_{horizon}m"] = 0.0
                result[f"prob_{horizon}m_raw"] = 0.0

        if "USREC" in df.columns:
            result["actual_recession"] = df["USREC"].values

        return result

    def save(self):
        """Save all model artifacts to disk."""
        save_model(self)

    def load(self) -> bool:
        """Load model artifacts from disk."""
        return load_model(self)

    def get_model_info(self) -> Dict[str, Any]:
        """Return model metadata and metrics for the frontend."""
        if not self.is_trained:
            return {"trained": False}

        return {
            "trained": True,
            "training_metadata": self.training_metadata,
            "metrics": {
                f"{h}m": self.metrics.get(h, {})
                for h in HORIZONS
            },
            "confusion_matrices": {
                f"{h}m": self.confusion_matrices.get(h, {})
                for h in HORIZONS
            },
            "best_model": {
                f"{h}m": self.best_model.get(h, "logistic")
                for h in HORIZONS
            },
            "decision_tree_rules": {
                f"{h}m": self.decision_tree_rules.get(h, [])
                for h in HORIZONS
            },
            "optimal_thresholds": {
                f"{h}m": self.optimal_thresholds.get(h, {})
                for h in HORIZONS
            },
            "ensemble_weights": {
                f"{h}m": self.ensemble_weights.get(h, {})
                for h in HORIZONS
            },
            "calibration_method": {
                f"{h}m": self.calibration_method.get(h)
                for h in HORIZONS
            },
            "calibration_brier_comparison": {
                f"{h}m": self.calibration_brier.get(h, {})
                for h in HORIZONS
            },
            "walk_forward_metrics": {
                f"{h}m": self.walk_forward_metrics.get(h, {})
                for h in HORIZONS
            },
            "operating_points": {
                f"{h}m": self.operating_points.get(h, [])
                for h in HORIZONS
            },
            "default_threshold": {
                f"{h}m": self.default_threshold.get(h, {})
                for h in HORIZONS
            },
            "model_types": MODEL_TYPES,
            "horizons": [f"{h}m" for h in HORIZONS],
        }
