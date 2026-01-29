"""
Economic Calendar API Endpoints

Provides access to upcoming economic releases and historical data.
"""

from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from loguru import logger

from modules.utils.timezone import get_current_time
from modules.economic_calendar import EconomicCalendar, CalendarStorage, TRACKED_RELEASES

router = APIRouter()

# Initialize calendar
calendar = EconomicCalendar()
storage = CalendarStorage()


@router.get("/")
async def get_calendar_summary():
    """
    Get economic calendar summary with upcoming releases.

    Returns releases grouped by this week and next week.
    """
    if not calendar.is_available():
        logger.warning("FRED API not available for calendar")

    summary = calendar.get_calendar_summary()
    summary["timestamp"] = get_current_time().isoformat()

    return summary


@router.get("/upcoming")
async def get_upcoming_releases(
    days: int = Query(14, description="Days ahead to look", ge=1, le=60),
    importance: Optional[str] = Query(None, description="Filter by importance: high, medium, low")
):
    """
    Get list of upcoming economic releases.

    Args:
        days: Number of days ahead to look (default 14)
        importance: Filter by importance level

    Returns:
        List of upcoming releases with dates and previous values
    """
    releases = calendar.get_upcoming_releases(days_ahead=days)

    # Filter by importance if specified
    if importance:
        releases = [r for r in releases if r.importance.value == importance.lower()]

    return {
        "timestamp": get_current_time().isoformat(),
        "days_ahead": days,
        "count": len(releases),
        "releases": [calendar._release_to_dict(r) for r in releases]
    }


@router.get("/releases")
async def get_all_tracked_releases():
    """
    Get list of all tracked economic releases.

    Returns metadata about each tracked release.
    """
    releases = []
    for release_id, release in TRACKED_RELEASES.items():
        releases.append({
            "id": release.id,
            "name": release.name,
            "series_id": release.series_id,
            "importance": release.importance.value,
            "typical_time": release.typical_time,
            "frequency": release.frequency,
            "description": release.description
        })

    # Sort by importance
    importance_order = {"high": 0, "medium": 1, "low": 2}
    releases.sort(key=lambda r: importance_order.get(r["importance"], 3))

    return {
        "timestamp": get_current_time().isoformat(),
        "count": len(releases),
        "releases": releases
    }


@router.get("/release/{release_id}")
async def get_release_detail(release_id: str):
    """
    Get detailed information about a specific release.

    Includes history and upcoming schedule.
    """
    if release_id not in TRACKED_RELEASES:
        raise HTTPException(status_code=404, detail=f"Release '{release_id}' not found")

    release = TRACKED_RELEASES[release_id]
    history = calendar.get_release_history(release_id, limit=12)

    # Get upcoming instance
    upcoming = calendar.get_upcoming_releases(days_ahead=60)
    next_release = next((r for r in upcoming if r.id == release_id), None)

    return {
        "timestamp": get_current_time().isoformat(),
        "release": {
            "id": release.id,
            "name": release.name,
            "series_id": release.series_id,
            "importance": release.importance.value,
            "typical_time": release.typical_time,
            "frequency": release.frequency,
            "description": release.description
        },
        "next_release": calendar._release_to_dict(next_release) if next_release else None,
        "history": history
    }


@router.get("/this-week")
async def get_this_week_releases():
    """
    Get releases scheduled for this week.
    """
    releases = calendar.get_upcoming_releases(days_ahead=7)

    # Only include high and medium importance
    important = [r for r in releases if r.importance.value in ["high", "medium"]]

    return {
        "timestamp": get_current_time().isoformat(),
        "week_of": date.today().isoformat(),
        "count": len(important),
        "releases": [calendar._release_to_dict(r) for r in important]
    }


@router.post("/consensus/{release_id}")
async def set_consensus_estimate(
    release_id: str,
    release_date: str = Query(..., description="Release date YYYY-MM-DD"),
    estimate: float = Query(..., description="Consensus estimate value")
):
    """
    Set consensus estimate for an upcoming release.

    This can be used to manually input consensus estimates.
    """
    if release_id not in TRACKED_RELEASES:
        raise HTTPException(status_code=404, detail=f"Release '{release_id}' not found")

    try:
        parsed_date = datetime.strptime(release_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    storage.set_consensus(release_id, parsed_date, estimate)

    return {
        "status": "success",
        "release_id": release_id,
        "release_date": release_date,
        "estimate": estimate,
        "timestamp": get_current_time().isoformat()
    }
