"""Tests for scorecard composite cutoff back-test (Phase 2 §2.6)."""
from datetime import date, timedelta
from unittest.mock import MagicMock

from modules.risk_scorecard.backtest import (
    backtest_composite_cutoff,
    _is_recession_within,
)


def test_is_recession_within_true_for_near_date():
    snap = date(2008, 6, 1)
    nber = [date(2008, 12, 1)]  # 6 months later
    assert _is_recession_within(snap, nber, lookahead_days=365) is True


def test_is_recession_within_false_for_far_date():
    snap = date(2008, 6, 1)
    nber = [date(2009, 12, 1)]  # 18 months later — outside 365-day window
    assert _is_recession_within(snap, nber, lookahead_days=365) is False


def test_is_recession_within_false_for_past_date():
    snap = date(2008, 6, 1)
    nber = [date(2007, 6, 1)]  # before snapshot
    assert _is_recession_within(snap, nber, lookahead_days=365) is False


def _make_journal_entry(d, composite):
    e = MagicMock()
    e.date = d
    e.pillar_scores_snapshot = {"composite": composite}
    return e


def test_backtest_no_entries_returns_skipped():
    db = MagicMock()
    db.query.return_value.order_by.return_value.all.return_value = []
    result = backtest_composite_cutoff(db)
    assert result["n_snapshots"] == 0
    assert result["cutoffs"] == []


def test_backtest_no_nber_dates_returns_skipped_with_note():
    db = MagicMock()
    db.query.return_value.order_by.return_value.all.return_value = [
        _make_journal_entry(date(2008, 1, 1), 70.0),
    ]
    # _load_nber_dates fallback also returns [] (no indicator) so no NBER list.
    result = backtest_composite_cutoff(db, nber_dates=[])
    assert result["n_snapshots"] == 1
    assert result["cutoffs"] == []
    assert "NBER" in result["note"]


def test_backtest_perfect_signal_high_precision_recall():
    """High composite scores should align with NBER recessions ahead."""
    db = MagicMock()
    entries = [
        _make_journal_entry(date(2008, 1, 1), 80.0),  # recession in 6mo -> TP at 67
        _make_journal_entry(date(2008, 7, 1), 75.0),  # recession ongoing -> TP at 67
        _make_journal_entry(date(2010, 1, 1), 25.0),  # no recession near -> TN at 67
        _make_journal_entry(date(2015, 1, 1), 30.0),  # no recession near -> TN at 67
    ]
    db.query.return_value.order_by.return_value.all.return_value = entries

    nber = [date(2008, 6, 1), date(2008, 7, 1), date(2008, 8, 1)]

    result = backtest_composite_cutoff(db, cutoffs=(50.0, 67.0), nber_dates=nber)
    assert result["n_snapshots"] == 4
    assert result["n_positive_outcomes"] == 2

    by_cutoff = {row["cutoff"]: row for row in result["cutoffs"]}
    # At cutoff 67: both high-composite snapshots flag, both align with
    # NBER -> precision = 1.0, recall = 1.0
    assert by_cutoff[67.0]["precision"] == 1.0
    assert by_cutoff[67.0]["recall"] == 1.0
    assert by_cutoff[67.0]["f1"] == 1.0


def test_backtest_handles_missing_composite_gracefully():
    """Entries without composite in pillar_scores_snapshot should be ignored."""
    db = MagicMock()
    no_composite = MagicMock()
    no_composite.date = date(2008, 1, 1)
    no_composite.pillar_scores_snapshot = {}  # missing composite

    valid = _make_journal_entry(date(2008, 6, 1), 70.0)

    db.query.return_value.order_by.return_value.all.return_value = [no_composite, valid]
    nber = [date(2008, 12, 1)]

    result = backtest_composite_cutoff(db, cutoffs=(67.0,), nber_dates=nber)
    assert result["n_snapshots"] == 1  # only the valid entry counted


# ──────────────────────────────────────────────
# _load_nber_dates against a real DB session
# ──────────────────────────────────────────────

def test_load_nber_dates_returns_usrec_positive_dates(tmp_path, monkeypatch):
    """Regression for pass-4 finding: _load_nber_dates queried a non-existent
    `IndicatorValue.indicator_id` column, silently returning [] even when
    USREC was populated. This exercises the fixed series_id-based query
    path against a real SQLite session."""
    db_path = tmp_path / "nber.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    import importlib
    from modules.data_storage import database as db_mod
    importlib.reload(db_mod)
    from modules.data_storage import schema  # noqa: F401
    db_mod.init_db()

    from modules.data_storage.schema import EconomicIndicator, IndicatorValue
    session = db_mod.SessionLocal()
    try:
        ind = EconomicIndicator(
            series_id="USREC",
            name="USREC",
            report_group="Recession",
            units="binary",
            frequency="monthly",
        )
        session.add(ind)
        session.commit()
        for d, v in [
            (date(2008, 12, 1), 1.0),
            (date(2009, 1, 1), 1.0),
            (date(2010, 1, 1), 0.0),  # not a recession month
        ]:
            session.add(IndicatorValue(series_id="USREC", date=d, value=v))
        session.commit()

        from modules.risk_scorecard.backtest import _load_nber_dates
        nber = _load_nber_dates(session)
        assert sorted(nber) == [date(2008, 12, 1), date(2009, 1, 1)]
    finally:
        session.close()


def test_load_nber_dates_empty_when_no_usrec_rows(tmp_path, monkeypatch):
    db_path = tmp_path / "nber_empty.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    import importlib
    from modules.data_storage import database as db_mod
    importlib.reload(db_mod)
    from modules.data_storage import schema  # noqa: F401
    db_mod.init_db()

    session = db_mod.SessionLocal()
    try:
        from modules.risk_scorecard.backtest import _load_nber_dates
        assert _load_nber_dates(session) == []
    finally:
        session.close()
