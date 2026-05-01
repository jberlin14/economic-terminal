"""Tests for scorecard threshold-crossing alerts (Phase 4.4)."""
import os
import tempfile
from datetime import date, datetime, timedelta

import pytest


@pytest.fixture
def db_session(monkeypatch):
    """Spin up an isolated SQLite DB for the duration of a test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")

    # Re-import database module under the patched env var.
    import importlib

    from modules.data_storage import database as db_mod
    importlib.reload(db_mod)
    from modules.data_storage import schema  # noqa: F401  (registers tables)
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


def _seed_journal(session, day: date, composite: float = 50.0, sahm: float | None = None):
    from modules.data_storage.schema import AIMarketJournal

    snapshot = {"derived": {}}
    if sahm is not None:
        snapshot["derived"]["sahm_rule"] = sahm

    entry = AIMarketJournal(
        date=day,
        regime="CAUTIOUS",
        key_themes=[],
        narrative_summary="seed",
        indicator_snapshot=snapshot,
        news_themes={},
        pillar_scores_snapshot={"composite": composite, "pillars": {}},
    )
    session.add(entry)
    session.commit()
    return entry


def test_composite_band_crossing_emits_alert(db_session):
    from modules.risk_scorecard.alerts import check_composite_band_crossing
    from modules.data_storage.schema import RiskAlert

    yesterday = date.today() - timedelta(days=1)
    _seed_journal(db_session, yesterday, composite=20.0)  # green

    summary = check_composite_band_crossing(db_session, current_composite=70.0)  # red
    assert summary is not None
    assert summary["prior_band"] == "green"
    assert summary["current_band"] == "red"

    alerts = db_session.query(RiskAlert).all()
    assert len(alerts) == 1
    assert "GREEN" in alerts[0].title and "RED" in alerts[0].title
    assert alerts[0].severity == "CRITICAL"


def test_composite_band_crossing_dedups_same_day(db_session):
    from modules.risk_scorecard.alerts import check_composite_band_crossing
    from modules.data_storage.schema import RiskAlert

    yesterday = date.today() - timedelta(days=1)
    _seed_journal(db_session, yesterday, composite=20.0)

    s1 = check_composite_band_crossing(db_session, current_composite=70.0)
    s2 = check_composite_band_crossing(db_session, current_composite=70.0)
    assert s1["alert_id"] is not None
    assert s2["duplicate"] is True
    alerts = db_session.query(RiskAlert).all()
    assert len(alerts) == 1


def test_composite_band_no_change_no_alert(db_session):
    from modules.risk_scorecard.alerts import check_composite_band_crossing
    from modules.data_storage.schema import RiskAlert

    yesterday = date.today() - timedelta(days=1)
    _seed_journal(db_session, yesterday, composite=50.0)  # yellow

    summary = check_composite_band_crossing(db_session, current_composite=55.0)  # still yellow
    assert summary is None
    assert db_session.query(RiskAlert).count() == 0


def test_composite_band_no_prior_journal_no_alert(db_session):
    from modules.risk_scorecard.alerts import check_composite_band_crossing
    summary = check_composite_band_crossing(db_session, current_composite=70.0)
    assert summary is None


def test_drift_alert_emits_when_level_warn_or_alert(db_session):
    from modules.risk_scorecard.alerts import check_drift_alert
    from modules.data_storage.schema import RiskAlert

    summary = check_drift_alert(db_session, {"level": "alert", "drift_score": 0.55, "n_out_of_bounds": 3})
    assert summary is not None
    alerts = db_session.query(RiskAlert).all()
    assert len(alerts) == 1
    assert alerts[0].severity == "HIGH"


def test_drift_alert_skipped_when_ok(db_session):
    from modules.risk_scorecard.alerts import check_drift_alert
    from modules.data_storage.schema import RiskAlert

    summary = check_drift_alert(db_session, {"level": "ok", "drift_score": 0.10})
    assert summary is None
    assert db_session.query(RiskAlert).count() == 0


def test_sahm_trigger_emits_when_crossing_up(db_session):
    from modules.risk_scorecard.alerts import check_sahm_trigger
    from modules.data_storage.schema import RiskAlert

    yesterday = date.today() - timedelta(days=1)
    _seed_journal(db_session, yesterday, composite=50.0, sahm=0.40)

    summary = check_sahm_trigger(db_session, sahm_value=0.55)
    assert summary is not None
    assert summary["direction"] == "up"
    alerts = db_session.query(RiskAlert).all()
    assert len(alerts) == 1
    assert alerts[0].severity == "CRITICAL"


def test_sahm_trigger_no_alert_when_steady_below(db_session):
    from modules.risk_scorecard.alerts import check_sahm_trigger
    from modules.data_storage.schema import RiskAlert

    yesterday = date.today() - timedelta(days=1)
    _seed_journal(db_session, yesterday, composite=50.0, sahm=0.30)
    assert check_sahm_trigger(db_session, sahm_value=0.32) is None
    assert db_session.query(RiskAlert).count() == 0
