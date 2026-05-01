"""
Recession Model Training Pipeline — per-model fit/eval helpers.

Pure module-level functions for creating, fitting, and evaluating individual
models. Carved out of `RecessionModel` so the orchestrator in `model.py`
focuses on cross-horizon coordination, not per-model mechanics.
"""

from typing import Any, Dict, List, Tuple

import numpy as np
from loguru import logger

from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score,
    roc_auc_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)


HORIZONS_LABELS = {3: "3-month", 6: "6-month", 12: "12-month"}

MODEL_TYPES = {
    "logistic": "Logistic Regression",
    "knn": "K-Nearest Neighbors",
    "random_forest": "Random Forest",
    "gradient_boosting": "Gradient Boosting",
}


def create_model(model_type: str):
    """Create a fresh model instance by type."""
    if model_type == "logistic":
        # L1-penalized logistic with light regularization (Phase 2 §2.2).
        # On 199 features over ~800 samples the legacy L2 fit produced
        # diffuse coefficients that didn't generalize. L1 zeroes irrelevant
        # features, leaving a sparse coefficient list that the UI can
        # surface honestly. liblinear is the only sklearn solver that
        # supports L1 + binary classification reliably.
        return LogisticRegression(
            penalty="l1", C=0.1, max_iter=2000, class_weight="balanced",
            solver="liblinear", random_state=42,
        )
    elif model_type == "knn":
        # KNN doesn't accept class_weight. We compensate at fit time via
        # `train_single_model`, which under-samples the majority class to
        # match positive recession-month support (Phase 2 §2.1).
        return KNeighborsClassifier(n_neighbors=5, weights="distance")
    elif model_type == "random_forest":
        return RandomForestClassifier(
            n_estimators=200, max_depth=8, min_samples_leaf=5,
            class_weight="balanced", random_state=42, n_jobs=-1,
        )
    elif model_type == "gradient_boosting":
        # GradientBoostingClassifier accepts sample_weight at fit time.
        # `train_single_model` passes inverse-class-frequency weights
        # (Phase 2 §2.1) — recessions are 14-24% of months and were
        # previously under-called by the unweighted GB head.
        return GradientBoostingClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.05,
            min_samples_leaf=10, subsample=0.8, random_state=42,
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}")


def _balanced_sample_weights(y: np.ndarray) -> np.ndarray:
    """
    Return per-sample weights inversely proportional to class frequency,
    normalized so the mean weight is 1. Mirrors sklearn's class_weight='balanced'
    formula (n_samples / (n_classes * class_count)) but as an explicit array
    for estimators that don't expose `class_weight` (e.g. GradientBoosting).
    """
    classes, counts = np.unique(y, return_counts=True)
    n_samples = len(y)
    n_classes = len(classes)
    if n_classes < 2:
        return np.ones_like(y, dtype=float)
    class_weight = {c: n_samples / (n_classes * cnt) for c, cnt in zip(classes, counts)}
    return np.array([class_weight[v] for v in y], dtype=float)


def _undersample_majority(
    X: np.ndarray, y: np.ndarray, random_state: int = 42
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Randomly under-sample the majority class to match minority support.
    Used for KNN, which has no class-weight or sample-weight knob.

    Order is preserved within each class so callers that care about time
    ordering can re-sort by index if needed (the KNN fit is order-invariant).
    """
    classes, counts = np.unique(y, return_counts=True)
    if len(classes) < 2:
        return X, y
    minority_class = classes[np.argmin(counts)]
    majority_class = classes[np.argmax(counts)]
    n_minority = int(min(counts))

    rng = np.random.RandomState(random_state)
    minority_idx = np.where(y == minority_class)[0]
    majority_idx = np.where(y == majority_class)[0]
    if len(majority_idx) > n_minority:
        majority_idx = rng.choice(majority_idx, size=n_minority, replace=False)
    keep = np.sort(np.concatenate([minority_idx, majority_idx]))
    return X[keep], y[keep]


def find_optimal_threshold(y_true: np.ndarray, y_prob: np.ndarray) -> float:
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


def train_single_model(
    model_type: str,
    X_train: np.ndarray, y_train: np.ndarray,
    X_test: np.ndarray, y_test: np.ndarray,
    feature_names: List[str],
) -> Tuple[Dict[str, Any], Any, float]:
    """
    Train a single model type and compute test-set metrics.

    Returns (metrics, fitted_model, optimal_threshold). The caller is
    responsible for storing these on the orchestrator's state.
    """

    model = create_model(model_type)

    if len(np.unique(y_train)) < 2:
        raise ValueError("Training set has only one class")

    # Class imbalance handling for the two estimators that don't expose
    # `class_weight` (Phase 2 §2.1):
    #   - KNN: under-sample the majority class to match minority support.
    #   - GradientBoosting: pass balanced sample_weight at fit time.
    if model_type == "knn":
        X_fit, y_fit = _undersample_majority(X_train, y_train)
        model.fit(X_fit, y_fit)
    elif model_type == "gradient_boosting":
        model.fit(X_train, y_train, sample_weight=_balanced_sample_weights(y_train))
    else:
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
    optimal_threshold = find_optimal_threshold(y_test, y_prob)

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
            zip(feature_names, importances.tolist()),
            key=lambda x: abs(x[1]), reverse=True,
        )
        metrics["feature_importance"] = [
            {"feature": name, "importance": round(imp, 4)}
            for name, imp in importance_list[:15]
        ]
    elif hasattr(model, "coef_"):
        coefs = model.coef_[0] if model.coef_.ndim > 1 else model.coef_
        importance_list = sorted(
            zip(feature_names, coefs.tolist()),
            key=lambda x: abs(x[1]), reverse=True,
        )
        metrics["feature_importance"] = [
            {"feature": name, "coefficient": round(coef, 4)}
            for name, coef in importance_list[:15]
        ]

    return metrics, model, optimal_threshold


def extract_tree_rules(
    rf_model: RandomForestClassifier,
    feature_names: List[str],
) -> List[Dict]:
    """
    Extract interpretable decision rules from the random forest.
    Takes the most important tree paths to build a logic tree.
    """
    rules: List[Dict] = []
    if not hasattr(rf_model, 'estimators_') or not rf_model.estimators_:
        return rules

    # Use the first tree as representative
    tree = rf_model.estimators_[0]
    tree_struct = tree.tree_

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
