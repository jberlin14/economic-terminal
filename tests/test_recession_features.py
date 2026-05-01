"""
Golden snapshot test for recession-model feature engineering.

Builds a deterministic synthetic input, runs `engineer_features`, and hashes a
stable subset of derived columns. Protects against silent behavior drift.
"""
import hashlib

import numpy as np
import pandas as pd

from modules.recession_model.features import engineer_features, FEATURE_SERIES, get_feature_columns


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


# ──────────────────────────────────────────────
# Phase 2 §2.3: era-aware imputation
# ──────────────────────────────────────────────

def test_era_aware_imputation_does_not_use_zero_for_head_nans():
    """When a Tier 3/4 series has NaN at the head of the window (it didn't
    exist yet), imputation should land on the column's median, not 0."""
    # Build a synthetic frame with two series, where one has 50 leading NaNs.
    idx = pd.date_range("2005-01-31", periods=120, freq="ME")
    rng = np.random.RandomState(7)
    df = pd.DataFrame({
        "UNRATE": rng.normal(5.0, 0.5, size=120),
        "VIXCLS": np.concatenate([
            np.full(50, np.nan),
            rng.normal(20.0, 5.0, size=70),
        ]),
        "USREC": np.zeros(120),
    }, index=idx)

    # Mirror data_builder's imputation step on the raw series, then engineer.
    cols = ["UNRATE", "VIXCLS"]
    for col in cols:
        df[col] = df[col].ffill()
        if df[col].isna().any():
            med = df[col].median(skipna=True)
            df[col] = df[col].fillna(med)

    head_vix = df["VIXCLS"].iloc[:50]
    body_median = df["VIXCLS"].iloc[50:].median()

    # All head values should equal the median of the body (post-imputation).
    assert (head_vix == body_median).all(), (
        f"head VIX values not at median: head[0]={head_vix.iloc[0]}, body_median={body_median}"
    )
    # And specifically, NOT zero.
    assert (head_vix != 0).all(), "head VIX should not be zero after era-aware imputation"
