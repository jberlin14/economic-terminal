"""
Treasury Yields API Endpoints
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from modules.data_storage.database import get_db
from modules.yields_monitor.storage import YieldsStorage
from modules.yields_monitor.curve_builder import CurveBuilder

router = APIRouter()


@router.get("/curve")
async def get_yield_curve(
    country: str = Query(default="US"),
    db: Session = Depends(get_db)
):
    """
    Get current yield curve.
    
    Query params:
        country: Country code (default: US)
    """
    storage = YieldsStorage(db)
    curve = storage.get_latest_curve(country)
    
    if not curve:
        raise HTTPException(status_code=404, detail=f"No yield curve data for {country}")
    
    return {
        "timestamp": curve.timestamp.isoformat() if curve.timestamp else None,
        "country": curve.country,
        "curve": {
            "1M": curve.tenor_1m,
            "3M": curve.tenor_3m,
            "6M": curve.tenor_6m,
            "1Y": curve.tenor_1y,
            "2Y": curve.tenor_2y,
            "5Y": curve.tenor_5y,
            "10Y": curve.tenor_10y,
            "20Y": curve.tenor_20y,
            "30Y": curve.tenor_30y,
        },
        "spreads": {
            "10Y-2Y": curve.spread_10y2y,
            "10Y-3M": curve.spread_10y3m,
            "30Y-10Y": curve.spread_30y10y,
        },
        "tips": {
            "5Y": curve.tips_5y,
            "10Y": curve.tips_10y,
        },
        "is_inverted": curve.spread_10y2y < 0 if curve.spread_10y2y else False
    }


@router.get("/history")
async def get_yield_history(
    country: str = Query(default="US"),
    days: int = Query(default=7, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Get yield curve history.
    
    Query params:
        country: Country code
        days: Number of days of history
    """
    storage = YieldsStorage(db)
    history = storage.get_curve_history(country, days)
    
    return {
        "country": country,
        "days": days,
        "count": len(history),
        "history": [
            {
                "timestamp": h.timestamp.isoformat(),
                "10Y": h.tenor_10y,
                "2Y": h.tenor_2y,
                "spread_10y2y": h.spread_10y2y
            }
            for h in history
        ]
    }


@router.get("/spread-history")
async def get_spread_history(
    spread: str = Query(default="10y2y", regex="^(10y2y|10y3m|30y10y)$"),
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Get historical spread data for charting.
    """
    storage = YieldsStorage(db)
    history = storage.get_spread_history(spread, days)
    
    return {
        "spread": spread,
        "days": days,
        "history": history
    }


@router.get("/analysis")
async def get_curve_analysis(
    db: Session = Depends(get_db)
):
    """
    Get yield curve analysis including inversion detection.
    """
    storage = YieldsStorage(db)
    current = storage.get_latest_curve('US')
    
    if not current:
        raise HTTPException(status_code=404, detail="No yield curve data available")
    
    # Get 1-week-ago curve for comparison
    from datetime import timedelta
    week_ago_time = datetime.utcnow() - timedelta(days=7)
    historical = storage.get_curve_at_time(week_ago_time, 'US')
    
    # Build analysis
    from modules.yields_monitor.models import YieldCurveData
    
    current_data = YieldCurveData(
        country=current.country,
        timestamp=current.timestamp,
        tenor_1m=current.tenor_1m,
        tenor_3m=current.tenor_3m,
        tenor_6m=current.tenor_6m,
        tenor_1y=current.tenor_1y,
        tenor_2y=current.tenor_2y,
        tenor_5y=current.tenor_5y,
        tenor_10y=current.tenor_10y,
        tenor_20y=current.tenor_20y,
        tenor_30y=current.tenor_30y,
        spread_10y2y=current.spread_10y2y,
        spread_10y3m=current.spread_10y3m,
        spread_30y10y=current.spread_30y10y
    )
    
    summary = CurveBuilder.get_curve_summary(current_data)
    
    # Add comparison data if available
    if historical:
        summary['week_ago'] = {
            'timestamp': historical.timestamp.isoformat(),
            '10Y': historical.tenor_10y,
            '2Y': historical.tenor_2y,
            'spread_10y2y': historical.spread_10y2y
        }
        
        # Calculate change
        if current.spread_10y2y is not None and historical.spread_10y2y is not None:
            summary['spread_change_1w'] = round(
                (current.spread_10y2y - historical.spread_10y2y) * 100, 1
            )  # bps
    
    return summary


@router.get("/interpolated")
async def get_interpolated_curve(
    points: int = Query(default=50, ge=10, le=200),
    db: Session = Depends(get_db)
):
    """
    Get interpolated yield curve for smooth charting.
    """
    storage = YieldsStorage(db)
    current = storage.get_latest_curve('US')
    
    if not current:
        raise HTTPException(status_code=404, detail="No yield curve data available")
    
    from modules.yields_monitor.models import YieldCurveData
    
    current_data = YieldCurveData(
        tenor_1m=current.tenor_1m,
        tenor_3m=current.tenor_3m,
        tenor_6m=current.tenor_6m,
        tenor_1y=current.tenor_1y,
        tenor_2y=current.tenor_2y,
        tenor_5y=current.tenor_5y,
        tenor_10y=current.tenor_10y,
        tenor_20y=current.tenor_20y,
        tenor_30y=current.tenor_30y
    )
    
    interpolated = CurveBuilder.interpolate_curve(current_data, points)
    
    return {
        "timestamp": current.timestamp.isoformat() if current.timestamp else None,
        "points": len(interpolated),
        "curve": interpolated
    }
