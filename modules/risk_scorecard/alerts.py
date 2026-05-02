"""
Threshold-crossing alerts for the macro risk scorecard (Phase 4.4).

Detects three classes of state changes that warrant a notification:

  1. **Composite band crossings** — composite score moves between
     green/yellow/red bands relative to the prior journal entry.
  2. **Drift alert** — recession-model live drift score crosses into
     'warn' or 'alert' level.
  3. **Sahm Rule trigger** — Sahm value moves above 0.50 (recession-level
     labor deterioration), or back below.

Alerts are written into the existing `risk_alerts` table with a hash-based
dedup key so repeated polls during the same day don't re-emit.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from modules.data_storage.schema import AIMarketJournal, RiskAlert


# Band cutoffs match scorecard.py (_color_for_score).
def _band(score: float) -> str:
    if score <= 33:
        return "green"
    if score <= 66:
        return "yellow"
    return "red"


def _alert_hash(
    alert_type: str,
    related_entity: str,
    day: date,
    key_suffix: Optional[str] = None,
) -> str:
    """Stable per-day dedup key.

    Same-day repeat polls dedup. A next-day re-trigger emits again because
    the date is part of the key. `key_suffix` further partitions the dedup
    space — used for composite band crossings so that green→yellow at noon
    and yellow→red at 6pm don't collide on a single "scorecard.composite"
    key for the day.
    """
    parts = [alert_type, related_entity, day.isoformat()]
    if key_suffix:
        parts.append(key_suffix)
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _existing_alert(db: Session, alert_hash: str) -> bool:
    return db.query(RiskAlert).filter(RiskAlert.alert_hash == alert_hash).first() is not None


def _emit(
    db: Session,
    alert_type: str,
    severity: str,
    title: str,
    message: str,
    related_entity: str,
    related_value: Optional[float] = None,
    threshold_value: Optional[float] = None,
    details: Optional[Dict[str, Any]] = None,
    today: Optional[date] = None,
    key_suffix: Optional[str] = None,
) -> Optional[int]:
    """Insert a new alert if no same-day duplicate exists. Returns id or None.

    Dedup check runs against the caller's session (so we see uncommitted
    upstream writes), but the alert insert itself uses a dedicated
    `SessionLocal()` session. Coupling a side-effect commit to the
    request-scoped session would publish any unrelated dirty state on
    that session — same isolation the scorecard's `_persist_pillar_scores`
    applies for its journal write.
    """
    from modules.data_storage.database import SessionLocal

    today = today or date.today()
    h = _alert_hash(alert_type, related_entity, today, key_suffix)
    if _existing_alert(db, h):
        return None
    alert = RiskAlert(
        alert_type=alert_type,
        severity=severity,
        title=title,
        message=message,
        details=details or {},
        triggered_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=7),
        related_entity=related_entity,
        related_value=related_value,
        threshold_value=threshold_value,
        alert_hash=h,
        is_active=True,
    )
    write_db = SessionLocal()
    try:
        write_db.add(alert)
        write_db.commit()
        write_db.refresh(alert)
        return alert.id
    except Exception:
        write_db.rollback()
        raise
    finally:
        write_db.close()


def check_composite_band_crossing(
    db: Session,
    current_composite: float,
    today: Optional[date] = None,
) -> Optional[Dict[str, Any]]:
    """
    Detect a band change vs the prior journal entry's composite.

    Returns a summary dict if an alert was emitted (including dedup case
    where it's noted but not duplicated), else None.
    """
    today = today or date.today()
    prior = (
        db.query(AIMarketJournal)
        .filter(AIMarketJournal.date < today)
        .order_by(AIMarketJournal.date.desc())
        .first()
    )
    if not prior:
        return None
    prior_snap = prior.pillar_scores_snapshot or {}
    prior_composite = prior_snap.get("composite") if isinstance(prior_snap, dict) else None
    if prior_composite is None:
        return None

    prior_band = _band(float(prior_composite))
    current_band = _band(current_composite)
    if prior_band == current_band:
        return None

    # Severity mapping by destination band.
    severity = {"green": "MEDIUM", "yellow": "HIGH", "red": "CRITICAL"}.get(current_band, "MEDIUM")
    direction = "up" if current_composite > prior_composite else "down"
    title = f"Macro composite crossed {prior_band.upper()} → {current_band.upper()}"
    message = (
        f"Composite risk score moved from {prior_composite:.1f} ({prior_band}) "
        f"to {current_composite:.1f} ({current_band}) — risk shifted {direction}."
    )
    alert_id = _emit(
        db,
        alert_type="ECON",
        severity=severity,
        title=title,
        message=message,
        related_entity="risk_scorecard.composite",
        related_value=current_composite,
        threshold_value=33.0 if current_band == "green" else (66.0 if current_band == "yellow" else 67.0),
        details={"prior_band": prior_band, "current_band": current_band, "prior_composite": prior_composite},
        today=today,
        # Distinct dedup partitions per band transition so a green→yellow
        # crossing at noon doesn't suppress yellow→red at 6pm same day.
        key_suffix=f"{prior_band}->{current_band}",
    )
    return {
        "alert_id": alert_id,
        "duplicate": alert_id is None,
        "prior_band": prior_band,
        "current_band": current_band,
    }


def check_drift_alert(
    db: Session,
    drift: Dict[str, Any],
    today: Optional[date] = None,
) -> Optional[Dict[str, Any]]:
    """Emit an alert if the recession model's drift level is warn or alert."""
    if not drift:
        return None
    level = drift.get("level")
    if level not in ("warn", "alert"):
        return None
    score = drift.get("drift_score")
    n_oob = drift.get("n_out_of_bounds", 0)
    severity = "HIGH" if level == "alert" else "MEDIUM"
    title = f"Recession model drift: {level.upper()}"
    message = (
        f"Live feature snapshot is {level} relative to training distribution "
        f"(score={score}, {n_oob} feature(s) outside [P01, P99])."
    )
    alert_id = _emit(
        db,
        alert_type="ECON",
        severity=severity,
        title=title,
        message=message,
        related_entity="recession_model.drift",
        related_value=float(score) if score is not None else None,
        threshold_value=0.30 if level == "warn" else 0.50,
        details={"level": level, "n_out_of_bounds": n_oob},
        today=today,
    )
    return {"alert_id": alert_id, "duplicate": alert_id is None, "level": level}


def check_sahm_trigger(
    db: Session,
    sahm_value: Optional[float],
    today: Optional[date] = None,
) -> Optional[Dict[str, Any]]:
    """Emit an alert when the Sahm Rule crosses the 0.50 recession threshold."""
    if sahm_value is None:
        return None
    today = today or date.today()
    prior = (
        db.query(AIMarketJournal)
        .filter(AIMarketJournal.date < today)
        .order_by(AIMarketJournal.date.desc())
        .first()
    )
    prior_sahm: Optional[float] = None
    if prior and prior.indicator_snapshot:
        prior_sahm = (prior.indicator_snapshot.get("derived") or {}).get("sahm_rule")

    crossed_up = sahm_value >= 0.50 and (prior_sahm is None or prior_sahm < 0.50)
    crossed_down = sahm_value < 0.50 and prior_sahm is not None and prior_sahm >= 0.50
    if not (crossed_up or crossed_down):
        return None

    severity = "CRITICAL" if crossed_up else "MEDIUM"
    title = f"Sahm Rule {'TRIGGERED' if crossed_up else 'reset below 0.50'}"
    message = (
        f"Sahm Rule moved from {prior_sahm if prior_sahm is not None else 'n/a'} "
        f"to {sahm_value:.2f} — labor market "
        f"{'recession signal active' if crossed_up else 'no longer in trigger range'}."
    )
    alert_id = _emit(
        db,
        alert_type="ECON",
        severity=severity,
        title=title,
        message=message,
        related_entity="labor.sahm_rule",
        related_value=float(sahm_value),
        threshold_value=0.50,
        details={"prior_sahm": prior_sahm, "direction": "up" if crossed_up else "down"},
        today=today,
    )
    return {"alert_id": alert_id, "duplicate": alert_id is None, "direction": "up" if crossed_up else "down"}


def evaluate_scorecard_alerts(
    db: Session,
    scorecard_result: Dict[str, Any],
    drift: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Run all threshold checks against a freshly-computed scorecard payload.
    Best-effort: any one failure shouldn't break the others.

    Returns a list of summary dicts for emitted (or deduped) alerts.
    """
    fired: List[Dict[str, Any]] = []
    today = date.today()

    try:
        composite = float(scorecard_result.get("composite_score", 0.0))
        crossing = check_composite_band_crossing(db, composite, today=today)
        if crossing:
            fired.append({"kind": "composite_band", **crossing})
    except Exception as e:
        logger.debug(f"Composite band alert check failed: {e}")

    if drift:
        try:
            d = check_drift_alert(db, drift, today=today)
            if d:
                fired.append({"kind": "drift", **d})
        except Exception as e:
            logger.debug(f"Drift alert check failed: {e}")

    try:
        # Sahm rule comes from labor pillar components; pull it from scorecard.
        labor_pillar = next(
            (p for p in scorecard_result.get("pillars", []) if p.get("id") == "labor"),
            None,
        )
        sahm_val: Optional[float] = None
        if labor_pillar:
            for c in labor_pillar.get("components", []):
                if c.get("label") == "Sahm Rule":
                    raw = c.get("value", "")
                    try:
                        sahm_val = float(str(raw).strip())
                    except ValueError:
                        sahm_val = None
                    break
        s = check_sahm_trigger(db, sahm_val, today=today)
        if s:
            fired.append({"kind": "sahm", **s})
    except Exception as e:
        logger.debug(f"Sahm alert check failed: {e}")

    return fired
