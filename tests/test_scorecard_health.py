"""Tests for the scorecard input audit."""
import os
import tempfile

import pytest


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


def _seed_indicator(session, series_id, with_value=True):
    from datetime import date
    from modules.data_storage.schema import EconomicIndicator, IndicatorValue

    ind = EconomicIndicator(
        series_id=series_id,
        name=series_id,
        report_group="Test",
        units="",
        frequency="monthly",
    )
    session.add(ind)
    session.commit()
    if with_value:
        session.add(IndicatorValue(
            series_id=series_id,
            date=date(2026, 1, 1),
            value=1.0,
        ))
        session.commit()
    return ind


def test_audit_returns_empty_when_all_present(db_session):
    from modules.risk_scorecard.health import audit_scorecard_inputs, EXPECTED_SERIES

    for series_ids in EXPECTED_SERIES.values():
        for sid in series_ids:
            _seed_indicator(db_session, sid)

    missing = audit_scorecard_inputs(db_session)
    assert missing == {}


def test_audit_reports_missing_indicator_rows(db_session):
    from modules.risk_scorecard.health import audit_scorecard_inputs

    # Only seed one series; everything else missing.
    _seed_indicator(db_session, "CPIAUCSL")

    missing = audit_scorecard_inputs(db_session)
    assert "inflation" in missing
    assert "PCEPILFE" in missing["inflation"]
    assert "labor" in missing  # all of UNRATE/PAYEMS/etc missing
    assert "housing" in missing


def test_audit_reports_missing_indicator_values(db_session):
    """An indicator row with zero data points should still count as missing —
    the scorecard reads values, not just registration."""
    from modules.risk_scorecard.health import audit_scorecard_inputs

    _seed_indicator(db_session, "HOUST", with_value=False)
    _seed_indicator(db_session, "PERMIT", with_value=True)

    missing = audit_scorecard_inputs(db_session)
    assert "housing" in missing
    assert missing["housing"] == ["HOUST"]
