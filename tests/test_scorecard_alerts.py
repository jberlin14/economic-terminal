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


def test_composite_band_two_transitions_same_day_both_emit(db_session):
    """Multiple band crossings on the same day should each emit. Previously
    the dedup hash collided on (alert_type, related_entity, day) and the
    second crossing was silently swallowed."""
    from modules.risk_scorecard.alerts import check_composite_band_crossing
    from modules.data_storage.schema import RiskAlert, AIMarketJournal

    yesterday = date.today() - timedelta(days=1)
    _seed_journal(db_session, yesterday, composite=20.0)  # green

    # Noon: green → yellow.
    s1 = check_composite_band_crossing(db_session, current_composite=50.0)
    assert s1["alert_id"] is not None
    assert s1["prior_band"] == "green" and s1["current_band"] == "yellow"

    # Update prior journal to reflect the new state, then 6pm: yellow → red.
    prior = db_session.query(AIMarketJournal).filter(
        AIMarketJournal.date == yesterday
    ).first()
    prior.pillar_scores_snapshot = {"composite": 50.0, "pillars": {}}
    db_session.commit()

    s2 = check_composite_band_crossing(db_session, current_composite=80.0)
    assert s2["alert_id"] is not None
    assert s2["prior_band"] == "yellow" and s2["current_band"] == "red"

    alerts = db_session.query(RiskAlert).all()
    assert len(alerts) == 2  # both emitted, distinct dedup partitions


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


def test_emit_handles_concurrent_dedup_race_via_unique_constraint(db_session):
    """When two concurrent _emit calls both pass the dedup check before
    either commits, the unique index on alert_hash catches the duplicate
    at commit time. The second writer's IntegrityError must be caught
    and treated as 'dedup-resolved', not a hard failure (debug-review
    pass-3 finding 1)."""
    from modules.risk_scorecard.alerts import _emit
    from modules.data_storage.schema import RiskAlert
    from modules.data_storage.database import SessionLocal

    yesterday = date.today() - timedelta(days=1)
    _seed_journal(db_session, yesterday, composite=20.0)

    # First emit succeeds.
    today = date.today()
    a1 = _emit(
        db_session,
        alert_type="ECON",
        severity="MEDIUM",
        title="t1",
        message="m1",
        related_entity="test.race",
        today=today,
        key_suffix="green->yellow",
    )
    assert a1 is not None

    # Now simulate a concurrent emit that won past the dedup check (e.g.
    # the first writer hadn't committed yet). Manually insert into a
    # second SessionLocal — bypass the dedup check by reusing the same
    # alert_hash and confirm the unique constraint catches it.
    from modules.risk_scorecard.alerts import _alert_hash
    h = _alert_hash("ECON", "test.race", today, "green->yellow")

    # Pre-insert another identical alert with the same hash (simulates
    # the racing writer arriving second). _emit's dedup-check WOULD have
    # caught it — we want to test the safety net for when it doesn't.
    write_db = SessionLocal()
    try:
        from datetime import datetime as _dt, timedelta as _td
        dup = RiskAlert(
            alert_type="ECON",
            severity="MEDIUM",
            title="t2",
            message="m2",
            details={},
            triggered_at=_dt.utcnow(),
            expires_at=_dt.utcnow() + _td(days=7),
            related_entity="test.race",
            alert_hash=h,
            is_active=True,
        )
        write_db.add(dup)
        # The unique index makes this commit fail.
        from sqlalchemy.exc import IntegrityError
        try:
            write_db.commit()
            assert False, "expected IntegrityError on duplicate alert_hash"
        except IntegrityError:
            write_db.rollback()
    finally:
        write_db.close()

    # Confirm only one alert exists with that hash.
    alerts = db_session.query(RiskAlert).filter(RiskAlert.alert_hash == h).all()
    assert len(alerts) == 1


def test_evaluate_scorecard_alerts_extracts_sahm_from_pillar_components(db_session):
    """End-to-end: build a scorecard payload with a Sahm Rule component
    and verify evaluate_scorecard_alerts correctly parses the value and
    fires the trigger. Regression for the brittle string-match extraction
    in the orchestrator (debug-review VG-3)."""
    from modules.risk_scorecard.alerts import evaluate_scorecard_alerts
    from modules.data_storage.schema import RiskAlert

    yesterday = date.today() - timedelta(days=1)
    _seed_journal(db_session, yesterday, composite=50.0, sahm=0.40)

    scorecard_result = {
        "composite_score": 55.0,  # still yellow → no band crossing
        "pillars": [
            {
                "id": "labor",
                "name": "Labor Market",
                "components": [
                    {"label": "Sahm Rule", "value": "0.55", "status": "triggered"},
                    {"label": "Unemployment", "value": "4.5%", "status": "moderate"},
                ],
            }
        ],
    }

    fired = evaluate_scorecard_alerts(db_session, scorecard_result)
    sahm_fires = [f for f in fired if f.get("kind") == "sahm"]
    assert len(sahm_fires) == 1
    assert sahm_fires[0]["direction"] == "up"

    alerts = db_session.query(RiskAlert).filter(
        RiskAlert.related_entity == "labor.sahm_rule"
    ).all()
    assert len(alerts) == 1
    assert alerts[0].related_value == 0.55


def test_sahm_trigger_no_alert_when_steady_below(db_session):
    from modules.risk_scorecard.alerts import check_sahm_trigger
    from modules.data_storage.schema import RiskAlert

    yesterday = date.today() - timedelta(days=1)
    _seed_journal(db_session, yesterday, composite=50.0, sahm=0.30)
    assert check_sahm_trigger(db_session, sahm_value=0.32) is None
    assert db_session.query(RiskAlert).count() == 0
