"""
Intelligence API Router

Provides endpoints for the AI-powered market intelligence system:
conversational chat, regime detection, playbook matching, and correlation tracking.
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from loguru import logger

from modules.data_storage.database import get_db
from modules.utils.timezone import get_current_time

router = APIRouter()


# ──────────────────────────────────────────────
# Request/Response Models
# ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    theory_depth: Optional[str] = "analyst"  # "executive", "analyst", or "research"


class ScenarioRequest(BaseModel):
    scenario: str
    theory_depth: Optional[str] = "analyst"


# ──────────────────────────────────────────────
# Theory Depth Tiers
# ──────────────────────────────────────────────

@router.get("/theory/tiers")
async def get_theory_tiers():
    """Get available analytical depth tiers."""
    try:
        from modules.theory_library import get_available_tiers
        return {
            "tiers": get_available_tiers(),
            "default": "analyst",
        }
    except Exception as e:
        logger.error(f"Theory tiers error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Chat Endpoints
# ──────────────────────────────────────────────

@router.post("/chat")
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """Conversational AI chat with economic context and analytical lens metadata."""
    try:
        from modules.conversational_ai import ChatEngine

        engine = ChatEngine(db)
        if not engine.is_available():
            raise HTTPException(
                status_code=503,
                detail="AI chat unavailable. ANTHROPIC_API_KEY not configured."
            )

        result = await engine.chat(
            request.message,
            request.session_id,
            theory_depth=request.theory_depth,
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/sessions")
async def get_chat_sessions(db: Session = Depends(get_db)):
    """Get list of active chat sessions."""
    try:
        from modules.conversational_ai import ChatEngine

        engine = ChatEngine(db)
        return {
            "sessions": engine.get_sessions(),
            "timestamp": get_current_time().isoformat(),
        }
    except Exception as e:
        logger.error(f"Sessions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Regime Detection Endpoints
# ──────────────────────────────────────────────

@router.get("/regime")
async def get_regime(db: Session = Depends(get_db)):
    """Get current regime assessment."""
    try:
        from modules.regime_detector import RegimeDetector

        detector = RegimeDetector(db)
        return detector.assess_regime()

    except Exception as e:
        logger.error(f"Regime assessment error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/regime/shifts")
async def get_regime_shifts(
    include_ai: bool = Query(default=False, description="Include AI explanations"),
    db: Session = Depends(get_db),
):
    """Get detected regime shifts with optional AI explanations."""
    try:
        from modules.regime_detector import RegimeDetector

        detector = RegimeDetector(db)
        return detector.get_shifts(include_ai=include_ai)

    except Exception as e:
        logger.error(f"Regime shifts error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Playbook Matching Endpoints
# ──────────────────────────────────────────────

@router.get("/playbook")
async def get_playbook(
    include_ai: bool = Query(default=False, description="Include AI analysis"),
    db: Session = Depends(get_db),
):
    """Match current conditions against historical episodes."""
    try:
        from modules.playbook_matcher import PlaybookMatcher

        matcher = PlaybookMatcher(db)
        return matcher.match(include_ai=include_ai)

    except Exception as e:
        logger.error(f"Playbook matching error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Correlation Tracking Endpoints
# ──────────────────────────────────────────────

@router.get("/correlations")
async def get_correlations():
    """Get cross-asset correlation analysis."""
    try:
        from modules.correlation_tracker import CorrelationTracker

        tracker = CorrelationTracker()
        return tracker.analyze()

    except Exception as e:
        logger.error(f"Correlation analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Risk Scorecard Endpoints
# ──────────────────────────────────────────────

@router.get("/risk-scorecard")
async def get_risk_scorecard(db: Session = Depends(get_db)):
    """Get composite macro risk scorecard with 7 pillar breakdowns."""
    try:
        from modules.risk_scorecard import RiskScorecard

        scorecard = RiskScorecard(db)
        return scorecard.compute()

    except Exception as e:
        logger.error(f"Risk scorecard error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk-scorecard/backtest")
async def get_risk_scorecard_backtest(
    lookahead_days: int = Query(365, ge=30, le=730),
    db: Session = Depends(get_db),
):
    """
    Phase 4.3: Back-test composite cutoff thresholds (50/60/67) against NBER
    recession dates within `lookahead_days` after each historical journal
    snapshot. Validates the published green/yellow/red bands.
    """
    try:
        from modules.risk_scorecard.backtest import backtest_composite_cutoff

        return backtest_composite_cutoff(db, lookahead_days=lookahead_days)
    except Exception as e:
        logger.error(f"Risk scorecard backtest error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Regime Timeline Endpoints
# ──────────────────────────────────────────────

def _recompute_regime_from_snapshot(snapshot: dict) -> tuple:
    """
    Recompute regime and themes from a journal snapshot using the corrected
    weighted scoring logic. This ensures old journal entries with buggy
    curve shape classifications get corrected on the fly.

    Returns (regime, corrected_themes).
    """
    if not snapshot:
        return "UNKNOWN", []

    derived = snapshot.get("derived", {})
    spreads = snapshot.get("spreads", {})

    weighted_score = 0.0
    themes = []

    # 1. Yield curve — use the actual 10Y-2Y spread, not the stored shape
    spread_10y2y = spreads.get("10y2y")
    curve_inverted = False
    if spread_10y2y is not None:
        spread_bps = spread_10y2y * 100
        if spread_bps < -50:
            weighted_score += 2.0
            curve_inverted = True
            themes.append("curve_deeply_inverted")
        elif spread_bps < -10:
            weighted_score += 1.0
            curve_inverted = True
            themes.append("curve_inverted")
        elif spread_bps < 25:
            themes.append("curve_flat")
        elif spread_bps >= 100:
            themes.append("curve_steep")
        else:
            themes.append("curve_normal")

    # 2. Credit stress
    credit_stress = snapshot.get("credit_stress", "NORMAL")
    if credit_stress == "HIGH":
        weighted_score += 2.0
        themes.append("credit_stressed")
    elif credit_stress == "ELEVATED":
        weighted_score += 0.75
        themes.append("credit_elevated")

    # 3. Sahm Rule
    sahm = derived.get("sahm_rule")
    if sahm is not None:
        if sahm >= 0.50:
            weighted_score += 2.5
            themes.append("sahm_triggered")
        elif sahm >= 0.30:
            weighted_score += 0.5

    # 4. CPI / inflation
    cpi_yoy = derived.get("cpi_yoy")
    if cpi_yoy is not None:
        if cpi_yoy < 2.5:
            themes.append("disinflation_progress")
        elif cpi_yoy < 3.5:
            themes.append("inflation_moderate")
        else:
            themes.append("inflation_elevated")

        if cpi_yoy > 4.0:
            weighted_score += 1.5
        elif cpi_yoy > 3.0:
            weighted_score += 0.5

    # 5. Labor
    sahm_triggered = derived.get("sahm_triggered", False)
    if sahm_triggered:
        themes.append("labor_deteriorating")
    elif sahm is not None and sahm > 0.30:
        themes.append("labor_softening")
    else:
        themes.append("labor_stable")

    # 6. Policy stance
    real_ff = derived.get("real_fed_funds")
    if real_ff is not None:
        if real_ff > 2.0:
            themes.append("policy_restrictive")
        elif real_ff > 0.5:
            themes.append("policy_mildly_restrictive")
        elif real_ff > -0.5:
            themes.append("policy_neutral")
        else:
            themes.append("policy_accommodative")

    # Determine regime
    if weighted_score >= 5.0:
        regime = "CRISIS"
    elif weighted_score >= 3.5:
        regime = "RISK_OFF"
    elif weighted_score >= 2.0:
        regime = "CAUTIOUS"
    else:
        regime = "RISK_ON"

    return regime, themes


@router.get("/regime/timeline")
async def get_regime_timeline(
    days: int = Query(default=90, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """Get regime history with transitions for timeline visualization."""
    try:
        from modules.market_summary.journal import MarketJournal

        journal = MarketJournal(db)
        entries = journal.get_recent(days=days)

        if not entries:
            return {"periods": [], "transitions": [], "entries": [], "total_days": days, "actual_days": 0}

        entries.reverse()  # Chronological order

        # Recompute regime for each entry from snapshot data using corrected logic
        corrected_entries = []
        for e in entries:
            snap = e.indicator_snapshot or {}
            regime, themes = _recompute_regime_from_snapshot(snap)
            corrected_entries.append({
                "entry": e,
                "regime": regime,
                "themes": themes,
            })

        # Build regime periods (consecutive days with same regime)
        periods = []
        transitions = []
        current_period = {
            "regime": corrected_entries[0]["regime"],
            "start_date": corrected_entries[0]["entry"].date.isoformat(),
            "end_date": corrected_entries[0]["entry"].date.isoformat(),
            "days": 1,
        }

        for i in range(1, len(corrected_entries)):
            ce = corrected_entries[i]
            entry_regime = ce["regime"]

            if entry_regime == current_period["regime"]:
                current_period["end_date"] = ce["entry"].date.isoformat()
                current_period["days"] += 1
            else:
                periods.append(current_period)
                transitions.append({
                    "date": ce["entry"].date.isoformat(),
                    "from_regime": current_period["regime"],
                    "to_regime": entry_regime,
                    "trigger_themes": ce["themes"],
                })
                current_period = {
                    "regime": entry_regime,
                    "start_date": ce["entry"].date.isoformat(),
                    "end_date": ce["entry"].date.isoformat(),
                    "days": 1,
                }

        periods.append(current_period)

        # Journal entries for detail popups (with corrected regime/themes)
        entry_list = [
            {
                "date": ce["entry"].date.isoformat(),
                "regime": ce["regime"],
                "key_themes": ce["themes"],
                "narrative_summary": ce["entry"].narrative_summary,
                "news_themes": ce["entry"].news_themes or {},
            }
            for ce in corrected_entries
        ]

        return {
            "periods": periods,
            "transitions": transitions,
            "entries": entry_list,
            "total_days": days,
            "actual_days": len(entries),
        }

    except Exception as e:
        logger.error(f"Regime timeline error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Scenario Simulator Endpoints
# ──────────────────────────────────────────────

@router.post("/scenario/simulate")
async def simulate_scenario(request: ScenarioRequest, db: Session = Depends(get_db)):
    """Simulate cascading market impact of a hypothetical scenario."""
    try:
        from modules.scenario_simulator import ScenarioSimulator

        simulator = ScenarioSimulator(db)
        if not simulator.is_available():
            raise HTTPException(
                status_code=503,
                detail="AI unavailable. ANTHROPIC_API_KEY not configured."
            )

        result = simulator.simulate(request.scenario, request.theory_depth)

        if "error" in result and not result.get("simulated_impacts"):
            raise HTTPException(status_code=500, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scenario simulation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scenario/presets")
async def get_scenario_presets():
    """Get preset scenario options."""
    from modules.scenario_simulator import PRESET_SCENARIOS
    return {"presets": PRESET_SCENARIOS}


# ──────────────────────────────────────────────
# Recession Model Endpoints
# ──────────────────────────────────────────────

@router.get("/recession/probability")
async def get_recession_probability(db: Session = Depends(get_db)):
    """Get current recession probabilities from the ML model."""
    try:
        from modules.recession_model.predictor import RecessionPredictor

        predictor = RecessionPredictor(db)
        return predictor.get_current_probability()

    except Exception as e:
        logger.error(f"Recession probability error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recession/history")
async def get_recession_history():
    """Get historical recession probability time series for charting."""
    try:
        from modules.recession_model.predictor import RecessionPredictor
        from modules.data_storage.database import get_db_context

        with get_db_context() as db:
            predictor = RecessionPredictor(db)
            return predictor.get_historical_probabilities()

    except Exception as e:
        logger.error(f"Recession history error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recession/model-info")
async def get_recession_model_info():
    """Get model metadata, metrics, and feature importances."""
    try:
        from modules.recession_model import RecessionModel

        model = RecessionModel()
        loaded = model.load()

        if not loaded:
            return {"trained": False}

        return model.get_model_info()

    except Exception as e:
        logger.error(f"Recession model info error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Training state for async tracking
_training_state = {
    "status": "idle",  # idle | training | completed | failed
    "progress": None,
    "result": None,
    "error": None,
    "started_at": None,
    "completed_at": None,
}


def _run_training():
    """Run model training synchronously (called in background thread)."""
    from modules.recession_model import RecessionModel
    import time

    _training_state["status"] = "training"
    _training_state["progress"] = "Fetching FRED data..."
    _training_state["started_at"] = time.time()
    _training_state["result"] = None
    _training_state["error"] = None

    model = RecessionModel()
    result = model.train()

    _training_state["status"] = "completed"
    _training_state["progress"] = None
    _training_state["result"] = result
    _training_state["completed_at"] = time.time()
    return result


@router.post("/recession/train")
async def train_recession_model():
    """Kick off async recession model training. Returns immediately."""
    import time

    if _training_state["status"] == "training":
        return {"status": "already_training", "message": "Training is already in progress"}

    # Reset state
    _training_state["status"] = "training"
    _training_state["progress"] = "Initializing..."
    _training_state["started_at"] = time.time()
    _training_state["result"] = None
    _training_state["error"] = None
    _training_state["completed_at"] = None

    async def _train_background():
        try:
            await asyncio.to_thread(_run_training)
        except Exception as e:
            logger.error(f"Recession model training error: {e}", exc_info=True)
            _training_state["status"] = "failed"
            _training_state["error"] = str(e)
            _training_state["completed_at"] = time.time()

    asyncio.create_task(_train_background())

    return {"status": "started", "message": "Training started in background"}


@router.get("/recession/training-status")
async def get_training_status():
    """Poll training progress."""
    import time

    response = {
        "status": _training_state["status"],
        "progress": _training_state["progress"],
    }

    if _training_state["started_at"]:
        elapsed = ((_training_state.get("completed_at") or time.time()) - _training_state["started_at"])
        response["elapsed_seconds"] = round(elapsed, 1)

    if _training_state["status"] == "completed":
        response["result"] = _training_state["result"]

    if _training_state["status"] == "failed":
        response["error"] = _training_state["error"]

    return response
