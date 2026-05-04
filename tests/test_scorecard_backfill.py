"""Tests for the pillar_scores_snapshot reconstruction + sweep."""
import os
import tempfile
from datetime import date, timedelta

import pytest

from modules.risk_scorecard.backfill import (
    reconstruct_compact_from_indicator_snapshot,
)


# ──────────────────────────────────────────────
# reconstruct_compact_from_indicator_snapshot — pure helper
# ──────────────────────────────────────────────

def test_reconstruct_returns_none_for_empty_snapshot():
    assert reconstruct_compact_from_indicator_snapshot(None) is None
    assert reconstruct_compact_from_indicator_snapshot({}) is None


def test_reconstruct_with_full_signals():
    snapshot = {
        "derived": {"cpi_yoy": 3.5, "sahm_rule": 0.40},
        "spreads": {"10y2y": -0.20},
        "credit_stress": "ELEVATED",
    }
    out = reconstruct_compact_from_indicator_snapshot(snapshot)
    assert out is not None
    pillars = out["pillars"]
    assert set(pillars) == {"inflation", "labor", "yield_curve", "credit"}
    assert pillars["inflation"]["score"] == pytest.approx(44.4, abs=0.5)
    assert pillars["labor"]["score"] == pytest.approx(50.0, abs=0.5)
    assert pillars["credit"]["score"] == 55.0
    # composite is renormalized over the four available pillars
    assert 0 <= out["composite"] <= 100
    assert out["_reconstructed"] is True


def test_reconstruct_with_partial_signals():
    """Missing signals → renormalize over what's available.

    Credit pillar always materializes (defaulting to NORMAL) whenever any
    other signal is present, matching the legacy live-sparkline fallback.
    """
    snapshot = {"derived": {"cpi_yoy": 3.0}}  # only CPI
    out = reconstruct_compact_from_indicator_snapshot(snapshot)
    assert out is not None
    assert set(out["pillars"]) == {"inflation", "credit"}
    # Credit defaulted to NORMAL → 15.
    assert out["pillars"]["credit"]["score"] == 15.0


def test_reconstruct_returns_none_when_no_signals():
    """No usable signal at all → None (don't backfill empty entries with
    a default credit=NORMAL)."""
    snapshot = {"derived": {}, "spreads": {}}
    assert reconstruct_compact_from_indicator_snapshot(snapshot) is None


def test_reconstruct_credit_stress_implicit_default():
    """credit_stress missing but other signals present → credit defaults
    to NORMAL (legacy parity)."""
    snapshot = {"derived": {"cpi_yoy": 3.0}}
    out = reconstruct_compact_from_indicator_snapshot(snapshot)
    assert out is not None
    assert out["pillars"]["credit"]["score"] == 15.0


# ──────────────────────────────────────────────
# backfill_pillar_scores_snapshot — DB sweep
# ──────────────────────────────────────────────

