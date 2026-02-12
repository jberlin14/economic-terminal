"""
Intelligence API Routes

Endpoints for the four high-impact differentiators:
1. Conversational AI (chat)
2. Regime Change Detection
3. Historical Playbook Matching
4. Cross-Asset Correlation Tracking
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from loguru import logger
from pydantic import BaseModel
from typing import Optional

from modules.data_storage.database import get_db
from modules.utils.timezone import get_current_time


router = APIRouter()


# =============================================================================
# REQUEST MODELS
# =============================================================================

class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


# =============================================================================
# 1. CONVERSATIONAL AI ENDPOINTS
# =============================================================================

@router.post("/chat")
async def chat_with_data(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Chat with your economic data.

    Send a natural language question and get a data-grounded response.
    Supports multi-turn conversations via session_id.

    Examples:
        - "Why did the 2s10s spread widen today?"
        - "Compare current labor market to 2019"
        - "What would a 50bp cut mean for equities?"
    """
    try:
        from modules.conversational_ai import ChatEngine

        engine = ChatEngine(db)

        if not engine.is_available():
            raise HTTPException(
                status_code=503,
                detail="AI chat unavailable. Configure ANTHROPIC_API_KEY."
            )

        result = await engine.chat(
            question=request.question,
            session_id=request.session_id
        )

        if "error" in result and result["error"] != str(None):
            if result["error"] == "api_key_missing":
                raise HTTPException(status_code=503, detail=result["response"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/sessions")
async def get_chat_sessions():
    """Get info about active chat sessions."""
    try:
        from modules.conversational_ai import ChatEngine
        return ChatEngine.get_active_sessions()
    except Exception as e:
        logger.error(f"Chat sessions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 2. REGIME CHANGE DETECTION ENDPOINTS
# =============================================================================

@router.get("/regime")
async def get_current_regime(db: Session = Depends(get_db)):
    """
    Get current economic regime assessment.

    Checks all regime detection rules (Sahm Rule, yield curve,
    VIX, credit stress, inflation, Fed policy) and returns
    the overall regime classification.
    """
    try:
        from modules.regime_detector import RegimeChangeDetector

        detector = RegimeChangeDetector(db)
        return detector.get_current_regime()

    except Exception as e:
        logger.error(f"Regime detection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/regime/shifts")
async def detect_regime_shifts(db: Session = Depends(get_db)):
    """
    Detect active regime shifts with AI-powered explanations.

    Returns any detected regime changes along with contextual
    explanations of what triggered them and what typically follows.
    """
    try:
        from modules.regime_detector import RegimeChangeDetector

        detector = RegimeChangeDetector(db)
        shifts = await detector.detect_and_explain()

        return {
            "shifts": shifts,
            "count": len(shifts),
            "timestamp": get_current_time().isoformat(),
        }

    except Exception as e:
        logger.error(f"Regime shift detection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 3. HISTORICAL PLAYBOOK MATCHING ENDPOINTS
# =============================================================================

@router.get("/playbook")
async def match_historical_playbooks(
    with_analysis: bool = Query(False, description="Include AI analysis of top matches"),
    db: Session = Depends(get_db)
):
    """
    Match current conditions to historical episodes.

    Compares current economic regime against known historical periods
    (2008 GFC, 2020 COVID, 1998 LTCM, 2022 Tightening, etc.)
    and ranks them by similarity.
    """
    try:
        from modules.playbook_matcher import PlaybookMatcher

        matcher = PlaybookMatcher(db)

        if with_analysis:
            result = await matcher.match_and_analyze()
        else:
            result = matcher.match_episodes()

        return result

    except Exception as e:
        logger.error(f"Playbook matching error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 4. CROSS-ASSET CORRELATION ENDPOINTS
# =============================================================================

@router.get("/correlations")
async def get_correlations(db: Session = Depends(get_db)):
    """
    Get cross-asset correlation matrix and breakdown alerts.

    Monitors key asset relationships:
    - Stocks/Bonds, Stocks/VIX, Dollar/Gold
    - 2Y/10Y yield co-movement
    - Oil/Inflation expectations
    - NASDAQ/S&P breadth

    Flags correlation breakdowns that signal regime shifts.
    """
    try:
        from modules.correlation_tracker import CorrelationTracker

        tracker = CorrelationTracker(db)
        return tracker.compute_all_correlations()

    except Exception as e:
        logger.error(f"Correlation tracking error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/correlations/breakdowns")
async def get_correlation_breakdowns(db: Session = Depends(get_db)):
    """
    Get only correlation breakdowns (for alerts).

    Returns pairs where the current correlation has deviated
    significantly from normal, indicating a regime shift.
    """
    try:
        from modules.correlation_tracker import CorrelationTracker

        tracker = CorrelationTracker(db)
        breakdowns = tracker.get_breakdown_alerts()

        return {
            "breakdowns": breakdowns,
            "count": len(breakdowns),
            "timestamp": get_current_time().isoformat(),
        }

    except Exception as e:
        logger.error(f"Correlation breakdown error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# COMBINED INTELLIGENCE ENDPOINT
# =============================================================================

@router.get("/overview")
async def get_intelligence_overview(db: Session = Depends(get_db)):
    """
    Get a combined intelligence overview with all four systems.

    Returns regime assessment, top playbook match, correlation status,
    and active regime shifts in a single request.
    """
    result = {
        "timestamp": get_current_time().isoformat(),
    }

    # Regime
    try:
        from modules.regime_detector import RegimeChangeDetector
        detector = RegimeChangeDetector(db)
        result["regime"] = detector.get_current_regime()
    except Exception as e:
        logger.error(f"Intelligence overview - regime error: {e}")
        result["regime"] = {"error": str(e)}

    # Playbook
    try:
        from modules.playbook_matcher import PlaybookMatcher
        matcher = PlaybookMatcher(db)
        playbook = matcher.match_episodes()
        result["playbook"] = {
            "best_match": playbook.get("best_match"),
            "match_count": len(playbook.get("matches", [])),
        }
    except Exception as e:
        logger.error(f"Intelligence overview - playbook error: {e}")
        result["playbook"] = {"error": str(e)}

    # Correlations
    try:
        from modules.correlation_tracker import CorrelationTracker
        tracker = CorrelationTracker(db)
        corr = tracker.compute_all_correlations()
        result["correlations"] = {
            "pairs_tracked": corr.get("pairs_tracked", 0),
            "breakdown_count": corr.get("breakdown_count", 0),
            "breakdowns": corr.get("breakdowns", []),
        }
    except Exception as e:
        logger.error(f"Intelligence overview - correlation error: {e}")
        result["correlations"] = {"error": str(e)}

    return result
