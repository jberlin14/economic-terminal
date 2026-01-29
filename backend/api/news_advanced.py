"""
Advanced News API Endpoints

Leader detection, institution tracking, event filtering, and advanced search.
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from modules.utils.timezone import get_current_time
from sqlalchemy.orm import Session

from modules.data_storage.database import get_db
from modules.news_aggregator.search import NewsSearch
from modules.news_aggregator.leader_detector import LeaderDetector
from modules.news_aggregator.config import LEADERS, RSS_FEEDS

router = APIRouter()


@router.get("/search")
async def search_news(
    q: Optional[str] = Query(default=None, description="Free text search"),
    leaders: Optional[str] = Query(default=None, description="Comma-separated leader keys (powell,lagarde)"),
    countries: Optional[str] = Query(default=None, description="Comma-separated country codes (US,EU,MX)"),
    institutions: Optional[str] = Query(default=None, description="Comma-separated institutions (FED,ECB,WHITE_HOUSE)"),
    events: Optional[str] = Query(default=None, description="Comma-separated event types (RATE_DECISION,TRADE_POLICY)"),
    severity: Optional[str] = Query(default=None, description="Comma-separated severities (CRITICAL,HIGH)"),
    category: Optional[str] = Query(default=None, description="Comma-separated categories"),
    hours: int = Query(default=24, ge=1, le=720),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Advanced news search with multiple filter options.

    All filters are optional and can be combined.

    Examples:
        /api/news/search?leaders=powell,lagarde&severity=CRITICAL,HIGH
        /api/news/search?countries=MX&events=TRADE_POLICY&hours=48
        /api/news/search?q=tariff&institutions=WHITE_HOUSE
    """
    search = NewsSearch(db)

    # Parse comma-separated parameters
    leaders_list = leaders.split(',') if leaders else None
    countries_list = countries.split(',') if countries else None
    institutions_list = institutions.split(',') if institutions else None
    events_list = events.split(',') if events else None
    severities_list = severity.split(',') if severity else None
    categories_list = category.split(',') if category else None

    articles = search.search(
        query=q,
        leaders=leaders_list,
        countries=countries_list,
        institutions=institutions_list,
        event_types=events_list,
        severities=severities_list,
        categories=categories_list,
        hours=hours,
        limit=limit
    )

    return {
        "timestamp": get_current_time().isoformat(),
        "count": len(articles),
        "filters": {
            "query": q,
            "leaders": leaders_list,
            "countries": countries_list,
            "institutions": institutions_list,
            "events": events_list,
            "severity": severities_list,
            "category": categories_list,
            "hours": hours
        },
        "articles": articles
    }


@router.get("/leaders")
async def get_all_leaders(db: Session = Depends(get_db)):
    """
    Get list of all trackable leaders with recent mention counts.

    Returns information about all 60+ tracked world leaders.
    """
    search = NewsSearch(db)
    trending = search.get_trending_leaders(hours=168)  # Last 7 days

    # Also return all leaders even if not mentioned
    detector = LeaderDetector()
    all_leaders = []

    for key, data in LEADERS.items():
        leader_info = data.copy()
        leader_info['key'] = key
        # Check if in trending
        mentions = next((l['mentions'] for l in trending if l['key'] == key), 0)
        leader_info['recent_mentions'] = mentions
        all_leaders.append(leader_info)

    return {
        "timestamp": get_current_time().isoformat(),
        "total_leaders": len(all_leaders),
        "trending": trending[:20],  # Top 20
        "all_leaders": sorted(all_leaders, key=lambda x: x['recent_mentions'], reverse=True)
    }


