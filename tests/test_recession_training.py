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
    _balanced_sample_weights,
    _undersample_majority,
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


# ──────────────────────────────────────────────
# Phase 2 §2.1: class imbalance helpers
# ──────────────────────────────────────────────

def test_balanced_sample_weights_inverse_frequency():
    """Each class's weight should be inversely proportional to its count."""
    y = np.array([0] * 80 + [1] * 20)
    w = _balanced_sample_weights(y)

    # Mean weight should equal 1 (per sklearn's balanced formula).
    assert abs(w.mean() - 1.0) < 1e-9
    # Minority weight = n / (n_classes * count) = 100 / (2 * 20) = 2.5
    # Majority weight = 100 / (2 * 80) = 0.625
    assert abs(w[y == 1][0] - 2.5) < 1e-9
    assert abs(w[y == 0][0] - 0.625) < 1e-9


def test_balanced_sample_weights_single_class():
    y = np.array([0] * 50)
    w = _balanced_sample_weights(y)
    assert (w == 1.0).all()


def test_undersample_majority_balances_classes():
    rng = np.random.RandomState(0)
    X = rng.random((100, 4))
    y = np.array([0] * 80 + [1] * 20)

    X_bal, y_bal = _undersample_majority(X, y, random_state=42)
    classes, counts = np.unique(y_bal, return_counts=True)
    assert set(classes) == {0, 1}
    assert counts[0] == counts[1] == 20


def test_undersample_majority_single_class_passthrough():
    X = np.zeros((10, 3))
    y = np.zeros(10, dtype=int)
    X_out, y_out = _undersample_majority(X, y)
    assert X_out.shape == X.shape
    assert (y_out == y).all()


def test_logistic_uses_l1_and_produces_sparse_coefficients():
    """Phase 2 §2.2: L1 logistic should zero a meaningful share of features
    on a high-dimensional, mostly-uninformative problem."""
    rng = np.random.RandomState(3)
    n, p = 200, 50
    informative = 5
    X = rng.standard_normal((n, p))
    # Only the first `informative` features carry signal.
    logits = X[:, :informative].sum(axis=1) * 1.5
    y = (logits + rng.standard_normal(n) * 0.5 > 0).astype(int)

    sc = StandardScaler()
    Xs = sc.fit_transform(X)
    feature_names = [f"f{i}" for i in range(p)]

    metrics, fitted, _ = train_single_model(
        "logistic", Xs[:140], y[:140], Xs[140:], y[140:], feature_names,
    )

    # Confirm L1 was used.
    assert fitted.penalty == "l1"
    assert fitted.solver == "liblinear"

    coefs = fitted.coef_[0]
    n_nonzero = int(np.sum(np.abs(coefs) > 1e-9))
    # L1 with C=0.1 should sparsify well below the full feature count.
    assert n_nonzero < p, f"L1 produced no sparsity: {n_nonzero}/{p}"


def test_knn_uses_undersampling_and_gb_uses_sample_weights(monkeypatch):
    """Smoke test that the imbalance handling actually changes what KNN/GB see.

    We patch each estimator's `fit` to capture the data it was given, then run
    train_single_model and assert the KNN call received a balanced subset and
    the GradientBoosting call received a `sample_weight` kwarg.
    """
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.ensemble import GradientBoostingClassifier

    X_train, y_train, X_test, y_test, feature_names = _make_data()

    knn_capture: dict = {}
    orig_knn_fit = KNeighborsClassifier.fit

    def knn_fit(self, X, y):
        knn_capture["n"] = len(y)
        knn_capture["pos"] = int((y == 1).sum())
        knn_capture["neg"] = int((y == 0).sum())
        return orig_knn_fit(self, X, y)

    monkeypatch.setattr(KNeighborsClassifier, "fit", knn_fit)
    train_single_model("knn", X_train, y_train, X_test, y_test, feature_names)
    assert knn_capture["pos"] == knn_capture["neg"], (
        f"KNN saw imbalanced data: {knn_capture}"
    )

    gb_capture: dict = {}
    orig_gb_fit = GradientBoostingClassifier.fit

    def gb_fit(self, X, y, sample_weight=None, **kwargs):
        gb_capture["sample_weight_mean"] = (
            float(np.mean(sample_weight)) if sample_weight is not None else None
        )
        return orig_gb_fit(self, X, y, sample_weight=sample_weight, **kwargs)

    monkeypatch.setattr(GradientBoostingClassifier, "fit", gb_fit)
    train_single_model(
        "gradient_boosting", X_train, y_train, X_test, y_test, feature_names,
    )
    assert gb_capture["sample_weight_mean"] is not None
    assert abs(gb_capture["sample_weight_mean"] - 1.0) < 1e-6