@pytest.fixture
def db_session(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    import importlib
    from modules.data_storage import database as db_mod
    importlib.reload(db_mod)
    from modules.data_storage import schema  # noqa: F401
    db_mod.init_db()
    session = db_mod.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        try:
            os.remove(path)
        except OSError:
            pass


def _seed_journal(session, day, indicator_snapshot=None, pillar_snapshot=None):
    from modules.data_storage.schema import AIMarketJournal
    entry = AIMarketJournal(
        date=day,
        regime="CAUTIOUS",
        key_themes=[],
        narrative_summary="seed",
        indicator_snapshot=indicator_snapshot or {},
        news_themes={},
        pillar_scores_snapshot=pillar_snapshot,
    )
    session.add(entry)
    session.commit()
    return entry


def test_backfill_fills_missing_snapshots(db_session):
    from modules.risk_scorecard.backfill import backfill_pillar_scores_snapshot

    today = date.today()
    _seed_journal(
        db_session,
        today - timedelta(days=2),
        indicator_snapshot={
            "derived": {"cpi_yoy": 3.0, "sahm_rule": 0.30},
            "spreads": {"10y2y": 0.10},
            "credit_stress": "NORMAL",
        },
    )
    _seed_journal(
        db_session,
        today - timedelta(days=1),
        indicator_snapshot={"derived": {"cpi_yoy": 4.5}},  # partial
    )

    report = backfill_pillar_scores_snapshot(db_session)
    assert report["scanned"] == 2
    assert report["filled"] == 2
    assert report["skipped_existing"] == 0
    assert report["skipped_no_data"] == 0
    assert report["committed"] is True

    from modules.data_storage.schema import AIMarketJournal
    entries = db_session.query(AIMarketJournal).all()
    assert all(e.pillar_scores_snapshot is not None for e in entries)
    assert all(e.pillar_scores_snapshot.get("_reconstructed") for e in entries)


def test_backfill_does_not_overwrite_live_snapshots(db_session):
    from modules.risk_scorecard.backfill import backfill_pillar_scores_snapshot

    today = date.today()
    # Live (non-reconstructed) snapshot.
    live = {"composite": 42.0, "pillars": {"inflation": {"score": 50.0}}}
    _seed_journal(
        db_session,
        today - timedelta(days=1),
        indicator_snapshot={"derived": {"cpi_yoy": 9.0}},
        pillar_snapshot=live,
    )

    report = backfill_pillar_scores_snapshot(db_session, overwrite=True)
    assert report["filled"] == 0
    assert report["skipped_existing"] == 1

    from modules.data_storage.schema import AIMarketJournal
    entry = db_session.query(AIMarketJournal).first()
    assert entry.pillar_scores_snapshot == live  # untouched


def test_backfill_overwrite_replays_reconstructed_snapshots(db_session):
    from modules.risk_scorecard.backfill import backfill_pillar_scores_snapshot

    today = date.today()
    # Reconstructed snapshot from a previous run.
    old_recon = {
        "composite": 50.0,
        "pillars": {},
        "_reconstructed": True,
    }
    _seed_journal(
        db_session,
        today - timedelta(days=1),
        indicator_snapshot={"derived": {"cpi_yoy": 4.0, "sahm_rule": 0.4}},
        pillar_snapshot=old_recon,
    )

    report = backfill_pillar_scores_snapshot(db_session, overwrite=True)
    assert report["filled"] == 1

    from modules.data_storage.schema import AIMarketJournal
    entry = db_session.query(AIMarketJournal).first()
    # The new compact has actual pillars, not empty.
    assert entry.pillar_scores_snapshot["pillars"]


def test_backfill_dry_run_does_not_commit(db_session):
    """Dry-run rolls back any dirtied state so a context-managed session
    that auto-commits on clean exit doesn't accidentally publish the
    reconstruction. Regression for the bug where dry-run reported
    committed=False but get_db_context still committed the changes."""
    from modules.risk_scorecard.backfill import backfill_pillar_scores_snapshot

    today = date.today()
    _seed_journal(
        db_session,
        today - timedelta(days=1),
        indicator_snapshot={"derived": {"cpi_yoy": 3.0}},
    )

    report = backfill_pillar_scores_snapshot(db_session, dry_run=True)
    assert report["filled"] == 1
    assert report["committed"] is False

    # Simulate the get_db_context auto-commit-on-exit path: any dirtied
    # state must NOT be flushed to disk after the function returns.
    db_session.commit()
    db_session.expire_all()
    from modules.data_storage.schema import AIMarketJournal
    entry = db_session.query(AIMarketJournal).first()
    assert entry.pillar_scores_snapshot is None


def test_backfill_dry_run_through_get_db_context_does_not_persist(db_session, monkeypatch):
    """End-to-end via get_db_context's auto-commit: dry-run dirties the
    session, the context manager would commit on clean exit, and the
    rollback in backfill_pillar_scores_snapshot must defeat that."""
    from modules.risk_scorecard.backfill import backfill_pillar_scores_snapshot
    from modules.data_storage import database as db_mod
    from modules.data_storage.schema import AIMarketJournal

    today = date.today()
    _seed_journal(
        db_session,
        today - timedelta(days=1),
        indicator_snapshot={"derived": {"cpi_yoy": 3.0}},
    )
    db_session.close()

    # Now call through get_db_context — exits cleanly, would auto-commit.
    with db_mod.get_db_context() as ctx_db:
        report = backfill_pillar_scores_snapshot(ctx_db, dry_run=True)
        assert report["filled"] == 1
        assert report["committed"] is False

    # Re-open session and verify nothing was committed.
    fresh = db_mod.SessionLocal()
    try:
        entry = fresh.query(AIMarketJournal).first()
        assert entry.pillar_scores_snapshot is None
    finally:
        fresh.close()


def test_backfill_skips_no_data_entries(db_session):
    from modules.risk_scorecard.backfill import backfill_pillar_scores_snapshot

    today = date.today()
    _seed_journal(
        db_session,
        today - timedelta(days=1),
        indicator_snapshot={"derived": {}},  # no usable signals
    )

    report = backfill_pillar_scores_snapshot(db_session)
    assert report["filled"] == 0
    assert report["skipped_no_data"] == 1
