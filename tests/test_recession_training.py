"""
Contract tests for the per-model training pipeline.

For each model type, verifies that train_single_model returns the expected
(metrics, model, threshold) tuple shape and that the metrics dict carries the
documented keys. Uses a synthetic imbalanced classification problem.
"""
import numpy as np
import pytest
from sklearn.datasets import make_classification
from sklearn.preprocessing import StandardScaler

from modules.recession_model.training import (
    MODEL_TYPES,
    find_optimal_threshold,
    train_single_model,
)


def _make_data(seed: int = 0):
    X, y = make_classification(
        n_samples=200,
        n_features=20,
        n_informative=10,
        n_redundant=5,
        weights=[0.85, 0.15],  # imbalance like real recessions
        random_state=seed,
    )
    split = 140
    X_train_raw, X_test_raw = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    sc = StandardScaler()
    X_train = sc.fit_transform(X_train_raw)
    X_test = sc.transform(X_test_raw)
    feature_names = [f"f{i}" for i in range(X.shape[1])]
    return X_train, y_train, X_test, y_test, feature_names


@pytest.mark.parametrize("model_type", list(MODEL_TYPES.keys()))
def test_train_single_model_contract(model_type):
    X_train, y_train, X_test, y_test, feature_names = _make_data()
    metrics, fitted, threshold = train_single_model(
        model_type, X_train, y_train, X_test, y_test, feature_names,
    )

    expected_keys = {
        "accuracy", "precision", "recall", "f1", "auc_roc",
        "optimal_threshold", "confusion_matrix",
    }
    missing = expected_keys - set(metrics.keys())
    assert not missing, f"Missing keys: {missing}"

    assert hasattr(fitted, "predict_proba") or hasattr(fitted, "decision_function")
    assert 0.0 <= threshold <= 1.0


def test_find_optimal_threshold_range():
    rng = np.random.RandomState(0)
    y = (rng.random(100) > 0.7).astype(int)
    p = rng.random(100)
    t = find_optimal_threshold(y, p)
    assert 0.0 <= t <= 1.0