@router.get("/leaders/{leader_key}")
async def get_leader_articles(
    leader_key: str,
    hours: int = Query(default=168, ge=1, le=720),  # Default 7 days
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Get all articles mentioning a specific leader.

    Examples:
        /api/news/leaders/powell
        /api/news/leaders/lagarde
        /api/news/leaders/trump
    """
    search = NewsSearch(db)
    detector = LeaderDetector()

    # Validate leader exists
    leader_info = detector.get_leader_info(leader_key)
    if not leader_info:
        raise HTTPException(status_code=404, detail=f"Leader '{leader_key}' not found")

    articles = search.get_by_leader(leader_key, hours=hours, limit=limit)

    return {
        "timestamp": get_current_time().isoformat(),
        "leader": leader_info,
        "count": len(articles),
        "articles": articles
    }


@router.get("/institutions/{institution}")
async def get_institution_articles(
    institution: str,
    hours: int = Query(default=168, ge=1, le=720),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Get articles by institution (FED, ECB, WHITE_HOUSE, etc).

    Examples:
        /api/news/institutions/FED
        /api/news/institutions/ECB
        /api/news/institutions/WHITE_HOUSE
    """
    search = NewsSearch(db)
    articles = search.get_by_institution(institution.upper(), hours=hours, limit=limit)

    return {
        "timestamp": get_current_time().isoformat(),
        "institution": institution.upper(),
        "count": len(articles),
        "articles": articles
    }


@router.get("/events/{event_type}")
async def get_event_articles(
    event_type: str,
    hours: int = Query(default=168, ge=1, le=720),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Get articles by event type.

    Event types:
        RATE_DECISION, TRADE_POLICY, SANCTIONS, MILITARY, ELECTION,
        ECONOMIC_DATA, MARKET_MOVE, CURRENCY, DEBT_CREDIT, DISASTER

    Examples:
        /api/news/events/RATE_DECISION
        /api/news/events/TRADE_POLICY
        /api/news/events/MILITARY
    """
    search = NewsSearch(db)
    articles = search.get_by_event_type(event_type.upper(), hours=hours, limit=limit)

    return {
        "timestamp": get_current_time().isoformat(),
        "event_type": event_type.upper(),
        "count": len(articles),
        "articles": articles
    }


@router.get("/countries/{country}/critical")
async def get_critical_by_country(
    country: str,
    hours: int = Query(default=168, ge=1, le=720),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Get critical/high severity articles for a specific country.

    Examples:
        /api/news/countries/US/critical
        /api/news/countries/MX/critical
        /api/news/countries/EU/critical
    """
    search = NewsSearch(db)
    articles = search.get_critical_by_country(country.upper(), hours=hours, limit=limit)

    return {
        "timestamp": get_current_time().isoformat(),
        "country": country.upper(),
        "count": len(articles),
        "articles": articles
    }


@router.get("/dashboard")
async def get_news_dashboard(
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive dashboard summary.

    Includes:
    - Counts by severity, country, institution
    - Active leaders with mention counts
    - Top event types
    - Latest critical articles
    - Trending leaders and events
    """
    search = NewsSearch(db)
    summary = search.get_dashboard_summary(hours=hours)

    # Add trending data
    trending_leaders = search.get_trending_leaders(hours=hours)
    trending_events = search.get_trending_events(hours=hours)

    return {
        "timestamp": get_current_time().isoformat(),
        "hours": hours,
        "summary": summary,
        "trending_leaders": trending_leaders[:10],
        "trending_events": trending_events[:10]
    }


@router.get("/timeline/{leader_key}")
async def get_leader_timeline(
    leader_key: str,
    hours: int = Query(default=168, ge=1, le=720),
    db: Session = Depends(get_db)
):
    """
    Get chronological timeline of articles mentioning a leader.

    Returns articles sorted by publish date for timeline visualization.
    """
    search = NewsSearch(db)
    detector = LeaderDetector()

    # Validate leader exists
    leader_info = detector.get_leader_info(leader_key)
    if not leader_info:
        raise HTTPException(status_code=404, detail=f"Leader '{leader_key}' not found")

    timeline = search.get_leader_timeline(leader_key, hours=hours)

    return {
        "timestamp": get_current_time().isoformat(),
        "leader": leader_info,
        "count": len(timeline),
        "timeline": timeline
    }


@router.get("/stats")
async def get_news_stats(db: Session = Depends(get_db)):
    """
    Get overall news aggregation statistics.

    Returns:
    - Total feeds configured
    - Total leaders tracked
    - Recent article counts
    - System configuration
    """
    search = NewsSearch(db)

    # Get basic stats
    recent_24h = search.get_dashboard_summary(hours=24)
    recent_7d = search.get_dashboard_summary(hours=168)

    return {
        "timestamp": get_current_time().isoformat(),
        "configuration": {
            "total_rss_feeds": len(RSS_FEEDS),
            "total_leaders": len(LEADERS),
            "total_institutions": len(set(l['institution'] for l in LEADERS.values())),
            "countries_covered": len(set(c for l in LEADERS.values() for c in l['countries']))
        },
        "last_24_hours": {
            "total_articles": recent_24h['total_articles'],
            "critical_count": recent_24h['critical_count'],
            "high_count": recent_24h['high_count']
        },
        "last_7_days": {
            "total_articles": recent_7d['total_articles'],
            "critical_count": recent_7d['critical_count'],
            "high_count": recent_7d['high_count']
        }
    }
