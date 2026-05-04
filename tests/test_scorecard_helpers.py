"""Tests for scorecard module-level helpers (Phase 1 §1.5, Phase 3 §3.6/§3.7)."""
from datetime import date, timedelta
from unittest.mock import patch

from modules.risk_scorecard.scorecard import (
    PILLAR_WEIGHTS,
    _compute_pillar_deltas,
    _freshness_badge,
    _trend_from_series,
)


# ──────────────────────────────────────────────
# PILLAR_WEIGHTS contract
# ──────────────────────────────────────────────

def test_pillar_weights_sum_to_one():
    assert abs(sum(PILLAR_WEIGHTS.values()) - 1.0) < 1e-9


def test_pillar_weights_includes_housing():
    """Phase 3.1: housing should be a pillar after the reweight."""
    assert "housing" in PILLAR_WEIGHTS


# ──────────────────────────────────────────────
# _trend_from_series (Phase 1 §1.5)
# ──────────────────────────────────────────────

def test_trend_from_series_stable_under_threshold():
    assert _trend_from_series([10.0, 12.0, 11.0]) == "stable"


def test_trend_from_series_deteriorating_when_recent_higher():
    assert _trend_from_series([10, 10, 10, 50, 50, 50]) == "deteriorating"


def test_trend_from_series_improving_when_recent_lower():
    assert _trend_from_series([60, 60, 60, 30, 30, 30]) == "improving"


def test_trend_from_series_handles_none_values():
    # All None → stable (no data)
    assert _trend_from_series([None, None, None]) == "stable"
    # Mostly None → fall through gracefully
    assert _trend_from_series([None, None, 50.0]) == "stable"


# ──────────────────────────────────────────────
# _compute_pillar_deltas (Phase 3.6)
# ──────────────────────────────────────────────

def test_pillar_deltas_full_history():
    # Synthetic 30-day sparkline ending at 50
    history = list(range(20, 50))  # length 30
    deltas = _compute_pillar_deltas(current_score=55.0, historical_series=history)
    assert deltas["d1"] == 6.0  # 55 - 49
    assert deltas["w1"] == 12.0  # 55 - 43 (7 back from end)
    assert deltas["m1"] == 35.0  # 55 - 20 (oldest entry)


def test_pillar_deltas_short_history_only_1d_populated():
    history = [40.0, 45.0, 47.0]  # only 3 entries
    deltas = _compute_pillar_deltas(current_score=50.0, historical_series=history)
    # 1D: against most-recent
    assert deltas["d1"] == 3.0
    # 1W and 1M now require enough history; otherwise None so UI hides
    # the cell instead of showing a misleading short-window delta.
    assert deltas["w1"] is None
    assert deltas["m1"] is None


def test_pillar_deltas_14d_history_no_1m():
    # 14-day default sparkline: 1D + 1W populated, 1M None.
    history = [float(x) for x in range(14)]  # 0..13
    deltas = _compute_pillar_deltas(current_score=15.0, historical_series=history)
    assert deltas["d1"] == 2.0  # 15 - 13
    assert deltas["w1"] == 8.0  # 15 - 7
    assert deltas["m1"] is None


def test_pillar_deltas_no_history_all_none():
    deltas = _compute_pillar_deltas(current_score=50.0, historical_series=[])
    assert deltas == {"d1": None, "w1": None, "m1": None}


def test_pillar_deltas_filters_none_values():
    history = [None, None, 40.0, None, 45.0]
    deltas = _compute_pillar_deltas(current_score=50.0, historical_series=history)
    assert deltas["d1"] == 5.0  # 50 - 45 (last non-None)


# ──────────────────────────────────────────────
# _freshness_badge (Phase 3.7)
# ──────────────────────────────────────────────

def test_freshness_badge_fresh_within_14_days():
    today = date.today()
    recent = (today - timedelta(days=5)).isoformat()
    badge = _freshness_badge(recent)
    assert badge["level"] == "fresh"
    assert badge["age_days"] == 5


def test_freshness_badge_aging_15_to_45_days():
    today = date.today()
    aging = (today - timedelta(days=30)).isoformat()
    badge = _freshness_badge(aging)
    assert badge["level"] == "aging"
    assert "30d" in badge["label"]


def test_freshness_badge_stale_over_45_days():
    today = date.today()
    stale = (today - timedelta(days=90)).isoformat()
    badge = _freshness_badge(stale)
    assert badge["level"] == "stale"
    assert "stale" in badge["label"]


def test_freshness_badge_handles_iso_datetime_string():
    today = date.today()
    iso_dt = (today - timedelta(days=3)).isoformat() + "T12:00:00"
    badge = _freshness_badge(iso_dt)
    assert badge["level"] == "fresh"


def test_freshness_badge_handles_none():
    badge = _freshness_badge(None)
    assert badge["level"] == "unknown"


def test_freshness_badge_handles_unparseable():
    badge = _freshness_badge("not a date")
    assert badge["level"] == "unknown"
