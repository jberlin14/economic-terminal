"""
Treasury Yields API Endpoints
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from modules.utils.timezone import get_current_time
from sqlalchemy.orm import Session

from modules.data_storage.database import get_db
from modules.yields_monitor.storage import YieldsStorage
from modules.yields_monitor.curve_builder import CurveBuilder

router = APIRouter()

# Mapping from horizon string to timedelta
HORIZON_MAP = {
    '1h': timedelta(hours=1),
    '6h': timedelta(hours=6),
    '1d': timedelta(days=1),
    '1w': timedelta(weeks=1),
    '1m': timedelta(days=30),
    '3m': timedelta(days=90),
    '6m': timedelta(days=182),
    '1y': timedelta(days=365),
    '5y': timedelta(days=1825),
    '10y': timedelta(days=3650),
}

TENOR_ATTRS = [
    ('1M', 'tenor_1m'),
    ('3M', 'tenor_3m'),
    ('6M', 'tenor_6m'),
    ('1Y', 'tenor_1y'),
    ('2Y', 'tenor_2y'),
    ('5Y', 'tenor_5y'),
    ('10Y', 'tenor_10y'),
    ('20Y', 'tenor_20y'),
    ('30Y', 'tenor_30y'),
]


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
    spread: str = Query(default="10y2y", pattern="^(10y2y|10y3m|30y10y)$"),
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
    week_ago_time = get_current_time() - timedelta(days=7)
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


@router.get("/history-table")
async def get_yield_history_table(
    horizon: str = Query(default="1d", pattern="^(1h|6h|1d|1w|1m|3m|6m|1y|5y|10y)$"),
    db: Session = Depends(get_db)
):
    """
    Get current yields with changes over a selected time horizon.

    Returns all 9 tenors + 10Y-2Y spread with current values and
    basis-point changes relative to the historical point.
    """
    storage = YieldsStorage(db)
    current = storage.get_latest_curve('US')

    if not current:
        raise HTTPException(status_code=404, detail="No yield curve data available")

    delta = HORIZON_MAP.get(horizon, timedelta(days=1))
    target_time = get_current_time() - delta
    historical = storage.get_curve_at_time(target_time, 'US')

    tenors = []
    for label, attr in TENOR_ATTRS:
        cur_val = getattr(current, attr, None)
        change_bps = None
        if historical and cur_val is not None:
            hist_val = getattr(historical, attr, None)
            if hist_val is not None:
                change_bps = round((cur_val - hist_val) * 100, 1)
        tenors.append({
            "label": label,
            "value": cur_val,
            "change_bps": change_bps,
        })

    # 10Y-2Y spread
    cur_spread = current.spread_10y2y
    spread_change_bps = None
    if historical and cur_spread is not None and historical.spread_10y2y is not None:
        spread_change_bps = round((cur_spread - historical.spread_10y2y) * 100, 1)

    return {
        "horizon": horizon,
        "timestamp": current.timestamp.isoformat() if current.timestamp else None,
        "historical_timestamp": historical.timestamp.isoformat() if historical and historical.timestamp else None,
        "tenors": tenors,
        "spread_10y2y": {
            "value": cur_spread,
            "value_bps": round(cur_spread * 100, 1) if cur_spread is not None else None,
            "change_bps": spread_change_bps,
        },
    }


# Mapping from tenor label to DB attribute
TENOR_ATTR_MAP = {label: attr for label, attr in TENOR_ATTRS}


@router.get("/tenor-chart")
async def get_tenor_chart(
    tenor: str = Query(default="10Y", pattern="^(1M|3M|6M|1Y|2Y|5Y|10Y|20Y|30Y|spread_10y2y)$"),
    horizon: str = Query(default="1m", pattern="^(1d|1w|1m|3m|6m|1y|2y|5y|10y)$"),
    db: Session = Depends(get_db)
):
    """
    Get time-series data for a single tenor or spread, for charting.

    Returns an array of {date, value} points over the requested horizon.
    """
    from modules.data_storage.schema import YieldCurve as YieldCurveModel
    from sqlalchemy import asc

    delta = HORIZON_MAP.get(horizon, timedelta(days=30))
    cutoff = get_current_time() - delta

    # Determine which DB attribute to extract
    if tenor == 'spread_10y2y':
        attr = 'spread_10y2y'
    else:
        attr = TENOR_ATTR_MAP.get(tenor)
        if not attr:
            raise HTTPException(status_code=400, detail=f"Unknown tenor: {tenor}")

    # Query yield curve records in the time range
    curves = (
        db.query(YieldCurveModel)
        .filter(YieldCurveModel.country == 'US')
        .filter(YieldCurveModel.timestamp >= cutoff)
        .order_by(asc(YieldCurveModel.timestamp))
        .all()
    )

    # For longer horizons, thin the data to ~one point per day to avoid
    # sending thousands of intraday records
    points = []
    seen_dates = set()
    for curve in curves:
        val = getattr(curve, attr, None)
        if val is None:
            continue
        ts = curve.timestamp
        date_key = ts.date()

        # For horizons > 1 week, keep only one point per day
        if delta > timedelta(weeks=1):
            if date_key in seen_dates:
                continue
            seen_dates.add(date_key)

        points.append({
            "date": ts.isoformat(),
            "value": round(val, 4) if tenor != 'spread_10y2y' else round(val * 100, 1),
        })

    # Current value
    current_val = None
    if points:
        current_val = points[-1]["value"]

    # Change from start of period
    change = None
    if len(points) >= 2:
        change = round(points[-1]["value"] - points[0]["value"], 2)

    return {
        "tenor": tenor,
        "horizon": horizon,
        "current": current_val,
        "change": change,
        "unit": "bps" if tenor == "spread_10y2y" else "%",
        "points": points,
    }
