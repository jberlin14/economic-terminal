"""
News Aggregator Module

Fetches and aggregates financial news from RSS feeds.
"""

from .models import NewsArticle, NewsFeed, NewsAlert, NewsSummary
from .rss_fetcher import RSSFetcher
from .storage import NewsStorage, store_news_feed, get_latest_news
from .article_scraper import ArticleScraper, scrape_missing_articles

__all__ = [
    'NewsArticle',
    'NewsFeed',
    'NewsAlert',
    'NewsSummary',
    'RSSFetcher',
    'NewsStorage',
    'store_news_feed',
    'get_latest_news',
    'ArticleScraper',
    'scrape_missing_articles',
]