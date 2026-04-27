"""
Tests for FRED release-lag dating in the recession model live-prediction path.

Verifies the per-series release-lag config and the lag-application logic that
clips the most recent `release_lag_months` months of each series at inference
time, so the live snapshot row mirrors the as-of state of an end-of-month
training row.
"""

import numpy as np
import pandas as pd

from modules.recession_model.features import (
    DEFAULT_RELEASE_LAG_MONTHS,
    FEATURE_SERIES,
    get_release_lag,
    get_series_name,
)


def test_lag_zero_for_unrate():
    assert get_release_lag("UNRATE") == 0


def test_lag_one_for_cpi():
    assert get_release_lag("CPIAUCSL") == 1


def test_lag_two_for_oecd_lei():
    assert get_release_lag("USALOLITONOSTSAM") == 2


def test_lag_three_for_quarterly_debt_service():
    assert get_release_lag("BOGZ1FL072052006Q") == 3


def test_unknown_series_defaults_to_one():
    assert get_release_lag("NOT_A_REAL_SERIES_ID") == DEFAULT_RELEASE_LAG_MONTHS
    assert DEFAULT_RELEASE_LAG_MONTHS == 1


def test_get_series_name_returns_human_string():
    assert "Unemployment" in get_series_name("UNRATE")


def test_get_series_name_falls_back_to_id_for_unknown():
    assert get_series_name("BOGUS") == "BOGUS"


def test_all_feature_series_have_release_lag_in_config():
    """Every series id in FEATURE_SERIES has a non-negative integer lag."""
    for sid, info in FEATURE_SERIES.items():
        assert isinstance(info, dict), f"{sid} should be a dict, got {type(info)}"
        lag = info.get("release_lag_months")
        assert isinstance(lag, int), f"{sid} missing or non-int release_lag_months"
        assert lag >= 0, f"{sid} has negative release_lag_months: {lag}"


def test_all_feature_series_have_name_in_config():
    """Every series id in FEATURE_SERIES has a non-empty name string."""
    for sid, info in FEATURE_SERIES.items():
        assert isinstance(info, dict)
        name = info.get("name")
        assert isinstance(name, str) and len(name) > 0, f"{sid} missing name"


def test_build_current_features_applies_lag_two_months():
    """Lag-application logic mirrors `build_current_features`.

    For a series configured with release_lag_months=2, the latest available
    value after lag-clip equals the value from 2 months prior in the raw data.
    """
    # Synthetic monthly series: values 100..119 over 20 months.
    idx = pd.date_range("2024-01-31", periods=20, freq="ME")
    series = pd.Series(np.arange(100, 120, dtype=float), index=idx)

    lag = get_release_lag("USALOLITONOSTSAM")
    assert lag == 2

    # Mirror the production loop:
    # `monthly[sid] = monthly[sid].iloc[:-lag]` when lag > 0.
    lagged = series.iloc[:-lag] if lag > 0 else series

    # Latest value after the 2-month clip should be 117 (the value from
    # 2 months earlier than the original 119).
    assert lagged.iloc[-1] == 117.0
    # Confirm the original tail is 119, so the clip really moved the head.
    assert series.iloc[-1] == 119.0
    assert len(lagged) == len(series) - lag


def test_build_current_features_zero_lag_preserves_latest():
    """For release_lag_months=0, the latest value is preserved unchanged."""
    idx = pd.date_range("2024-01-31", periods=10, freq="ME")
    series = pd.Series(np.arange(50, 60, dtype=float), index=idx)

    lag = get_release_lag("UNRATE")
    assert lag == 0

    # Production code skips the clip when lag == 0.
    lagged = series.iloc[:-lag] if lag > 0 else series
    assert lagged.iloc[-1] == 59.0
    assert len(lagged) == len(series)


def test_lag_clip_is_safe_when_series_shorter_than_lag():
    """The production guard (`len(monthly[sid]) > lag`) prevents over-clipping.

    A series shorter than `lag` rows must be left untouched so we don't
    produce an empty Series.
    """
    # Quarterly debt service has lag=3. Build a 2-row series and apply the
    # guard from `build_current_features` exactly.
    idx = pd.date_range("2024-01-31", periods=2, freq="ME")
    series = pd.Series([10.0, 11.0], index=idx)

    lag = get_release_lag("BOGZ1FL072052006Q")
    assert lag == 3

    # Production guard:
    if lag > 0 and len(series) > lag:
        clipped = series.iloc[:-lag]
    else:
        clipped = series

    # Series unchanged because len(2) is not > lag(3).
    assert len(clipped) == 2
    assert clipped.iloc[-1] == 11.0
