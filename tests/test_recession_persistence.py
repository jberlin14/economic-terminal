"""
Round-trip test for recession-model persistence.

Builds a tiny trained RecessionModel by hand, saves it to a tmp directory,
loads it into a fresh instance, and asserts state and predictions match.
"""
import numpy as np
from sklearn.preprocessing import StandardScaler

from modules.recession_model import persistence
from modules.recession_model.features import HORIZONS
from modules.recession_model.model import RecessionModel
from modules.recession_model.training import MODEL_TYPES, create_model


def test_save_load_round_trip(tmp_path, monkeypatch):
    # Redirect persistence to a tmp directory
    monkeypatch.setattr(persistence, "MODEL_DIR", tmp_path)

    rng = np.random.RandomState(0)
    n_features = 5
    feature_names = [f"f{i}" for i in range(n_features)]
    X = rng.random((100, n_features))
    y = (X[:, 0] > 0.5).astype(int)

    m = RecessionModel()
    m.feature_names = feature_names
    for h in HORIZONS:
        scaler = StandardScaler().fit(X)
        m.scalers[h] = scaler
        Xs = scaler.transform(X)
        m.models[h] = {}
        m.metrics[h] = {}
        m.optimal_thresholds[h] = {}
        m.confusion_matrices[h] = {}
        for mt in MODEL_TYPES:
            mdl = create_model(mt)
            mdl.fit(Xs, y)
            m.models[h][mt] = mdl
            m.metrics[h][mt] = {"f1": 0.5, "auc_roc": 0.6}
            m.optimal_thresholds[h][mt] = 0.5
            m.confusion_matrices[h][mt] = [[10, 5], [5, 10]]
        m.ensemble_weights[h] = {mt: 0.25 for mt in MODEL_TYPES}
        m.best_model[h] = "logistic"
        m.decision_tree_rules[h] = []
        m.operating_points[h] = [
            {"threshold": 0.30, "precision": 0.4, "recall": 0.8, "f1": 0.53,
             "n_positive_predictions": 40, "support_positives": 25},
            {"threshold": 0.50, "precision": 0.7, "recall": 0.5, "f1": 0.58,
             "n_positive_predictions": 18, "support_positives": 25},
        ]
        m.default_threshold[h] = {
            "threshold": 0.50, "precision": 0.7, "recall": 0.5,
            "f1": 0.58, "selection": "precision_target",
        }
    m.training_metadata = {"trained_at": "2026-04-26T00:00:00", "n_samples": 100}
    m._loaded = True

    persistence.save_model(m)

    # Fresh instance
    m2 = RecessionModel()
    ok = persistence.load_model(m2)
    assert ok is True

    assert m2.feature_names == m.feature_names
    assert m2.metrics == m.metrics
    assert m2.ensemble_weights == m.ensemble_weights
    assert m2.optimal_thresholds == m.optimal_thresholds
    assert m2.operating_points == m.operating_points
    assert m2.default_threshold == m.default_threshold

    # Predict produces same output on the same input
    features = {f"f{i}": float(X[0, i]) for i in range(n_features)}
    p1 = m.predict(features)
    p2 = m2.predict(features)
    assert p1 == p2

    # Phase 4.1: explain_prediction returns a per-horizon contribution
    # breakdown built from logistic coefficients × scaled value.
    explanation = m2.explain_prediction(features, top_k=5)
    assert set(explanation.keys()) <= {"3m", "6m", "12m"}
    for h, payload in explanation.items():
        assert payload["model_used"] == "logistic"
        for entry in payload["top_pushing_up"]:
            assert entry["contribution"] >= 0
            assert "feature" in entry
            assert "scaled_value" in entry
            assert "coefficient" in entry
        for entry in payload["top_pulling_down"]:
            assert entry["contribution"] <= 0
