"""
News API Endpoints
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from modules.data_storage.database import get_db
from modules.data_storage.queries import QueryHelper
from modules.news_aggregator.search import NewsSearch
from modules.news_aggregator.leader_detector import LeaderDetector
from modules.utils.timezone import get_current_time

router = APIRouter()


@router.get("/recent")
async def get_recent_news(
    hours: int = Query(default=24, ge=1, le=168),
    severity: Optional[str] = Query(default=None, pattern="^(CRITICAL|HIGH|MEDIUM|LOW)$"),
    category: Optional[str] = Query(default=None, pattern="^(ECON|FX|POLITICAL|CREDIT|CENTRAL_BANK|GEOPOLITICAL|GENERAL)$"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Get recent news articles.
    
    Query params:
        hours: How far back to look
        severity: Filter by severity (CRITICAL, HIGH, MEDIUM, LOW)
        category: Filter by category (ECON, FX, POLITICAL, CREDIT, CAT)
        limit: Maximum articles to return
    """
    helper = QueryHelper(db)
    articles = helper.get_recent_news(
        hours=hours,
        severity=severity,
        category=category,
        limit=limit
    )
    
    return {
        "timestamp": get_current_time().isoformat(),
        "hours": hours,
        "count": len(articles),
        "articles": [a.to_dict() for a in articles]
    }


@router.get("/critical")
async def get_critical_news(
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db)
):
    """
    Get critical severity news only.
    """
    helper = QueryHelper(db)
    articles = helper.get_critical_news(hours=hours)
    
    return {
        "timestamp": get_current_time().isoformat(),
        "count": len(articles),
        "articles": [a.to_dict() for a in articles]
    }


@router.get("/by-country/{country}")
async def get_news_by_country(
    country: str,
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get news filtered by country.
    """
    helper = QueryHelper(db)
    articles = helper.get_news_by_country(
        country=country.upper(),
        hours=hours,
        limit=limit
    )
    
    return {
        "country": country.upper(),
        "count": len(articles),
        "articles": [a.to_dict() for a in articles]
    }


@router.get("/summary")
async def get_news_summary(
    hours: int = Query(default=24),
    db: Session = Depends(get_db)
):
    """
    Get news summary with counts by category and severity.
    """
    helper = QueryHelper(db)
    articles = helper.get_recent_news(hours=hours, limit=200)
    
    # Count by severity
    by_severity = {}
    by_category = {}
    by_country = {}
    
    for article in articles:
        # Severity
        sev = article.severity or 'UNKNOWN'
        by_severity[sev] = by_severity.get(sev, 0) + 1
        
        # Category
        cat = article.category or 'UNKNOWN'
        by_category[cat] = by_category.get(cat, 0) + 1
        
        # Country
        for country in (article.country_tags or []):
            by_country[country] = by_country.get(country, 0) + 1
    
    return {
        "timestamp": get_current_time().isoformat(),
        "hours": hours,
        "total": len(articles),
        "by_severity": by_severity,
        "by_category": by_category,
        "by_country": by_country,
        "top_stories": [a.to_dict() for a in articles[:5]]
    }
