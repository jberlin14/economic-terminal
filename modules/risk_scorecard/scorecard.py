"""
Macro Risk Scorecard

Computes a composite 0-100 risk score from 6 market-data-driven pillars.
Each pillar is scored independently, then combined via weighted average.

Score interpretation:
  0-33  = GREEN  (low risk)
  34-66 = YELLOW (moderate risk)
  67-100 = RED   (high risk)

No AI required — pure computation from existing analytics pipeline.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import numpy as np
from sqlalchemy.orm import Session
from loguru import logger

from modules.utils.timezone import get_current_time


# Module-level cache for live yfinance pulls (Phase 2 §2.7).
# yfinance hits VIX/oil/gold every scorecard request — at ~3 page loads
# per minute that's 540 outbound requests/hour. A 5-minute TTL cache
# brings that to 36/hour without staleness issues for daily-grained pillars.
_LIVE_DATA_TTL_SECONDS = 300
_live_data_cache: Dict[str, Any] = {
    "data": None,
    "timestamp": 0.0,
}


# ──────────────────────────────────────────────
# Pillar Weights
# ──────────────────────────────────────────────

PILLAR_WEIGHTS = {
    "inflation": 0.18,
    "labor": 0.18,
    "yield_curve": 0.14,
    "credit": 0.14,
    "volatility": 0.12,
    "geopolitical": 0.12,
    "housing": 0.12,  # Phase 3.1: housing leads cycles — added as 7th pillar
}
assert abs(sum(PILLAR_WEIGHTS.values()) - 1.0) < 1e-9, "PILLAR_WEIGHTS must sum to 1"


def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def _linear_scale(value: float, low: float, high: float) -> float:
    """Map value from [low, high] range to [0, 100]. Values outside range are clamped."""
    if high <= low:
        return 0
    return _clamp(((value - low) / (high - low)) * 100)


def _color_for_score(score: float) -> str:
    if score <= 33:
        return "green"
    elif score <= 66:
        return "yellow"
    return "red"


def _compute_pillar_deltas(
    current_score: float,
    historical_series: List[Optional[float]],
) -> Dict[str, Optional[float]]:
    """
    Phase 3.6: Compute 1D / 1W / 1M deltas for a pillar.

    `historical_series` is the chronologically ordered sparkline (oldest first)
    of past pillar scores from the journal. The "current" score is appended
    notionally at the tail; deltas are taken against:
      - 1D: previous journal entry (sparkline[-1])
      - 1W: ~7 entries back
      - 1M: ~30 entries back (or the oldest available)

    Returns delta values (current - past) so positive = risk worsened.
    Missing positions yield None.
    """
    valid = [v for v in historical_series if v is not None]
    out: Dict[str, Optional[float]] = {"d1": None, "w1": None, "m1": None}
    if not valid:
        return out

    def _safe_delta(past: Optional[float]) -> Optional[float]:
        return round(current_score - past, 1) if past is not None else None

    # 1D: most-recent previous entry
    out["d1"] = _safe_delta(valid[-1])

    # 1W: ~7 entries back
    if len(valid) >= 7:
        out["w1"] = _safe_delta(valid[-7])
    elif valid:
        out["w1"] = _safe_delta(valid[0])

    # 1M: ~30 entries back, or oldest if shorter
    if len(valid) >= 30:
        out["m1"] = _safe_delta(valid[-30])
    elif valid:
        out["m1"] = _safe_delta(valid[0])

    return out


def _freshness_badge(data_freshness: Optional[str]) -> Dict[str, Any]:
    """
    Phase 3.7: Map a data-freshness date string to a UI freshness badge.

    Returns:
        {age_days, level, label}
        level ∈ {'fresh', 'aging', 'stale'}
    """
    if not data_freshness:
        return {"age_days": None, "level": "unknown", "label": "no date"}
    try:
        # Accept both YYYY-MM-DD and ISO datetime strings.
        d = data_freshness[:10]
        dt = datetime.strptime(d, "%Y-%m-%d").date()
        today = get_current_time().date()
        age = (today - dt).days
        if age < 0:
            age = 0
        if age <= 14:
            level, label = "fresh", "fresh"
        elif age <= 45:
            level, label = "aging", f"{age}d old"
        else:
            level, label = "stale", f"{age}d stale"
        return {"age_days": int(age), "level": level, "label": label}
    except Exception:
        return {"age_days": None, "level": "unknown", "label": "unparseable"}


def _trend_from_series(values: List[Optional[float]], delta_threshold: float = 3.0) -> str:
    """
    Classify a short score series as improving / deteriorating / stable.

    Risk pillars are 0-100 where higher = worse. So a series moving UP =
    risk DETERIORATING, moving DOWN = risk IMPROVING.

    Compares the mean of the most-recent 3 entries to the mean of the
    oldest 3. None values are skipped. Returns 'stable' if either window
    is empty or the absolute delta is below `delta_threshold` points.
    """
    cleaned = [float(v) for v in values if v is not None]
    if len(cleaned) < 2:
        return "stable"
    n = min(3, len(cleaned))
    recent = cleaned[-n:]
    older = cleaned[:n]
    diff = (sum(recent) / len(recent)) - (sum(older) / len(older))
    if diff > delta_threshold:
        return "deteriorating"
    if diff < -delta_threshold:
        return "improving"
    return "stable"


class RiskScorecard:
    """Computes composite macro risk scorecard from market data."""

    def __init__(self, db: Session):
        self.db = db

    def compute(self) -> Dict[str, Any]:
        """Main entry point. Returns full scorecard with all pillars."""
        start = time.time()

        from modules.market_summary.analytics_engine import (
            gather_market_context,
            compute_analytics,
        )

        context = gather_market_context(self.db)
        analytics = compute_analytics(context, self.db)

        # Fetch live equity/VIX/commodity data
        live_data = self._fetch_live_data()

        # Compute each pillar
        pillars = []
        pillar_scores = {}

        inflation = self._score_inflation(context, analytics)
        pillars.append(inflation)
        pillar_scores["inflation"] = inflation["score"]

        labor = self._score_labor(context, analytics)
        pillars.append(labor)
        pillar_scores["labor"] = labor["score"]

        curve = self._score_yield_curve(context, analytics)
        pillars.append(curve)
        pillar_scores["yield_curve"] = curve["score"]

        credit = self._score_credit(context, analytics)
        pillars.append(credit)
        pillar_scores["credit"] = credit["score"]

        vol = self._score_volatility(live_data)
        pillars.append(vol)
        pillar_scores["volatility"] = vol["score"]

        geo = self._score_geopolitical(context, analytics, live_data)
        pillars.append(geo)
        pillar_scores["geopolitical"] = geo["score"]

        housing = self._score_housing(context, analytics)
        pillars.append(housing)
        pillar_scores["housing"] = housing["score"]

        # Composite
        composite = sum(
            pillar_scores[k] * PILLAR_WEIGHTS[k] for k in PILLAR_WEIGHTS
        )
        composite = round(composite, 1)

        # Historical sparklines from journal
        sparkline_data = self._get_historical_sparklines()

        # Determine composite trend from sparklines
        composite_series = [s.get("composite") for s in sparkline_data] if sparkline_data else []
        composite_trend = _trend_from_series(composite_series)

        # Attach sparkline data + sparkline-derived trend to pillars.
        # For pillars that hard-code "stable" (credit / volatility /
        # geopolitical), override with the sparkline-derived trend so the
        # arrows reflect actual movement (Phase 1 §1.5). Pillars that
        # derive their own meaningful trend from indicator dynamics
        # (inflation, labor, yield curve) keep their existing label.
        # Also computes 1D/1W/1M deltas per pillar (Phase 3.6).
        SPARKLINE_OVERRIDE_PILLARS = {"credit", "volatility", "geopolitical", "housing"}
        for pillar in pillars:
            pid = pillar["id"]
            pillar_series = [s.get(pid) for s in sparkline_data] if sparkline_data else []
            pillar["sparkline"] = [
                v if v is not None else pillar["score"]
                for v in pillar_series
            ] if pillar_series else [pillar["score"]]
            if pid in SPARKLINE_OVERRIDE_PILLARS:
                pillar["trend"] = _trend_from_series(pillar_series)
            pillar["deltas"] = _compute_pillar_deltas(pillar["score"], pillar_series)
            pillar["freshness"] = _freshness_badge(pillar.get("data_freshness"))

        elapsed = int((time.time() - start) * 1000)

        result = {
            "composite_score": composite,
            "composite_color": _color_for_score(composite),
            "composite_trend": composite_trend,
            "pillars": pillars,
            "sparkline_dates": [s["date"] for s in sparkline_data] if sparkline_data else [],
            "composite_sparkline": [s["composite"] for s in sparkline_data] if sparkline_data else [composite],
            "recession_ml": self._fetch_recession_ml(),
            "assessed_at": get_current_time().isoformat(),
            "elapsed_ms": elapsed,
        }

        # Persist today's pillar scores to the journal so the sparkline reads
        # historical values that match live multi-component scoring (Phase 1
        # §1.4). Best-effort: never let a journal write break the API response.
        try:
            self._persist_pillar_scores(result)
        except Exception as e:
            logger.debug(f"Pillar scores persistence skipped: {e}")

        # Phase 4.4: emit alerts on band crossings, drift, and Sahm trigger.
        # Best-effort; alert evaluation never breaks the API response.
        try:
            from .alerts import evaluate_scorecard_alerts

            drift_payload = None
            ml = result.get("recession_ml")
            if ml is not None:
                # Pull the predictor's drift report if available — same call
                # the dedicated recession page uses, just shared here.
                try:
                    from modules.recession_model.predictor import RecessionPredictor

                    predictor = RecessionPredictor(self.db)
                    full = predictor.get_current_probability()
                    drift_payload = full.get("drift") if isinstance(full, dict) else None
                except Exception:
                    drift_payload = None
            fired = evaluate_scorecard_alerts(self.db, result, drift=drift_payload)
            if fired:
                result["alerts_fired"] = fired
        except Exception as e:
            logger.debug(f"Alert evaluation skipped: {e}")

        return result

    def _persist_pillar_scores(self, result: Dict[str, Any]) -> None:
        """Upsert today's scorecard into the journal's pillar_scores_snapshot column.

        Stores a compact snapshot:
          {
            composite, composite_color, composite_trend,
            pillars: {<id>: {score, color, trend}},
          }
        Trends are included so the sparkline reader can show today's pillar
        trend even if the live derivation drifts vs. the stored snapshot.
        """
        from modules.data_storage.schema import AIMarketJournal

        today = get_current_time().date()
        compact = {
            "composite": result["composite_score"],
            "composite_color": result["composite_color"],
            "composite_trend": result["composite_trend"],
            "pillars": {
                p["id"]: {
                    "score": p["score"],
                    "color": p["color"],
                    "trend": p.get("trend"),
                }
                for p in result["pillars"]
            },
        }

        existing = self.db.query(AIMarketJournal).filter(
            AIMarketJournal.date == today
        ).first()
        if existing:
            existing.pillar_scores_snapshot = compact
            self.db.commit()
            return

        # No journal entry yet for today — create a minimal stub so the
        # sparkline picks up today's value once the journal job runs and
        # fills in the rest. Other fields stay null.
        stub = AIMarketJournal(
            date=today,
            pillar_scores_snapshot=compact,
        )
        self.db.add(stub)
        self.db.commit()

    # ──────────────────────────────────────────
    # Pillar Scorers
    # ──────────────────────────────────────────

    def _score_inflation(self, context: Dict, analytics: Dict) -> Dict:
        """Score inflation risk (0-100).

        Phase 3.2 expansion:
          - CPI YoY (35%) — headline level
          - CPI MoM momentum (15%) — acceleration / deceleration
          - Core PCE YoY (15%) — Fed's preferred measure
          - PPI YoY (15%) — pipeline pressure
          - 5y5y forward inflation (T5YIFR) (20%) — market expectations
        """
        ind_analytics = analytics.get("indicators", {})
        derived = ind_analytics.get("_derived", {})
        indicators = context.get("indicators", {})

        components = []
        scores = []

        # CPI YoY — primary driver
        cpi_yoy = derived.get("cpi_yoy")
        if cpi_yoy is not None:
            # 0 at 1.5%, 50 at 3.5%, 100 at 6.0%
            cpi_score = _linear_scale(cpi_yoy, 1.5, 6.0)
            scores.append(("cpi_yoy", cpi_score, 0.35))
            status = "on target" if cpi_yoy < 2.5 else "elevated" if cpi_yoy < 4.0 else "high"
            components.append({"label": "CPI YoY", "value": f"{cpi_yoy:.1f}%", "status": status})

        # Inflation momentum: compare CPI MoM to assess if inflation is
        # accelerating or decelerating. The raw index trend from the analytics
        # engine is unreliable (it measures level slope, not rate-of-change slope).
        cpi_data = indicators.get("CPIAUCSL", {})
        cpi_mom = cpi_data.get("mom_change_pct")
        inflation_direction = "stable"  # default

        if cpi_mom is not None:
            # MoM > 0.3% annualizes to ~3.6%, suggesting acceleration
            # MoM < 0.15% annualizes to ~1.8%, suggesting deceleration
            if cpi_mom > 0.3:
                mom_score = 70
                inflation_direction = "accelerating"
            elif cpi_mom > 0.2:
                mom_score = 45
                inflation_direction = "stable"
            else:
                mom_score = 15
                inflation_direction = "decelerating"
            scores.append(("cpi_momentum", mom_score, 0.15))
            mom_annualized = cpi_mom * 12
            status = "on target" if mom_annualized < 2.5 else "elevated" if mom_annualized < 4.0 else "high"
            components.append({"label": "CPI MoM", "value": f"{cpi_mom:.2f}%", "status": status})
        else:
            # Fallback: if CPI YoY < 2.5, inflation is under control
            if cpi_yoy is not None:
                if cpi_yoy < 2.5:
                    inflation_direction = "decelerating"
                elif cpi_yoy > 3.5:
                    inflation_direction = "accelerating"

        # Core PCE (Fed's preferred measure)
        core_pce = indicators.get("PCEPILFE", {})
        if core_pce.get("yoy_change_pct") is not None:
            pce_yoy = core_pce["yoy_change_pct"]
            pce_score = _linear_scale(pce_yoy, 1.5, 5.0)
            scores.append(("pce_core", pce_score, 0.15))
            status = "on target" if pce_yoy < 2.5 else "elevated" if pce_yoy < 3.5 else "high"
            components.append({"label": "Core PCE YoY", "value": f"{pce_yoy:.1f}%", "status": status})

        # PPI YoY — pipeline inflation signal (Phase 3.2)
        ppi = indicators.get("PPIACO", {})
        ppi_yoy = ppi.get("yoy_change_pct")
        if ppi_yoy is not None:
            # PPI is more volatile than CPI; band scaled wider.
            ppi_score = _linear_scale(ppi_yoy, 0.0, 8.0)
            scores.append(("ppi_yoy", ppi_score, 0.15))
            status = "tame" if ppi_yoy < 1.5 else "elevated" if ppi_yoy < 4.0 else "high"
            components.append({"label": "PPI YoY", "value": f"{ppi_yoy:+.1f}%", "status": status})

        # 5y5y forward inflation expectations (Phase 3.2). FRED series T5YIFR.
        t5yifr = indicators.get("T5YIFR", {})
        breakeven_5y5y = t5yifr.get("value")
        if breakeven_5y5y is not None:
            # Anchored expectations: 2.0-2.4% target. Above 3% = un-anchored.
            be_score = _linear_scale(breakeven_5y5y, 2.0, 3.5)
            scores.append(("breakeven_5y5y", be_score, 0.20))
            status = (
                "anchored" if breakeven_5y5y < 2.5
                else "drifting" if breakeven_5y5y < 3.0
                else "un-anchored"
            )
            components.append({"label": "5y5y Forward", "value": f"{breakeven_5y5y:.2f}%", "status": status})

        # Weighted average
        if scores:
            total_weight = sum(w for _, _, w in scores)
            score = sum(s * w for _, s, w in scores) / total_weight
        else:
            score = 50  # no data = moderate risk

        data_date = indicators.get("CPIAUCSL", {}).get("date")

        # Map inflation direction to risk trend
        risk_trend = {
            "decelerating": "improving",
            "accelerating": "deteriorating",
            "stable": "stable",
        }.get(inflation_direction, "stable")

        return {
            "id": "inflation",
            "name": "Inflation",
            "score": round(score, 1),
            "color": _color_for_score(score),
            "trend": risk_trend,
            "components": components,
            "data_freshness": str(data_date) if data_date else None,
        }

    def _score_labor(self, context: Dict, analytics: Dict) -> Dict:
        """Score labor market risk (0-100).

        Phase 3.3 expansion:
          - Sahm Rule (30%) — recession trigger signal
          - Unemployment rate level (20%)
          - Initial claims (20%)
          - Payroll MoM (10%)
          - JOLTS openings YoY (10%) — labor demand softening
          - JOLTS quits rate (10%) — worker confidence
        """
        ind_analytics = analytics.get("indicators", {})
        derived = ind_analytics.get("_derived", {})
        indicators = context.get("indicators", {})

        components = []
        scores = []

        # Sahm Rule — most powerful signal
        sahm = derived.get("sahm_rule")
        if sahm is not None:
            # 0 at sahm=0, 50 at sahm=0.3, 100 at sahm=0.8
            sahm_score = _linear_scale(sahm, 0, 0.8)
            scores.append(("sahm", sahm_score, 0.30))
            triggered = sahm >= 0.50
            status = "triggered" if triggered else "elevated" if sahm > 0.30 else "normal"
            components.append({"label": "Sahm Rule", "value": f"{sahm:.2f}", "status": status})

        # Unemployment rate
        unrate = indicators.get("UNRATE", {})
        if unrate.get("value") is not None:
            ur = unrate["value"]
            # 0 at 3.5%, 50 at 5.0%, 100 at 7.0%
            ur_score = _linear_scale(ur, 3.5, 7.0)
            scores.append(("unrate", ur_score, 0.20))
            status = "low" if ur < 4.0 else "moderate" if ur < 5.5 else "elevated"
            components.append({"label": "Unemployment", "value": f"{ur:.1f}%", "status": status})

        # Initial Claims
        icsa = indicators.get("ICSA", {})
        if icsa.get("value") is not None:
            claims = icsa["value"]
            # 0 at 200K, 50 at 275K, 100 at 400K
            claims_score = _linear_scale(claims, 200000, 400000)
            scores.append(("claims", claims_score, 0.20))
            claims_k = claims / 1000
            status = "healthy" if claims_k < 225 else "softening" if claims_k < 300 else "recession signal"
            components.append({"label": "Initial Claims", "value": f"{claims_k:.0f}K", "status": status})

        # Payroll momentum (jobs change)
        payems = indicators.get("PAYEMS", {})
        if payems.get("jobs_change_thousands") is not None:
            jobs = payems["jobs_change_thousands"]
            # Inverse: strong jobs = low risk. 0 at +300K, 50 at +100K, 100 at -100K
            jobs_score = _linear_scale(-jobs, -300, 100)
            scores.append(("payrolls", jobs_score, 0.10))
            status = "strong" if jobs > 200 else "moderate" if jobs > 100 else "stall speed" if jobs > 0 else "contracting"
            components.append({"label": "Payrolls MoM", "value": f"{jobs:+.0f}K", "status": status})

        # JOLTS Job Openings YoY (Phase 3.3) — softening demand signal
        jolts = indicators.get("JTSJOL", {})
        openings_yoy = jolts.get("yoy_change_pct")
        if openings_yoy is not None:
            # Drops in openings: -10% = warning, -25% = recession-level
            openings_score = _linear_scale(-openings_yoy, -10.0, 30.0)
            scores.append(("jolts_openings", openings_score, 0.10))
            status = (
                "expanding" if openings_yoy > 5
                else "stable" if openings_yoy > -5
                else "softening" if openings_yoy > -15
                else "contracting"
            )
            components.append({"label": "JOLTS Openings YoY", "value": f"{openings_yoy:+.1f}%", "status": status})

        # JOLTS Quits Rate (Phase 3.3) — worker confidence
        # High quits rate = workers confident in finding new jobs (good labor market).
        quits = indicators.get("JTSQUR", {})
        quits_rate = quits.get("value")
        if quits_rate is not None:
            # Inverse: high quits = low risk. 0 at 3.0% (peak), 50 at 2.2%, 100 at 1.5%
            quits_score = _linear_scale(-quits_rate, -3.0, -1.5)
            scores.append(("jolts_quits", quits_score, 0.10))
            status = "confident" if quits_rate > 2.5 else "moderate" if quits_rate > 2.0 else "weak"
            components.append({"label": "Quits Rate", "value": f"{quits_rate:.1f}%", "status": status})

        if scores:
            total_weight = sum(w for _, _, w in scores)
            score = sum(s * w for _, s, w in scores) / total_weight
        else:
            score = 50

        data_date = indicators.get("UNRATE", {}).get("date") or indicators.get("PAYEMS", {}).get("date")

        # For labor risk: DECELERATING unemployment = risk IMPROVING (jobs are strong)
        # ACCELERATING unemployment = risk DETERIORATING (jobs weakening)
        unrate_trend = ind_analytics.get("UNRATE", {}).get("trend", "")
        if unrate_trend:
            # Unemployment going up = risk worsening, unemployment going down = risk improving
            risk_trend = {"ACCELERATING": "deteriorating", "DECELERATING": "improving", "STABLE": "stable"}.get(unrate_trend, "stable")
        else:
            risk_trend = "stable"

        return {
            "id": "labor",
            "name": "Labor Market",
            "score": round(score, 1),
            "color": _color_for_score(score),
            "trend": risk_trend,
            "components": components,
            "data_freshness": str(data_date) if data_date else None,
        }

    def _score_yield_curve(self, context: Dict, analytics: Dict) -> Dict:
        """Score yield curve risk (0-100)."""
        yield_analytics = analytics.get("yields", {})
        yields_ctx = context.get("yields", {})
        spreads = yields_ctx.get("spreads", {})

        components = []
        scores = []

        # 10Y-2Y spread — primary signal
        spread_10y2y = spreads.get("10y2y")
        if spread_10y2y is not None:
            # Positive spread = low risk, negative = high risk
            # 0 at +2.0%, 50 at 0%, 100 at -1.0%
            spread_score = _linear_scale(-spread_10y2y, -2.0, 1.0)
            scores.append(("spread", spread_score, 0.50))
            status = "normal" if spread_10y2y > 0.5 else "flat" if spread_10y2y > 0 else "inverted"
            components.append({"label": "10Y-2Y Spread", "value": f"{spread_10y2y:.2f}%", "status": status})

        # Curve shape
        shape = yield_analytics.get("shape", "UNKNOWN")
        shape_score = {
            "STEEP": 5, "NORMAL": 15, "FLAT": 40,
            "PARTIALLY_INVERTED": 70, "DEEPLY_INVERTED": 95,
        }.get(shape, 40)
        scores.append(("shape", shape_score, 0.25))
        components.append({"label": "Curve Shape", "value": shape.lower(), "status": shape.lower()})

        # Steepening trend
        trend = yield_analytics.get("steepening_trend") or "STABLE"
        trend_score = {
            "STEEPENING": 25, "STABLE": 40, "FLATTENING": 65
        }.get(trend, 40)
        scores.append(("trend", trend_score, 0.25))
        components.append({"label": "Trend", "value": trend.lower(), "status": trend.lower()})

        if scores:
            total_weight = sum(w for _, _, w in scores)
            score = sum(s * w for _, s, w in scores) / total_weight
        else:
            score = 50

        return {
            "id": "yield_curve",
            "name": "Yield Curve",
            "score": round(score, 1),
            "color": _color_for_score(score),
            "trend": trend.lower(),
            "components": components,
            "data_freshness": str(datetime.now().date()),
        }

    def _score_credit(self, context: Dict, analytics: Dict) -> Dict:
        """Score credit market risk (0-100)."""
        credit_analytics = analytics.get("credit", {})
        credit_ctx = context.get("credit", {})

        components = []
        scores = []

        # Stress level from analytics
        stress = credit_analytics.get("stress_level", "NORMAL")
        stress_score = {"NORMAL": 15, "ELEVATED": 55, "HIGH": 85}.get(stress, 40)
        scores.append(("stress", stress_score, 0.40))
        components.append({"label": "Stress Level", "value": stress.lower(), "status": stress.lower()})

        # IG spread
        ig = credit_ctx.get("US_IG", {})
        if ig.get("spread_bps") is not None:
            ig_bps = ig["spread_bps"]
            # 0 at 80bps, 50 at 150bps, 100 at 250bps
            ig_score = _linear_scale(ig_bps, 80, 250)
            scores.append(("ig", ig_score, 0.30))
            status = "tight" if ig_bps < 100 else "normal" if ig_bps < 150 else "wide"
            components.append({"label": "IG OAS", "value": f"{ig_bps:.0f}bps", "status": status})

        # HY spread
        hy = credit_ctx.get("US_HY", {})
        if hy.get("spread_bps") is not None:
            hy_bps = hy["spread_bps"]
            # 0 at 300bps, 50 at 500bps, 100 at 800bps
            hy_score = _linear_scale(hy_bps, 300, 800)
            scores.append(("hy", hy_score, 0.30))
            status = "tight" if hy_bps < 350 else "normal" if hy_bps < 500 else "stressed"
            components.append({"label": "HY OAS", "value": f"{hy_bps:.0f}bps", "status": status})

        if scores:
            total_weight = sum(w for _, _, w in scores)
            score = sum(s * w for _, s, w in scores) / total_weight
        else:
            score = 50

        return {
            "id": "credit",
            "name": "Credit",
            "score": round(score, 1),
            "color": _color_for_score(score),
            "trend": "stable",
            "components": components,
            "data_freshness": str(datetime.now().date()),
        }

    def _score_volatility(self, live_data: Dict) -> Dict:
        """Score volatility risk (0-100) from VIX."""
        components = []
        vix = live_data.get("vix")

        if vix is not None:
            # Piecewise scoring matching signal_interpretation.md thresholds
            if vix < 15:
                score = _linear_scale(vix, 10, 15) * 0.2  # 0-20
            elif vix < 20:
                score = 20 + _linear_scale(vix, 15, 20) * 0.15  # 20-35
            elif vix < 25:
                score = 35 + _linear_scale(vix, 20, 25) * 0.15  # 35-50
            elif vix < 30:
                score = 50 + _linear_scale(vix, 25, 30) * 0.15  # 50-65
            elif vix < 35:
                score = 65 + _linear_scale(vix, 30, 35) * 0.15  # 65-80
            elif vix < 40:
                score = 80 + _linear_scale(vix, 35, 40) * 0.10  # 80-90
            else:
                score = 90 + _linear_scale(vix, 40, 60) * 0.10  # 90-100

            status = "complacent" if vix < 15 else "normal" if vix < 25 else "elevated" if vix < 35 else "crisis"
            components.append({"label": "VIX", "value": f"{vix:.1f}", "status": status})
        else:
            score = 50
            components.append({"label": "VIX", "value": "N/A", "status": "unavailable"})

        # VIX change (additional context)
        vix_chg = live_data.get("vix_change_pct")
        if vix_chg is not None:
            # Spike bonus: +20% VIX move adds risk
            if vix_chg > 20:
                score = min(100, score + 15)
            elif vix_chg > 10:
                score = min(100, score + 8)
            components.append({"label": "VIX 1D Change", "value": f"{vix_chg:+.1f}%", "status": "spike" if vix_chg > 10 else "normal"})

        return {
            "id": "volatility",
            "name": "Volatility",
            "score": round(score, 1),
            "color": _color_for_score(score),
            "trend": "stable",
            "components": components,
            "data_freshness": str(datetime.now().date()),
        }

    def _score_housing(self, context: Dict, analytics: Dict) -> Dict:
        """
        Score housing market risk (Phase 3.1).

        Housing starts and permits historically lead recessions by 6-12
        months. Big YoY drops in housing activity are an early warning
        before broader weakness shows up in payrolls or production.

        Inputs:
          - HOUST YoY change (50%) — single-family + multi-family starts
          - PERMIT YoY change (30%) — building permits, even leadier than starts
          - HOUST 6mo / 12mo MA crossover (20%) — accelerating decline signal
        """
        indicators = context.get("indicators", {})

        components: List[Dict[str, Any]] = []
        scores: List[tuple] = []

        houst = indicators.get("HOUST", {})
        houst_value = houst.get("value")
        houst_yoy = houst.get("yoy_change_pct")
        if houst_yoy is not None:
            # YoY drops: -10% = warning, -25% = recession-level signal
            houst_score = _linear_scale(-houst_yoy, -10.0, 30.0)
            scores.append(("houst_yoy", houst_score, 0.50))
            status = (
                "expanding" if houst_yoy > 5
                else "stable" if houst_yoy > -5
                else "softening" if houst_yoy > -15
                else "contracting"
            )
            label_value = (
                f"{houst_value:.0f}K, {houst_yoy:+.1f}% YoY"
                if houst_value is not None
                else f"{houst_yoy:+.1f}% YoY"
            )
            components.append({"label": "Housing Starts", "value": label_value, "status": status})

        permit = indicators.get("PERMIT", {})
        permit_value = permit.get("value")
        permit_yoy = permit.get("yoy_change_pct")
        if permit_yoy is not None:
            permit_score = _linear_scale(-permit_yoy, -10.0, 30.0)
            scores.append(("permit_yoy", permit_score, 0.30))
            status = (
                "expanding" if permit_yoy > 5
                else "stable" if permit_yoy > -5
                else "softening" if permit_yoy > -15
                else "contracting"
            )
            label_value = (
                f"{permit_value:.0f}K, {permit_yoy:+.1f}% YoY"
                if permit_value is not None
                else f"{permit_yoy:+.1f}% YoY"
            )
            components.append({"label": "Building Permits", "value": label_value, "status": status})

        # MA crossover signal — short-MA below long-MA = accelerating decline.
        # Sourced from indicators analytics if present; otherwise skipped.
        ind_analytics = analytics.get("indicators", {})
        houst_analytics = ind_analytics.get("HOUST", {})
        ma_signal = houst_analytics.get("ma_cross_pct")  # may be missing — optional
        if ma_signal is not None:
            # ma_cross_pct < 0 means 6mo MA below 12mo MA → declining trend
            cross_score = _linear_scale(-ma_signal, -10.0, 10.0)
            scores.append(("houst_ma_cross", cross_score, 0.20))
            status = "rising" if ma_signal > 1 else "stable" if ma_signal > -1 else "declining"
            components.append({"label": "Starts 6/12mo MA", "value": f"{ma_signal:+.1f}%", "status": status})

        if scores:
            total_weight = sum(w for _, _, w in scores)
            score = sum(s * w for _, s, w in scores) / total_weight
        else:
            score = 50

        # Trend: prefer the stronger of HOUST or PERMIT YoY direction.
        if houst_yoy is not None and houst_yoy < -5:
            risk_trend = "deteriorating"
        elif houst_yoy is not None and houst_yoy > 5:
            risk_trend = "improving"
        else:
            risk_trend = "stable"

        data_date = (
            indicators.get("HOUST", {}).get("date")
            or indicators.get("PERMIT", {}).get("date")
        )

        return {
            "id": "housing",
            "name": "Housing",
            "score": round(score, 1),
            "color": _color_for_score(score),
            "trend": risk_trend,
            "components": components,
            "data_freshness": str(data_date) if data_date else None,
        }

    def _score_geopolitical(self, context: Dict, analytics: Dict, live_data: Dict) -> Dict:
        """
        Score geopolitical risk (0-100) from market-data proxies.

        Primary signals (market-driven):
        - Oil price level and spike (crude is the canonical geopolitical risk proxy)
        - Gold surge (safe-haven demand)
        - EM FX stress (capital flight from geopolitical risk)

        Secondary signal (headline-driven):
        - Critical/high severity geopolitical news count (tiebreaker)
        """
        components = []
        sub_scores = []

        # Oil price level and momentum
        oil = live_data.get("oil")
        oil_chg = live_data.get("oil_change_pct")
        if oil is not None:
            # Oil >$100 is geopolitical stress, >$120 is crisis
            oil_level_score = _linear_scale(oil, 60, 120)
            sub_scores.append(("oil_level", oil_level_score, 0.20))
            status = "normal" if oil < 80 else "elevated" if oil < 100 else "stress"
            components.append({"label": "Crude Oil", "value": f"${oil:.1f}", "status": status})

            if oil_chg is not None and oil_chg > 5:
                # Sharp oil spike = geopolitical event
                spike_score = _linear_scale(oil_chg, 5, 20)
                sub_scores.append(("oil_spike", spike_score, 0.15))
                components.append({"label": "Oil 1D Spike", "value": f"{oil_chg:+.1f}%", "status": "spike"})

        # Gold as safe-haven proxy
        gold_chg = live_data.get("gold_change_pct")
        if gold_chg is not None:
            # Gold surge >1% in a day = risk-off/geopolitical
            gold_score = _linear_scale(max(0, gold_chg), 0, 3.0)
            sub_scores.append(("gold", gold_score, 0.20))
            status = "normal" if gold_chg < 1 else "elevated" if gold_chg < 2 else "surge"
            components.append({"label": "Gold 1D Move", "value": f"{gold_chg:+.1f}%", "status": status})

        # EM FX stress (Phase 3.5): 20-day z-score of average EM weakening,
        # not the noisy single-day move. Falls back to em_avg_24h from
        # analytics if FX history isn't available.
        em_zscore_data = self._compute_em_fx_zscore(window_days=20)
        if em_zscore_data is not None:
            em_z = em_zscore_data["zscore"]
            recent_avg = em_zscore_data["recent_avg_pct"]
            # z < 0 means EM weaker than typical -> stress.
            # 0 at z=0 (typical), 50 at z=-1.0, 100 at z=-2.5.
            em_score = _linear_scale(-em_z, 0, 2.5)
            sub_scores.append(("em_fx", em_score, 0.25))
            status = "normal" if em_z > -0.5 else "stress" if em_z > -1.5 else "severe"
            components.append({
                "label": "EM FX Stress (20d z)",
                "value": f"z={em_z:+.2f} ({recent_avg:+.1f}%)",
                "status": status,
            })
        else:
            # Fallback to legacy 24-hour average if no history available.
            fx_analytics = analytics.get("fx", {})
            em_avg = fx_analytics.get("em_avg_24h")
            if em_avg is not None:
                em_score = _linear_scale(-em_avg, 0, 2.0)
                sub_scores.append(("em_fx", em_score, 0.25))
                status = "normal" if em_avg > -0.5 else "stress" if em_avg > -1.5 else "severe"
                components.append({"label": "EM FX Stress (24h)", "value": f"{em_avg:+.1f}%", "status": status})

        # News severity as tiebreaker (secondary signal, low weight)
        news_analytics = analytics.get("news", {})
        severity_counts = news_analytics.get("severity_counts", {})
        by_category = news_analytics.get("by_category", {})
        geo_news = by_category.get("GEOPOLITICAL", 0) + by_category.get("TRADE_POLICY", 0) + by_category.get("POLITICAL", 0)
        critical_high = severity_counts.get("CRITICAL", 0) + severity_counts.get("HIGH", 0)

        if geo_news > 0:
            # Max score from news alone capped at 60 (market data takes priority)
            news_score = min(60, geo_news * 8 + critical_high * 5)
            sub_scores.append(("news", news_score, 0.20))
            status = "quiet" if geo_news < 3 else "active" if geo_news < 8 else "elevated"
            components.append({"label": "Geo Headlines", "value": f"{geo_news} articles", "status": status})

        if sub_scores:
            total_weight = sum(w for _, _, w in sub_scores)
            score = sum(s * w for _, s, w in sub_scores) / total_weight
        else:
            score = 30  # no data = moderate-low assumption

        return {
            "id": "geopolitical",
            "name": "Geopolitical",
            "score": round(score, 1),
            "color": _color_for_score(score),
            "trend": "stable",
            "components": components,
            "data_freshness": str(datetime.now().date()),
        }

    # ──────────────────────────────────────────
    # Data Fetchers
    # ──────────────────────────────────────────

    def _compute_em_fx_zscore(self, window_days: int = 20) -> Optional[Dict[str, Any]]:
        """
        Phase 3.5: Compute the 20-day z-score of average EM-currency 24h moves.

        Pulls daily-resolution close prices from FXRate for the EM pairs over
        the last (window_days * 2) days, computes per-pair daily % changes,
        averages across pairs to get a daily "EM stress" series, then
        z-scores the most-recent value against the trailing window.

        Returns None if there isn't enough history to compute.
        """
        try:
            from modules.data_storage.schema import FXRate

            # Detect which pairs are EM. The FX module already classifies
            # currencies in the analytics engine, but we replicate the EM
            # set here so the scorecard doesn't depend on the analytics
            # output for this signal.
            from modules.market_summary.ai_narrative import EM_CURRENCIES

            em_pairs = [f"USD/{c}" for c in EM_CURRENCIES]
            if not em_pairs:
                return None

            cutoff = datetime.utcnow() - timedelta(days=window_days * 3)
            rates = (
                self.db.query(FXRate)
                .filter(FXRate.pair.in_(em_pairs))
                .filter(FXRate.timestamp >= cutoff)
                .order_by(FXRate.timestamp.asc())
                .all()
            )
            if not rates:
                return None

            # Build per-pair daily series: take last close per (pair, date).
            from collections import defaultdict
            per_pair_daily: Dict[str, Dict[str, float]] = defaultdict(dict)
            for r in rates:
                if r.rate is None:
                    continue
                d = r.timestamp.date().isoformat()
                per_pair_daily[r.pair][d] = float(r.rate)

            # Compute daily % change per pair, then average across pairs.
            # USD/XXX up = foreign currency weakening = stress (negative move
            # in our framing). We invert sign so "EM weakening" → negative.
            all_dates = sorted({d for series in per_pair_daily.values() for d in series})
            if len(all_dates) < 5:
                return None

            stress_series: List[float] = []
            for i in range(1, len(all_dates)):
                d_prev = all_dates[i - 1]
                d_curr = all_dates[i]
                changes = []
                for pair, series in per_pair_daily.items():
                    if d_prev in series and d_curr in series and series[d_prev] != 0:
                        chg_pct = ((series[d_curr] - series[d_prev]) / series[d_prev]) * 100
                        # USD/XXX up = foreign weaker = bad for EM. Sign flip
                        # to match analytics' em_avg_24h convention.
                        changes.append(-chg_pct)
                if changes:
                    stress_series.append(sum(changes) / len(changes))

            if len(stress_series) < window_days // 2:
                return None

            arr = np.array(stress_series[-window_days * 2:], dtype=float)
            if arr.size < 5:
                return None

            recent = float(arr[-1])
            window = arr[-window_days:] if arr.size >= window_days else arr
            mean = float(window.mean())
            sd = float(window.std())
            if sd == 0:
                z = 0.0
            else:
                z = (recent - mean) / sd

            return {
                "zscore": round(z, 3),
                "recent_avg_pct": round(recent, 3),
                "window_mean": round(mean, 3),
                "window_std": round(sd, 3),
                "n_observations": int(arr.size),
            }
        except Exception as e:
            logger.debug(f"EM FX z-score computation skipped: {e}")
            return None

    def _fetch_recession_ml(self) -> Optional[Dict[str, Any]]:
        """
        Phase 3.4: Surface the ML model's 6m recession probability as a
        display-only field on the scorecard response. NOT weighted into the
        composite (signals overlap with the pillars and would double-count).

        Returns None if the model isn't trained or import fails — the UI
        should hide the banner gracefully.
        """
        try:
            from modules.recession_model.predictor import RecessionPredictor

            predictor = RecessionPredictor(self.db)
            current = predictor.get_current_probability()
            if not current.get("trained") or current.get("error"):
                return None
            probs = current.get("probabilities") or {}
            return {
                "prob_3m": probs.get("3m"),
                "prob_6m": probs.get("6m"),
                "prob_12m": probs.get("12m"),
                "signal": current.get("signal"),
                "signal_label": current.get("signal_label"),
                "decision_threshold_6m": current.get("decision_threshold_6m"),
            }
        except Exception as e:
            logger.debug(f"Recession ML fetch skipped: {e}")
            return None

    def _fetch_live_data(self) -> Dict[str, Any]:
        """Fetch live VIX, oil, gold data via yfinance (Phase 2 §2.7 cached).

        Uses a module-level 5-minute TTL cache so concurrent scorecard
        requests don't hammer Yahoo. The cache is process-local and
        cleared on restart, which is fine — a 5-minute staleness on
        VIX is invisible at the daily-grained scorecard.
        """
        now = time.time()
        cached = _live_data_cache.get("data")
        cached_at = _live_data_cache.get("timestamp", 0.0)
        if cached is not None and (now - cached_at) < _LIVE_DATA_TTL_SECONDS:
            return cached

        result: Dict[str, Any] = {}
        try:
            import yfinance as yf
            import pandas as pd

            tickers = {
                "^VIX": ("vix", "vix_change_pct"),
                "CL=F": ("oil", "oil_change_pct"),
                "GC=F": ("gold", "gold_change_pct"),
            }

            for ticker, (val_key, chg_key) in tickers.items():
                try:
                    data = yf.download(ticker, period="5d", progress=False, auto_adjust=True)
                    if len(data) > 0:
                        close = data["Close"]
                        if isinstance(close, pd.DataFrame):
                            close = close.iloc[:, 0]
                        val = float(close.iloc[-1])
                        prev = float(close.iloc[-2]) if len(close) > 1 else val
                        chg = ((val - prev) / prev) * 100
                        result[val_key] = round(val, 2)
                        result[chg_key] = round(chg, 2)
                except Exception as e:
                    logger.debug(f"Failed to fetch {ticker}: {e}")
        except ImportError:
            logger.warning("yfinance not available for live data")

        # Only cache when we got real data; otherwise let the next request retry.
        if result:
            _live_data_cache["data"] = result
            _live_data_cache["timestamp"] = now
        return result

    def _get_historical_sparklines(self, days: int = 14) -> List[Dict]:
        """
        Read historical pillar scores from journal snapshots.

        Preferred path: read `pillar_scores_snapshot` directly — these are the
        same multi-component scores published live (Phase 1 §1.4).

        Fallback path (for journal entries pre-dating §1.4): reconstruct an
        approximate pillar score from the indicator_snapshot using a single
        component per pillar. This drifts from live values but keeps the
        sparkline non-empty during the migration window.
        """
        try:
            from modules.market_summary.journal import MarketJournal

            journal = MarketJournal(self.db)
            entries = journal.get_recent(days=days)
            if not entries:
                return []

            sparkline_data = []
            for entry in reversed(entries):  # chronological order
                stored = entry.pillar_scores_snapshot or {}
                stored_pillars = stored.get("pillars") if isinstance(stored, dict) else None

                if stored_pillars:
                    # Preferred path — published scores. Today's value matches
                    # the live pillar value so trend math is consistent.
                    day_scores = {"date": entry.date.isoformat()}
                    for pid in PILLAR_WEIGHTS:
                        p = stored_pillars.get(pid)
                        day_scores[pid] = (
                            round(float(p.get("score")), 1)
                            if isinstance(p, dict) and p.get("score") is not None
                            else None
                        )
                    composite = stored.get("composite")
                    if composite is not None:
                        day_scores["composite"] = round(float(composite), 1)
                    else:
                        # Derive from stored pillars on the fly.
                        avail = {k: v for k, v in day_scores.items() if k != "date" and v is not None}
                        if avail:
                            weights = {k: PILLAR_WEIGHTS.get(k, 0.15) for k in avail}
                            total_w = sum(weights.values())
                            day_scores["composite"] = round(
                                sum(avail[k] * weights[k] for k in avail) / total_w, 1
                            )
                        else:
                            day_scores["composite"] = 50
                    sparkline_data.append(day_scores)
                    continue

                # Fallback: legacy reconstruction from indicator_snapshot.
                snapshot = entry.indicator_snapshot or {}
                derived = snapshot.get("derived", {})

                day_scores = {"date": entry.date.isoformat()}

                cpi_yoy = derived.get("cpi_yoy")
                day_scores["inflation"] = round(_linear_scale(cpi_yoy, 1.5, 6.0), 1) if cpi_yoy else None

                sahm = derived.get("sahm_rule")
                day_scores["labor"] = round(_linear_scale(sahm, 0, 0.8), 1) if sahm else None

                spread = snapshot.get("spreads", {}).get("10y2y")
                day_scores["yield_curve"] = round(_linear_scale(-spread, -2.0, 1.0), 1) if spread is not None else None

                stress = snapshot.get("credit_stress", "NORMAL")
                day_scores["credit"] = {"NORMAL": 15, "ELEVATED": 55, "HIGH": 85}.get(stress, 40)

                day_scores["volatility"] = None
                day_scores["geopolitical"] = None

                available = {k: v for k, v in day_scores.items() if k != "date" and v is not None}
                if available:
                    weights = {k: PILLAR_WEIGHTS.get(k, 0.15) for k in available}
                    total_w = sum(weights.values())
                    day_scores["composite"] = round(
                        sum(available[k] * weights[k] for k in available) / total_w, 1
                    )
                else:
                    day_scores["composite"] = 50

                sparkline_data.append(day_scores)

            return sparkline_data

        except Exception as e:
            logger.debug(f"Sparkline reconstruction failed: {e}")
            return []
