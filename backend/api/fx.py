"""
FX Rate API Endpoints
"""

from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from modules.utils.timezone import get_current_time
from sqlalchemy.orm import Session

from modules.data_storage.database import get_db
from modules.fx_monitor.storage import FXStorage

router = APIRouter()


@router.get("/rates")
async def get_fx_rates(db: Session = Depends(get_db)):
    """
    Get latest FX rates for all currency pairs.
    """
    storage = FXStorage(db)
    rates = storage.get_latest_rates()
    
    return {
        "timestamp": get_current_time().isoformat(),
        "count": len(rates),
        "rates": [
            {
                "pair": r.pair,
                "rate": r.rate,
                "change_1h": r.change_1h,
                "change_24h": r.change_24h,
                "change_1w": r.change_1w,
                "change_ytd": r.change_ytd,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "sparkline": r.sparkline_data or []
            }
            for r in rates
        ]
    }


@router.get("/rates/{pair}")
async def get_fx_rate(
    pair: str,
    db: Session = Depends(get_db)
):
    """
    Get rate for a specific currency pair.
    
    Path params:
        pair: Currency pair (e.g., USD-EUR, use dash instead of slash)
    """
    # Convert dash to slash
    pair_formatted = pair.replace('-', '/')
    
    storage = FXStorage(db)
    rates = storage.get_latest_rates()
    
    for r in rates:
        if r.pair == pair_formatted:
            return {
                "pair": r.pair,
                "rate": r.rate,
                "change_1h": r.change_1h,
                "change_24h": r.change_24h,
                "change_1w": r.change_1w,
                "change_ytd": r.change_ytd,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "sparkline": r.sparkline_data or []
            }
    
    raise HTTPException(status_code=404, detail=f"Pair {pair_formatted} not found")


@router.get("/history/{pair}")
async def get_fx_history(
    pair: str,
    hours: int = Query(default=24, ge=1, le=720),
    db: Session = Depends(get_db)
):
    """
    Get historical rates for a currency pair.
    
    Path params:
        pair: Currency pair (use dash instead of slash)
    Query params:
        hours: Number of hours of history (1-720, default 24)
    """
    pair_formatted = pair.replace('-', '/')
    
    storage = FXStorage(db)
    history = storage.get_rate_history(pair_formatted, hours)
    
    return {
        "pair": pair_formatted,
        "hours": hours,
        "count": len(history),
        "history": [
            {
                "rate": h.rate,
                "timestamp": h.timestamp.isoformat()
            }
            for h in history
        ]
    }


@router.get("/summary")
async def get_fx_summary(db: Session = Depends(get_db)):
    """
    Get FX market summary with movers and alerts.
    """
    storage = FXStorage(db)
    summary = storage.get_rate_summary()
    
    return summary


@router.get("/movers")
async def get_top_movers(
    period: str = Query(default="24h", pattern="^(1h|24h|1w)$"),
    db: Session = Depends(get_db)
):
    """
    Get biggest FX movers.
    
    Query params:
        period: Time period (1h, 24h, 1w)
    """
    storage = FXStorage(db)
    rates = storage.get_latest_rates()
    
    change_key = {
        '1h': 'change_1h',
        '24h': 'change_24h',
        '1w': 'change_1w'
    }[period]
    
    # Filter rates with valid change data
    valid_rates = [r for r in rates if getattr(r, change_key) is not None]
    
    # Sort by absolute change
    sorted_rates = sorted(valid_rates, key=lambda r: abs(getattr(r, change_key) or 0), reverse=True)
    
    return {
        "period": period,
        "movers": [
            {
                "pair": r.pair,
                "rate": r.rate,
                "change": getattr(r, change_key),
                "direction": "up" if (getattr(r, change_key) or 0) > 0 else "down"
            }
            for r in sorted_rates[:5]
        ]
    }
