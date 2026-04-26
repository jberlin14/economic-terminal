"""
Golden snapshot test for recession-model feature engineering.

Builds a deterministic synthetic input, runs `engineer_features`, and hashes a
stable subset of derived columns. Protects against silent behavior drift.
"""
import hashlib

import numpy as np
import pandas as pd

from modules.recession_model.features import engineer_features, FEATURE_SERIES


def _build_synthetic_df() -> pd.DataFrame:
    """Deterministic synthetic input: monthly index, 240 rows, all FEATURE_SERIES columns."""
    rng = np.random.RandomState(42)
    idx = pd.date_range("2005-01-31", periods=240, freq="ME")
    data = {}
    for col in FEATURE_SERIES.keys():
        data[col] = pd.Series(rng.normal(loc=50.0, scale=5.0, size=240), index=idx)
    return pd.DataFrame(data, index=idx)


# Stable, intentionally narrow column subset of derived features. Adding new
# features later should not break this test.
HASH_COLUMNS = ["unrate_chg3", "t10y2y_ma3", "vix_zscore", "payems_ma3"]

EXPECTED_HASH = "dd270c68c763f9bebd1fb151c2d523348a6a2ba2b9adfe2ca05330c439654bed"


def test_engineer_features_golden_snapshot():
    df = _build_synthetic_df()
    out = engineer_features(df)

    for col in HASH_COLUMNS:
        assert col in out.columns, f"expected hashed column {col!r} in engineered output"

    rounded = out[HASH_COLUMNS].round(6).fillna(0.0)
    csv_bytes = rounded.to_csv().encode("utf-8")
    actual = hashlib.sha256(csv_bytes).hexdigest()
    assert actual == EXPECTED_HASH, (
        f"Feature engineering output drifted.\n"
        f"Expected: {EXPECTED_HASH}\n"
        f"Actual:   {actual}\n"
        f"If this is intentional, update EXPECTED_HASH in the test."
    )
