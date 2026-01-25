"""
News Search and Filtering

Advanced search functionality for news articles with multiple filter options.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from loguru import logger

from modules.data_storage.schema import NewsArticle
from .leader_detector import LeaderDetector


class NewsSearch:
    """
    Advanced search and filtering for news articles.
    """

    def __init__(self, db_session: Session):
        self.db = db_session
        self.detector = LeaderDetector()

    def search(
        self,
        query: Optional[str] = None,           # Free text search
        leaders: Optional[List[str]] = None,    # ['powell', 'lagarde']
        countries: Optional[List[str]] = None,  # ['US', 'EU', 'MX']
        institutions: Optional[List[str]] = None,  # ['FED', 'ECB', 'WHITE_HOUSE']
        event_types: Optional[List[str]] = None,   # ['RATE_DECISION', 'TRADE_POLICY']
        severities: Optional[List[str]] = None,    # ['CRITICAL', 'HIGH']
        categories: Optional[List[str]] = None,    # ['POLITICAL', 'CENTRAL_BANK']
        hours: int = 24,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search articles with multiple filters (all optional and combinable).

        Returns:
            List of article dicts
        """
        # Start with base query
        base_query = self.db.query(NewsArticle)

        # Time filter
        if hours > 0:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            base_query = base_query.filter(NewsArticle.published_at >= cutoff)

        # Free text search (headline or summary)
        if query:
            search_pattern = f"%{query}%"
            base_query = base_query.filter(
                or_(
                    NewsArticle.headline.ilike(search_pattern),
                    NewsArticle.summary.ilike(search_pattern)
                )
            )

        # Leader filter (JSON contains)
        if leaders:
            # Filter where leader_mentions contains any of the specified leaders
            leader_filters = []
            for leader in leaders:
                leader_filters.append(
                    NewsArticle.leader_mentions.contains([leader])
                )
            base_query = base_query.filter(or_(*leader_filters))

        # Country filter
        if countries:
            country_filters = []
            for country in countries:
                country_filters.append(
                    NewsArticle.country_tags.contains([country])
                )
            base_query = base_query.filter(or_(*country_filters))

        # Institution filter
        if institutions:
            institution_filters = []
            for institution in institutions:
                institution_filters.append(
                    NewsArticle.institutions.contains([institution])
                )
            base_query = base_query.filter(or_(*institution_filters))

        # Event type filter
        if event_types:
            event_filters = []
            for event_type in event_types:
                event_filters.append(
                    NewsArticle.event_types.contains([event_type])
                )
            base_query = base_query.filter(or_(*event_filters))

        # Severity filter
        if severities:
            base_query = base_query.filter(NewsArticle.severity.in_(severities))

        # Category filter
        if categories:
            base_query = base_query.filter(NewsArticle.category.in_(categories))

        # Order by published date (most recent first)
        base_query = base_query.order_by(NewsArticle.published_at.desc())

        # Limit results
        results = base_query.limit(limit).all()

        # Convert to dicts
        return [article.to_dict() for article in results]

    def get_by_leader(self, leader_key: str, hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get all articles mentioning a specific leader.

        Args:
            leader_key: Leader key (e.g., 'powell')
            hours: Hours to look back
            limit: Maximum results

        Returns:
            List of article dicts
        """
        return self.search(leaders=[leader_key], hours=hours, limit=limit)

    def get_by_institution(self, institution: str, hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get all articles about a specific institution.

        Args:
            institution: Institution name (e.g., 'FED', 'ECB')
            hours: Hours to look back
            limit: Maximum results

        Returns:
            List of article dicts
        """
        return self.search(institutions=[institution], hours=hours, limit=limit)

    def get_by_event_type(self, event_type: str, hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get all articles of a specific event type.

        Args:
            event_type: Event type (e.g., 'RATE_DECISION', 'TRADE_POLICY')
            hours: Hours to look back
            limit: Maximum results

        Returns:
            List of article dicts
        """
        return self.search(event_types=[event_type], hours=hours, limit=limit)

    def get_critical_by_country(self, country: str, hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get critical/high severity articles for a country.

        Args:
            country: Country code (e.g., 'US', 'MX')
            hours: Hours to look back
            limit: Maximum results

        Returns:
            List of article dicts
        """
        return self.search(
            countries=[country],
            severities=['CRITICAL', 'HIGH'],
            hours=hours,
            limit=limit
        )

    def get_dashboard_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get summary statistics for dashboard.

        Args:
            hours: Hours to look back

        Returns:
            Summary dict with counts, top leaders, institutions, etc.
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        # Get all recent articles
        articles = self.db.query(NewsArticle).filter(
            NewsArticle.published_at >= cutoff
        ).all()

        # Count by severity
        critical_count = sum(1 for a in articles if a.severity == 'CRITICAL')
        high_count = sum(1 for a in articles if a.severity == 'HIGH')

        # Count by country
        by_country = {}
        for article in articles:
            for country in (article.country_tags or []):
                by_country[country] = by_country.get(country, 0) + 1

        # Count by institution
        by_institution = {}
        for article in articles:
            for inst in (article.institutions or []):
                by_institution[inst] = by_institution.get(inst, 0) + 1

        # Count leader mentions
        leader_mentions = {}
        for article in articles:
            for leader in (article.leader_mentions or []):
                leader_mentions[leader] = leader_mentions.get(leader, 0) + 1

        # Top leaders (sorted by mentions)
        active_leaders = [
            {'key': key, 'mentions': count}
            for key, count in sorted(leader_mentions.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        # Top events
        event_counts = {}
        for article in articles:
            for event in (article.event_types or []):
                event_counts[event] = event_counts.get(event, 0) + 1

        top_events = sorted(event_counts.keys(), key=lambda x: event_counts[x], reverse=True)[:5]

        # Latest critical articles
        critical_articles = [
            a.to_dict() for a in articles
            if a.severity == 'CRITICAL'
        ][:5]

        return {
            'total_articles': len(articles),
            'critical_count': critical_count,
            'high_count': high_count,
            'by_country': by_country,
            'by_institution': by_institution,
            'active_leaders': active_leaders,
            'top_events': top_events,
            'latest_critical': critical_articles
        }

    def get_leader_timeline(self, leader_key: str, hours: int = 168) -> List[Dict[str, Any]]:
        """
        Get timeline of articles mentioning a leader.

        Args:
            leader_key: Leader key
            hours: Hours to look back (default: 7 days)

        Returns:
            List of article dicts sorted by date
        """
        articles = self.get_by_leader(leader_key, hours=hours, limit=100)
        return sorted(articles, key=lambda x: x['published_at'], reverse=True)

    def get_trending_leaders(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get leaders with most mentions in recent articles.

        Args:
            hours: Hours to look back

        Returns:
            List of dicts with leader info and mention counts
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        articles = self.db.query(NewsArticle).filter(
            NewsArticle.published_at >= cutoff
        ).all()

        leader_mentions = {}
        for article in articles:
            for leader in (article.leader_mentions or []):
                leader_mentions[leader] = leader_mentions.get(leader, 0) + 1

        # Sort by mentions
        trending = []
        for leader_key, count in sorted(leader_mentions.items(), key=lambda x: x[1], reverse=True)[:10]:
            leader_info = self.detector.get_leader_info(leader_key)
            if leader_info:
                leader_info['mentions'] = count
                trending.append(leader_info)

        return trending

    def get_trending_events(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get event types with most articles.

        Args:
            hours: Hours to look back

        Returns:
            List of dicts with event type and counts
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        articles = self.db.query(NewsArticle).filter(
            NewsArticle.published_at >= cutoff
        ).all()

        event_counts = {}
        for article in articles:
            for event in (article.event_types or []):
                event_counts[event] = event_counts.get(event, 0) + 1

        return [
            {'event_type': event, 'count': count}
            for event, count in sorted(event_counts.items(), key=lambda x: x[1], reverse=True)
        ]