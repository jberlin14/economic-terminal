"""
Credit Spreads API Endpoints
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from modules.utils.timezone import get_current_time
from sqlalchemy.orm import Session

from modules.data_storage.database import get_db
from modules.data_storage.queries import QueryHelper

router = APIRouter()


@router.get("/spreads")
async def get_credit_spreads(db: Session = Depends(get_db)):
    """
    Get latest credit spreads for all indices.
    """
    helper = QueryHelper(db)
    spreads = helper.get_latest_credit_spreads()
    
    return {
        "timestamp": get_current_time().isoformat(),
        "count": len(spreads),
        "spreads": [s.to_dict() for s in spreads]
    }


@router.get("/spreads/{index}")
async def get_credit_spread(
    index: str,
    db: Session = Depends(get_db)
):
    """
    Get spread for a specific credit index.
    """
    helper = QueryHelper(db)
    spreads = helper.get_latest_credit_spreads()
    
    for s in spreads:
        if s.index_name.lower() == index.lower():
            return s.to_dict()
    
    raise HTTPException(status_code=404, detail=f"Index {index} not found")


@router.get("/history/{index}")
async def get_spread_history(
    index: str,
    days: int = Query(default=90, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Get historical spreads for an index.
    """
    helper = QueryHelper(db)
    history = helper.get_credit_spread_history(index, days)
    
    return {
        "index": index,
        "days": days,
        "count": len(history),
        "history": [
            {
                "timestamp": h.timestamp.isoformat(),
                "spread_bps": h.spread_bps,
                "percentile_90d": h.percentile_90d
            }
            for h in history
        ]
    }


@router.get("/summary")
async def get_credit_summary(db: Session = Depends(get_db)):
    """
    Get credit market summary.
    """
    helper = QueryHelper(db)
    spreads = helper.get_latest_credit_spreads()
    
    # Find HY and IG
    hy_spread = None
    ig_spread = None
    
    for s in spreads:
        if 'HY' in s.index_name.upper() or 'HIGH YIELD' in s.index_name.upper():
            hy_spread = s
        elif 'IG' in s.index_name.upper() or 'BBB' in s.index_name.upper():
            ig_spread = s
    
    return {
        "timestamp": get_current_time().isoformat(),
        "investment_grade": ig_spread.to_dict() if ig_spread else None,
        "high_yield": hy_spread.to_dict() if hy_spread else None,
        "all_spreads": [s.to_dict() for s in spreads],
        "market_status": _assess_credit_status(spreads)
    }


def _assess_credit_status(spreads) -> str:
    """Assess overall credit market status."""
    for s in spreads:
        if s.percentile_90d and s.percentile_90d >= 95:
            return "STRESSED"
        if s.percentile_90d and s.percentile_90d >= 90:
            return "ELEVATED"
    return "NORMAL"
