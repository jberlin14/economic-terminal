"""
Scorecard composite cutoff back-test (Phase 2 §2.6).

Replays the scorecard composite score over historical journal snapshots
(or, when available, recession-model OOF features) and scores each
candidate cutoff (50, 60, 67) against NBER recession dates within a
configurable look-ahead window.

Used to validate that the published green/yellow/red bands are calibrated
against actual recession outcomes, not intuited.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from loguru import logger
from sqlalchemy.orm import Session

from modules.data_storage.schema import AIMarketJournal


# Look-ahead window in days. NBER calls a recession "near in time" if the
# composite spike preceded the recession start by at most this many days.
DEFAULT_LOOKAHEAD_DAYS = 365


def _is_recession_within(
    snapshot_date: date,
    nber_dates: List[date],
    lookahead_days: int = DEFAULT_LOOKAHEAD_DAYS,
) -> bool:
    """True if any NBER recession-month falls within `lookahead_days` after
    the snapshot date."""
    end = snapshot_date + timedelta(days=lookahead_days)
    return any(snapshot_date <= d <= end for d in nber_dates)


def backtest_composite_cutoff(
    db: Session,
    cutoffs: Tuple[float, ...] = (50.0, 60.0, 67.0),
    nber_dates: Optional[List[date]] = None,
    lookahead_days: int = DEFAULT_LOOKAHEAD_DAYS,
) -> Dict[str, Any]:
    """
    Score each cutoff by precision/recall against NBER outcomes.

    For each (snapshot_date, composite_score) pair in the journal:
      label = 1 if any NBER recession month falls within `lookahead_days`
              after the snapshot, else 0.
    Then for each cutoff threshold, compute:
      precision = TP / (TP + FP)
      recall    = TP / (TP + FN)
      f1        = 2 * P * R / (P + R)

    Args:
        db: SQLAlchemy session for the journal table.
        cutoffs: thresholds to evaluate. The current default banding maps
            green ≤ 33, yellow 34–66, red ≥ 67.
        nber_dates: optional explicit list of NBER recession-month dates.
            When None, reads USREC from `indicator_values` table if
            available; otherwise returns an empty result.
        lookahead_days: how far forward to look for an NBER outcome.

    Returns:
        {
            "cutoffs": [{cutoff, precision, recall, f1, n_pos_pred, n_total}],
            "n_snapshots": int,
            "n_positive_outcomes": int,
            "lookahead_days": int,
        }
    """
    entries = db.query(AIMarketJournal).order_by(AIMarketJournal.date.asc()).all()
    if not entries:
        return {
            "cutoffs": [],
            "n_snapshots": 0,
            "n_positive_outcomes": 0,
            "lookahead_days": lookahead_days,
            "note": "No journal entries available — backtest skipped.",
        }

    # Pull composite scores from the stored pillar_scores_snapshot column.
    rows: List[Tuple[date, float]] = []
    for e in entries:
        snap = e.pillar_scores_snapshot or {}
        composite = snap.get("composite") if isinstance(snap, dict) else None
        if composite is not None:
            rows.append((e.date, float(composite)))
    if not rows:
        return {
            "cutoffs": [],
            "n_snapshots": 0,
            "n_positive_outcomes": 0,
            "lookahead_days": lookahead_days,
            "note": "No journal entries with composite_score available — backtest skipped.",
        }

    # Resolve NBER dates if not provided.
    if nber_dates is None:
        nber_dates = _load_nber_dates(db)
    if not nber_dates:
        return {
            "cutoffs": [],
            "n_snapshots": len(rows),
            "n_positive_outcomes": 0,
            "lookahead_days": lookahead_days,
            "note": (
                "No NBER recession dates available locally. Populate USREC "
                "in indicator_values or pass nber_dates explicitly."
            ),
        }

    snapshot_dates = np.array([d for d, _ in rows])
    composites = np.array([s for _, s in rows], dtype=float)
    labels = np.array([
        _is_recession_within(d, nber_dates, lookahead_days)
        for d in snapshot_dates
    ], dtype=bool)

    n_pos = int(labels.sum())

    out = []
    for c in cutoffs:
        pred = composites >= c
        tp = int(np.sum(pred & labels))
        fp = int(np.sum(pred & ~labels))
        fn = int(np.sum(~pred & labels))
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        out.append({
            "cutoff": float(c),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "n_positive_predictions": int(pred.sum()),
            "n_true_positives": tp,
            "n_total": len(rows),
        })

    return {
        "cutoffs": out,
        "n_snapshots": len(rows),
        "n_positive_outcomes": n_pos,
        "lookahead_days": lookahead_days,
    }


def _load_nber_dates(db: Session) -> List[date]:
    """Best-effort: pull USREC=1 dates from indicator_values if present."""
    try:
        from modules.data_storage.schema import IndicatorValue, EconomicIndicator

        usrec = db.query(EconomicIndicator).filter(
            EconomicIndicator.series_id == "USREC"
        ).first()
        if not usrec:
            return []
        rows = db.query(IndicatorValue).filter(
            IndicatorValue.indicator_id == usrec.id,
            IndicatorValue.value == 1.0,
        ).all()
        return [r.date for r in rows if r.date is not None]
    except Exception as e:
        logger.debug(f"Could not load USREC from indicator_values: {e}")
        return []
