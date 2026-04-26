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
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import numpy as np
import pandas as pd
from loguru import logger

import joblib

from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score,
    roc_auc_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)

from .data_builder import RecessionDataBuilder
from .features import HORIZONS

MODEL_DIR = Path("data/recession_model")
HORIZONS_LABELS = {3: "3-month", 6: "6-month", 12: "12-month"}

MODEL_TYPES = {
    "logistic": "Logistic Regression",
    "knn": "K-Nearest Neighbors",
    "random_forest": "Random Forest",
    "gradient_boosting": "Gradient Boosting",
}


def _create_model(model_type: str):
    """Create a fresh model instance by type."""
    if model_type == "logistic":
        return LogisticRegression(
            C=1.0, max_iter=1000, class_weight="balanced",
            solver="lbfgs", random_state=42,
        )
    elif model_type == "knn":
        return KNeighborsClassifier(n_neighbors=5, weights="distance")
    elif model_type == "random_forest":
        return RandomForestClassifier(
            n_estimators=200, max_depth=8, min_samples_leaf=5,
            class_weight="balanced", random_state=42, n_jobs=-1,
        )
    elif model_type == "gradient_boosting":
        return GradientBoostingClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.05,
            min_samples_leaf=10, subsample=0.8, random_state=42,
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}")


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
                    model_metrics, fitted_model = self._train_single_model(
                        model_type, X_train, y_train, X_test, y_test, horizon
                    )

                    self.models[horizon][model_type] = fitted_model
                    self.metrics[horizon][model_type] = model_metrics
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
                self.decision_tree_rules[horizon] = self._extract_tree_rules(
                    self.models[horizon]["random_forest"], horizon
                )

            # Now refit all models on FULL data for production predictions
            scaler_full = StandardScaler()
            X_full = scaler_full.fit_transform(X)
            self.scalers[horizon] = scaler_full

            for model_type in MODEL_TYPES:
                if model_type in self.models[horizon]:
                    try:
                        full_model = _create_model(model_type)
                        full_model.fit(X_full, y)
                        self.models[horizon][model_type] = full_model
                    except Exception as e:
                        logger.warning(f"Failed to refit {model_type} on full data: {e}")

            # Re-extract tree rules from full-data random forest
            if "random_forest" in self.models[horizon]:
                rf = self.models[horizon]["random_forest"]
                if hasattr(rf, 'estimators_'):
                    self.decision_tree_rules[horizon] = self._extract_tree_rules(rf, horizon)

            results[f"{horizon}m"] = horizon_results

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
        }

        self._loaded = True
        self.save()

        return {
            "status": "trained",
            "metadata": self.training_metadata,
            "metrics": results,
        }

    def _train_single_model(
        self, model_type: str,
        X_train: np.ndarray, y_train: np.ndarray,
        X_test: np.ndarray, y_test: np.ndarray,
        horizon: int,
    ) -> Tuple[Dict[str, Any], Any]:
        """Train a single model type and compute test-set metrics."""

        model = _create_model(model_type)

        if len(np.unique(y_train)) < 2:
            raise ValueError("Training set has only one class")

        model.fit(X_train, y_train)

        # Get probabilities
        if hasattr(model, "predict_proba"):
            y_prob = model.predict_proba(X_test)[:, 1]
        elif hasattr(model, "decision_function"):
            decisions = model.decision_function(X_test)
            y_prob = 1 / (1 + np.exp(-decisions))
        else:
            y_prob = model.predict(X_test).astype(float)

        # Find optimal threshold that maximizes F1
        optimal_threshold = self._find_optimal_threshold(y_test, y_prob)
        self.optimal_thresholds[horizon] = self.optimal_thresholds.get(horizon, {})
        self.optimal_thresholds[horizon][model_type] = optimal_threshold

        # Use optimal threshold for classification metrics
        y_pred_optimal = (y_prob >= optimal_threshold).astype(int)
        # Also compute default 0.5 predictions for reference
        y_pred_default = (y_prob >= 0.5).astype(int)

        # Compute metrics using optimal threshold
        cm = confusion_matrix(y_test, y_pred_optimal, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()

        metrics = {
            "accuracy": round(float(accuracy_score(y_test, y_pred_optimal)), 4),
            "precision": round(float(precision_score(y_test, y_pred_optimal, zero_division=0)), 4),
            "recall": round(float(recall_score(y_test, y_pred_optimal, zero_division=0)), 4),
            "f1": round(float(f1_score(y_test, y_pred_optimal, zero_division=0)), 4),
            "specificity": round(float(tn / (tn + fp)) if (tn + fp) > 0 else 0, 4),
            "balanced_accuracy": round(float(
                (recall_score(y_test, y_pred_optimal, zero_division=0) +
                 (tn / (tn + fp) if (tn + fp) > 0 else 0)) / 2
            ), 4),
            "optimal_threshold": round(float(optimal_threshold), 3),
            "confusion_matrix": {
                "true_positives": int(tp),
                "false_positives": int(fp),
                "true_negatives": int(tn),
                "false_negatives": int(fn),
            },
        }

        # AUC-ROC (threshold-independent, uses probabilities directly)
        if len(np.unique(y_test)) > 1:
            metrics["auc_roc"] = round(float(roc_auc_score(y_test, y_prob)), 4)
        else:
            metrics["auc_roc"] = 0.5

        # Feature importances
        if hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
            importance_list = sorted(
                zip(self.feature_names, importances.tolist()),
                key=lambda x: abs(x[1]), reverse=True,
            )
            metrics["feature_importance"] = [
                {"feature": name, "importance": round(imp, 4)}
                for name, imp in importance_list[:15]
            ]
        elif hasattr(model, "coef_"):
            coefs = model.coef_[0] if model.coef_.ndim > 1 else model.coef_
            importance_list = sorted(
                zip(self.feature_names, coefs.tolist()),
                key=lambda x: abs(x[1]), reverse=True,
            )
            metrics["feature_importance"] = [
                {"feature": name, "coefficient": round(coef, 4)}
                for name, coef in importance_list[:15]
            ]

        self.confusion_matrices[horizon] = self.confusion_matrices.get(horizon, {})
        self.confusion_matrices[horizon][model_type] = cm.tolist()

        return metrics, model

    @staticmethod
    def _find_optimal_threshold(y_true: np.ndarray, y_prob: np.ndarray) -> float:
        """Find the threshold that maximizes F1 score on the test set."""
        best_f1 = 0.0
        best_threshold = 0.5
        for threshold in np.arange(0.10, 0.90, 0.01):
            y_pred = (y_prob >= threshold).astype(int)
            f1 = f1_score(y_true, y_pred, zero_division=0)
            if f1 > best_f1:
                best_f1 = f1
                best_threshold = threshold
        return best_threshold

    def _extract_tree_rules(self, rf_model: RandomForestClassifier, horizon: int) -> List[Dict]:
        """
        Extract interpretable decision rules from the random forest.
        Takes the most important tree paths to build a logic tree.
        """
        rules = []
        if not hasattr(rf_model, 'estimators_') or not rf_model.estimators_:
            return rules

        # Use the first tree as representative
        tree = rf_model.estimators_[0]
        tree_struct = tree.tree_

        feature_names = self.feature_names
        importances = rf_model.feature_importances_

        # Get top 5 most important features
        top_indices = np.argsort(importances)[::-1][:5]

        # Walk the tree to extract rules for recession prediction
        def _walk(node_id, path, depth):
            if depth > 4:
                return
            if tree_struct.feature[node_id] < 0:
                # Leaf node
                values = tree_struct.value[node_id][0]
                total = values.sum()
                if total > 0:
                    recession_prob = values[1] / total if len(values) > 1 else 0
                    if len(path) >= 1:
                        rules.append({
                            "conditions": list(path),
                            "recession_probability": round(float(recession_prob * 100), 1),
                            "samples": int(total),
                        })
                return

            feat_idx = tree_struct.feature[node_id]
            threshold = tree_struct.threshold[node_id]
            feat_name = feature_names[feat_idx] if feat_idx < len(feature_names) else f"feature_{feat_idx}"

            # Only follow paths for important features
            if feat_idx in top_indices:
                left_path = path + [f"{feat_name} <= {threshold:.2f}"]
                right_path = path + [f"{feat_name} > {threshold:.2f}"]
                _walk(tree_struct.children_left[node_id], left_path, depth + 1)
                _walk(tree_struct.children_right[node_id], right_path, depth + 1)
            else:
                _walk(tree_struct.children_left[node_id], path, depth)
                _walk(tree_struct.children_right[node_id], path, depth)

        _walk(0, [], 0)

        # Sort by recession probability descending, take most interesting rules
        rules.sort(key=lambda r: r["recession_probability"], reverse=True)

        # Keep top high-risk and top low-risk rules
        high_risk = [r for r in rules if r["recession_probability"] >= 50][:5]
        low_risk = [r for r in rules if r["recession_probability"] < 30][-3:]

        return high_risk + low_risk

    def predict(self, features: Dict[str, float]) -> Dict[str, Any]:
        """
        Generate recession probabilities from current feature values.
        Returns ensemble and per-model probabilities.
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() or load() first.")

        X = np.array([[features.get(f, 0.0) for f in self.feature_names]])

        model_probs = {}
        ensemble = {}

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

            # Ensemble = AUC-weighted average
            if horizon_probs and horizon_weights:
                w = np.array(horizon_weights)
                w = w / w.sum()  # re-normalize in case a model was skipped
                ensemble[f"{horizon}m"] = round(float(np.average(horizon_probs, weights=w)), 1)
            else:
                ensemble[f"{horizon}m"] = 0.0

        return {
            "ensemble": ensemble,
            "models": model_probs,
        }

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
                ensemble_probs = np.average(all_probs, axis=0, weights=w)
                result[f"prob_{horizon}m"] = (ensemble_probs * 100).round(1)
            else:
                result[f"prob_{horizon}m"] = 0.0

        if "USREC" in df.columns:
            result["actual_recession"] = df["USREC"].values

        return result

    def save(self):
        """Save all model artifacts to disk."""
        MODEL_DIR.mkdir(parents=True, exist_ok=True)

        for horizon in HORIZONS:
            # Save scaler
            joblib.dump(
                self.scalers[horizon],
                MODEL_DIR / f"scaler_{horizon}m.joblib",
            )
            # Save each model type
            for model_type in MODEL_TYPES:
                if model_type in self.models.get(horizon, {}):
                    joblib.dump(
                        self.models[horizon][model_type],
                        MODEL_DIR / f"model_{model_type}_{horizon}m.joblib",
                    )

        meta = {
            "feature_names": self.feature_names,
            "metrics": {
                str(h): {mt: m for mt, m in mts.items()}
                for h, mts in self.metrics.items()
            },
            "confusion_matrices": {
                str(h): {mt: cm for mt, cm in cms.items()}
                for h, cms in self.confusion_matrices.items()
            },
            "best_model": {str(k): v for k, v in self.best_model.items()},
            "decision_tree_rules": {
                str(k): v for k, v in self.decision_tree_rules.items()
            },
            "optimal_thresholds": {
                str(h): {mt: t for mt, t in thresholds.items()}
                for h, thresholds in self.optimal_thresholds.items()
            },
            "ensemble_weights": {
                str(h): {mt: w for mt, w in weights.items()}
                for h, weights in self.ensemble_weights.items()
            },
            "training_metadata": self.training_metadata,
            "model_types": list(MODEL_TYPES.keys()),
        }
        with open(MODEL_DIR / "metadata.json", "w") as f:
            json.dump(meta, f, indent=2)

        logger.success(f"Multi-model ensemble saved to {MODEL_DIR}")

    def load(self) -> bool:
        """Load model artifacts from disk."""
        meta_path = MODEL_DIR / "metadata.json"
        if not meta_path.exists():
            logger.debug("No saved recession model found")
            return False

        try:
            with open(meta_path) as f:
                meta = json.load(f)

            self.feature_names = meta["feature_names"]
            self.training_metadata = meta.get("training_metadata", {})

            # Load metrics
            stored_metrics = meta.get("metrics", {})
            self.metrics = {}
            for h_str, model_metrics in stored_metrics.items():
                h = int(h_str)
                self.metrics[h] = model_metrics

            # Load confusion matrices
            stored_cms = meta.get("confusion_matrices", {})
            self.confusion_matrices = {}
            for h_str, cms in stored_cms.items():
                self.confusion_matrices[int(h_str)] = cms

            self.best_model = {
                int(k): v for k, v in meta.get("best_model", {}).items()
            }
            self.decision_tree_rules = {
                int(k): v for k, v in meta.get("decision_tree_rules", {}).items()
            }
            self.optimal_thresholds = {
                int(k): v for k, v in meta.get("optimal_thresholds", {}).items()
            }
            self.ensemble_weights = {
                int(k): v for k, v in meta.get("ensemble_weights", {}).items()
            }

            # Determine which model types to load
            model_types = meta.get("model_types", list(MODEL_TYPES.keys()))

            # Load models and scalers
            self.models = {}
            self.scalers = {}

            for horizon in HORIZONS:
                scaler_path = MODEL_DIR / f"scaler_{horizon}m.joblib"
                if not scaler_path.exists():
                    # Backwards compat: try old single-model format
                    return self._load_legacy()
                self.scalers[horizon] = joblib.load(scaler_path)

                self.models[horizon] = {}
                for model_type in model_types:
                    model_path = MODEL_DIR / f"model_{model_type}_{horizon}m.joblib"
                    if model_path.exists():
                        self.models[horizon][model_type] = joblib.load(model_path)

                if not self.models[horizon]:
                    logger.warning(f"No models loaded for {horizon}m horizon")
                    return False

            self._loaded = True
            logger.info(f"Multi-model recession ensemble loaded ({len(model_types)} model types)")
            return True

        except Exception as e:
            logger.error(f"Failed to load recession model: {e}")
            return False

    def _load_legacy(self) -> bool:
        """Load old single-model format for backwards compatibility."""
        try:
            meta_path = MODEL_DIR / "metadata.json"
            with open(meta_path) as f:
                meta = json.load(f)

            self.feature_names = meta["feature_names"]
            self.training_metadata = meta.get("training_metadata", {})

            # Old format had metrics keyed by horizon directly
            old_metrics = meta.get("metrics", {})
            self.metrics = {}
            for h_str, m in old_metrics.items():
                h = int(h_str)
                # Wrap in logistic key
                self.metrics[h] = {"logistic": m}

            self.models = {}
            self.scalers = {}

            for horizon in HORIZONS:
                # Old format: model_{horizon}m.joblib, scaler_{horizon}m.joblib
                model_path = MODEL_DIR / f"model_{horizon}m.joblib"
                scaler_path = MODEL_DIR / f"scaler_{horizon}m.joblib"
                if not model_path.exists() or not scaler_path.exists():
                    return False

                self.scalers[horizon] = joblib.load(scaler_path)
                self.models[horizon] = {"logistic": joblib.load(model_path)}

            self.best_model = {h: "logistic" for h in HORIZONS}
            self._loaded = True
            logger.info("Loaded legacy single-model recession model")
            return True

        except Exception as e:
            logger.error(f"Failed to load legacy model: {e}")
            return False

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
            "model_types": MODEL_TYPES,
            "horizons": [f"{h}m" for h in HORIZONS],
        }
