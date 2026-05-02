"""
Startup health check: confirm the scorecard's expected indicator series
are present in the local DB. Pillars degrade gracefully when inputs are
missing, but their effective weights silently collapse to whatever's
available — distorting the score relative to the documented methodology.

This audit is fast (a single ORM query per series) and runs at startup
so an operator gets a clear log line if a backfill is overdue.
"""
from __future__ import annotations

from typing import Dict, List

from loguru import logger
from sqlalchemy.orm import Session

# Series the scorecard pillars consume directly. Keep in sync with
# scorecard.py:_score_inflation / _score_labor / _score_housing.
EXPECTED_SERIES: Dict[str, List[str]] = {
    "inflation": ["CPIAUCSL", "PCEPILFE", "PPIACO", "T5YIFR"],
    "labor": ["UNRATE", "PAYEMS", "ICSA", "JTSJOL", "JTSQUR"],
    "housing": ["HOUST", "PERMIT"],
}


def audit_scorecard_inputs(db: Session) -> Dict[str, List[str]]:
    """Return {pillar: [missing_series, ...]} for any expected scorecard
    series that have no rows in `economic_indicators` or no data points
    in `indicator_values`. Logs a warning at WARNING level when anything
    is missing so it surfaces above the normal startup chatter."""
    from modules.data_storage.schema import EconomicIndicator, IndicatorValue

    missing: Dict[str, List[str]] = {}
    for pillar, series_ids in EXPECTED_SERIES.items():
        gaps: List[str] = []
        for sid in series_ids:
            registered = (
                db.query(EconomicIndicator.series_id)
                .filter(EconomicIndicator.series_id == sid)
                .first()
                is not None
            )
            if not registered:
                gaps.append(sid)
                continue
            has_value = (
                db.query(IndicatorValue.id)
                .filter(IndicatorValue.series_id == sid)
                .first()
                is not None
            )
            if not has_value:
                gaps.append(sid)
        if gaps:
            missing[pillar] = gaps

    if missing:
        gap_summary = ", ".join(
            f"{pillar}: {','.join(sids)}" for pillar, sids in missing.items()
        )
        logger.warning(
            "Scorecard inputs missing — pillar weights will collapse to "
            "available series. Run `python scripts/init_indicators.py` to "
            f"backfill. Missing: {gap_summary}"
        )
    else:
        logger.info("Scorecard input audit: all expected series present.")

    return missing
