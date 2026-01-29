"""
News Storage Module

Handles database operations for news articles with deduplication.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import desc, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from loguru import logger

from ..data_storage.schema import NewsArticle as NewsArticleDB
from ..data_storage.database import get_db_context
from ..utils.timezone import get_current_time
from .models import NewsArticle, NewsFeed


class NewsStorage:
    """
    Database storage handler for news articles.
    """

    def __init__(self, db: Optional[Session] = None):
        self._db = db

    def _get_db(self) -> Session:
        if self._db:
            return self._db
        raise RuntimeError("No database session provided")

    def store_article(self, article: NewsArticle) -> Optional[NewsArticleDB]:
        """
        Store a single news article with deduplication.

        Returns:
            NewsArticleDB if stored, None if duplicate
        """
        db = self._get_db()

        # Check if article already exists by content hash
        existing = (
            db.query(NewsArticleDB)
            .filter(NewsArticleDB.content_hash == article.content_hash)
            .first()
        )

        if existing:
            logger.debug(f"Duplicate article skipped: {article.headline[:50]}...")
            return None

        try:
            news_article = NewsArticleDB(
                headline=article.headline,
                source=article.source,
                url=article.url,
                published_at=article.published_at,
                fetched_at=get_current_time(),
                country_tags=article.country_tags,
                category=article.category,
                severity=article.severity,
                content_hash=article.content_hash,
                summary=article.summary,
                relevance_score=article.relevance_score,
                keyword_matches=article.keyword_matches,
                # New fields from leader detection
                leader_mentions=article.leader_mentions,
                institutions=article.institutions,
                event_types=article.event_types,
                action_words=article.action_words,
                processed=False,
                alert_generated=False
            )

            db.add(news_article)
            db.commit()
            db.refresh(news_article)

            logger.debug(f"Stored article: {article.headline[:50]}...")
            return news_article

        except IntegrityError as e:
            db.rollback()
            logger.warning(f"Duplicate article (integrity error): {article.headline[:50]}...")
            return None
        except Exception as e:
            db.rollback()
            logger.error(f"Error storing article: {e}")
            return None

    def store_feed(self, feed: NewsFeed) -> Dict[str, int]:
        """
        Store a batch of news articles.

        Returns:
            Dictionary with counts (stored, duplicates, errors)
        """
        counts = {
            'stored': 0,
            'duplicates': 0,
            'errors': 0
        }

        for article in feed.articles:
            try:
                result = self.store_article(article)
                if result:
                    counts['stored'] += 1
                else:
                    counts['duplicates'] += 1
            except Exception as e:
                counts['errors'] += 1
                logger.error(f"Error storing article: {e}")

        logger.info(f"Feed {feed.source}: {counts['stored']} stored, {counts['duplicates']} duplicates, {counts['errors']} errors")
        return counts

    def get_recent_news(
        self,
        hours: int = 24,
        limit: int = 20,
        severity: Optional[str] = None
    ) -> List[NewsArticleDB]:
        """Get recent news articles."""
        db = self._get_db()
        cutoff = get_current_time() - timedelta(hours=hours)

        query = (
            db.query(NewsArticleDB)
            .filter(NewsArticleDB.published_at >= cutoff)
        )

        if severity:
            query = query.filter(NewsArticleDB.severity == severity)

        return (
            query
            .order_by(desc(NewsArticleDB.published_at))
            .limit(limit)
            .all()
        )

    def get_critical_news(self, hours: int = 24) -> List[NewsArticleDB]:
        """Get critical news articles."""
        return self.get_recent_news(hours=hours, severity='CRITICAL', limit=10)

    def get_news_by_country(
        self,
        country: str,
        hours: int = 24,
        limit: int = 10
    ) -> List[NewsArticleDB]:
        """Get news articles for a specific country."""
        db = self._get_db()
        cutoff = get_current_time() - timedelta(hours=hours)

        return (
            db.query(NewsArticleDB)
            .filter(NewsArticleDB.published_at >= cutoff)
            .filter(NewsArticleDB.country_tags.contains([country]))
            .order_by(desc(NewsArticleDB.published_at))
            .limit(limit)
            .all()
        )

    def get_news_by_source(
        self,
        source: str,
        hours: int = 24,
        limit: int = 10
    ) -> List[NewsArticleDB]:
        """Get news articles from a specific source."""
        db = self._get_db()
        cutoff = get_current_time() - timedelta(hours=hours)

        return (
            db.query(NewsArticleDB)
            .filter(NewsArticleDB.source == source)
            .filter(NewsArticleDB.published_at >= cutoff)
            .order_by(desc(NewsArticleDB.published_at))
            .limit(limit)
            .all()
        )

    def cleanup_old_news(self, days: int = 30) -> int:
        """Remove news older than specified days."""
        db = self._get_db()
        cutoff = get_current_time() - timedelta(days=days)

        deleted = (
            db.query(NewsArticleDB)
            .filter(NewsArticleDB.published_at < cutoff)
            .delete()
        )

        db.commit()
        logger.info(f"Cleaned up {deleted} old news articles")
        return deleted


def store_news_feed(feed: NewsFeed) -> Dict[str, int]:
    """Convenience function with context manager."""
    with get_db_context() as db:
        storage = NewsStorage(db)
        return storage.store_feed(feed)


def get_latest_news(hours: int = 24, limit: int = 20) -> List[Dict[str, Any]]:
    """Get latest news as list of dictionaries."""
    with get_db_context() as db:
        storage = NewsStorage(db)
        articles = storage.get_recent_news(hours=hours, limit=limit)

        return [article.to_dict() for article in articles]