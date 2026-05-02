"""
Pillar-score snapshot backfill for old journal entries.

When a journal entry was written before scorecard.compute() began
persisting `pillar_scores_snapshot` (Phase 1 §1.4), the back-test panel
and sparkline reader can't see its composite score. This module
reconstructs an approximate pillar snapshot from the legacy
`indicator_snapshot` payload using the same formula the live sparkline
fallback applies, so historical entries become readable without
recomputing the full multi-component scoring.

Two surfaces:
  * `reconstruct_compact_from_indicator_snapshot` — pure helper, used
    by both the live sparkline fallback and the offline backfill.
  * `backfill_pillar_scores_snapshot` — sweep journal entries that lack
    a snapshot and write reconstructed values.

The reconstruction is intentionally lossy: it only fills the four
pillars derivable from `indicator_snapshot` (inflation, labor,
yield_curve, credit) and weights the composite over only those.
Volatility, geopolitical, and housing aren't recoverable from journal
data — their snapshot values stay null.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from modules.data_storage.schema import AIMarketJournal


# Legacy four-pillar weights used by the reconstruction. We renormalize
# over only the four pillars we can derive — see _LEGACY_WEIGHTS_TOTAL.
_LEGACY_WEIGHTS = {
    "inflation": 0.18,
    "labor": 0.18,
    "yield_curve": 0.14,
    "credit": 0.14,
}
_LEGACY_WEIGHTS_TOTAL = sum(_LEGACY_WEIGHTS.values())


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _linear_scale(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return _clamp(((value - low) / (high - low)) * 100.0)


def _color(score: float) -> str:
    if score <= 33:
        return "green"
    if score <= 66:
        return "yellow"
    return "red"


def reconstruct_compact_from_indicator_snapshot(
    snapshot: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Build a compact pillar-snapshot from a legacy `indicator_snapshot`.

    Returns the same shape `RiskScorecard._persist_pillar_scores` writes:
        {
            composite, composite_color, composite_trend,
            pillars: {<id>: {score, color, trend}},
        }
    With `trend` left null and only the four derivable pillars populated.

    Returns None when the snapshot has no usable signals.
    """
    if not isinstance(snapshot, dict) or not snapshot:
        return None

    derived = snapshot.get("derived") or {}
    spreads = (snapshot.get("spreads") or {}) if isinstance(snapshot.get("spreads"), dict) else {}
    cpi_yoy = derived.get("cpi_yoy")
    sahm = derived.get("sahm_rule")
    spread_10y2y = spreads.get("10y2y")
    has_explicit_credit = "credit_stress" in snapshot

    # Skip entries with no useful signal at all — otherwise every empty
    # snapshot would get a default credit=NORMAL pillar and be backfilled
    # with a misleading composite=15.
    if (
        cpi_yoy is None
        and sahm is None
        and spread_10y2y is None
        and not has_explicit_credit
    ):
        return None

    pillars: Dict[str, Dict[str, Any]] = {}

    if cpi_yoy is not None:
        s = round(_linear_scale(float(cpi_yoy), 1.5, 6.0), 1)
        pillars["inflation"] = {"score": s, "color": _color(s), "trend": None}

    if sahm is not None:
        s = round(_linear_scale(float(sahm), 0.0, 0.8), 1)
        pillars["labor"] = {"score": s, "color": _color(s), "trend": None}

    if spread_10y2y is not None:
        s = round(_linear_scale(-float(spread_10y2y), -2.0, 1.0), 1)
        pillars["yield_curve"] = {"score": s, "color": _color(s), "trend": None}

    # Credit pillar: include it whenever there's at least one other
    # signal, defaulting to NORMAL when credit_stress wasn't recorded.
    # This matches the legacy live-sparkline fallback so backfilled
    # composites align with what runtime reconstruction was already
    # producing pre-Phase-1.4.
    stress = snapshot.get("credit_stress") or "NORMAL"
    credit_score = {"NORMAL": 15.0, "ELEVATED": 55.0, "HIGH": 85.0}.get(stress, 40.0)
    pillars["credit"] = {
        "score": credit_score,
        "color": _color(credit_score),
        "trend": None,
    }

    if not pillars:
        return None

    # Renormalize over only the pillars we have so the composite is a
    # weighted mean within the available signal set, not pulled toward
    # zero by missing pillars.
    total_w = sum(_LEGACY_WEIGHTS[p] for p in pillars if p in _LEGACY_WEIGHTS)
    if total_w <= 0:
        return None
    composite = round(
        sum(pillars[p]["score"] * _LEGACY_WEIGHTS[p] for p in pillars if p in _LEGACY_WEIGHTS)
        / total_w,
        1,
    )

    return {
        "composite": composite,
        "composite_color": _color(composite),
        "composite_trend": None,
        "pillars": pillars,
        "_reconstructed": True,
    }


def backfill_pillar_scores_snapshot(
    db: Session,
    dry_run: bool = False,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Sweep journal entries and reconstruct missing pillar snapshots.

    Args:
        db: SQLAlchemy session.
        dry_run: when True, no writes are committed.
        overwrite: when True, re-runs reconstruction for entries that
            already have a `_reconstructed` snapshot. Live snapshots
            (no `_reconstructed` flag) are never overwritten.

    Returns a counts dict: scanned / filled / skipped_existing /
    skipped_no_data / committed.
    """
    entries = db.query(AIMarketJournal).order_by(AIMarketJournal.date.asc()).all()

    scanned = len(entries)
    filled = 0
    skipped_existing = 0
    skipped_no_data = 0

    for entry in entries:
        existing = entry.pillar_scores_snapshot or {}
        if existing and not (overwrite and existing.get("_reconstructed")):
            skipped_existing += 1
            continue

        compact = reconstruct_compact_from_indicator_snapshot(entry.indicator_snapshot)
        if compact is None:
            skipped_no_data += 1
            continue

        entry.pillar_scores_snapshot = compact
        filled += 1

    if dry_run:
        # The caller may pass a session managed by `get_db_context()` (or
        # FastAPI's `Depends(get_db)`) which auto-commits on clean exit —
        # if we don't roll back here, dirtied entries get committed
        # despite the dry-run flag. Expunge to clear identity-map state too.
        db.rollback()
    elif filled > 0:
        db.commit()

    return {
        "scanned": scanned,
        "filled": filled,
        "skipped_existing": skipped_existing,
        "skipped_no_data": skipped_no_data,
        "committed": (not dry_run) and filled > 0,
    }
