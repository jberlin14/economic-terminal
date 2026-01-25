"""
RSS Feed Fetcher

Fetches and parses RSS feeds from financial news sources.
"""

import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from loguru import logger

try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False
    logger.warning("feedparser not installed. Run: pip install feedparser")

from .models import NewsArticle, NewsFeed


# RSS Feed sources (no API key required)
RSS_FEEDS = {
    'bloomberg': 'https://feeds.bloomberg.com/markets/news.rss',
    'cnbc': 'https://www.cnbc.com/id/20910258/device/rss/rss.html',
    'yahoo': 'https://finance.yahoo.com/news/rssindex'
}

# Country keywords for tagging
COUNTRY_KEYWORDS = {
    'US': ['united states', 'u.s.', 'usa', 'america', 'federal reserve', 'fed', 'treasury', 'dollar', 'washington', 'white house'],
    'JP': ['japan', 'japanese', 'tokyo', 'yen', 'boj', 'bank of japan', 'nikkei'],
    'CA': ['canada', 'canadian', 'ottawa', 'cad', 'bank of canada'],
    'MX': ['mexico', 'mexican', 'peso', 'banxico'],
    'EU': ['europe', 'european', 'euro', 'ecb', 'european central bank', 'brussels', 'eurozone'],
    'UK': ['britain', 'british', 'uk', 'pound', 'sterling', 'boe', 'bank of england', 'london'],
    'CN': ['china', 'chinese', 'yuan', 'renminbi', 'pboc', 'beijing'],
    'GLOBAL': ['global', 'worldwide', 'international', 'world']
}

# Severity keywords
CRITICAL_KEYWORDS = [
    'crisis', 'crash', 'collapse', 'emergency', 'panic', 'default',
    'recession confirmed', 'war declared', 'invasion', 'nuclear'
]

HIGH_KEYWORDS = [
    'tariff', 'trade war', 'rate cut', 'rate hike', 'recession',
    'inflation surge', 'employment crisis', 'debt ceiling', 'shutdown',
    'sanction', 'breaking', 'urgent', 'alert'
]

MEDIUM_KEYWORDS = [
    'gdp', 'unemployment', 'inflation', 'interest rate', 'central bank',
    'policy', 'forecast', 'outlook', 'concern', 'warning', 'risk'
]

# Category keywords
CATEGORY_KEYWORDS = {
    'ECON': ['gdp', 'employment', 'jobs', 'unemployment', 'inflation', 'cpi', 'ppi', 'retail sales'],
    'FX': ['currency', 'dollar', 'euro', 'yen', 'pound', 'forex', 'exchange rate'],
    'POLITICAL': ['election', 'congress', 'senate', 'president', 'government', 'policy', 'tariff', 'trade'],
    'CREDIT': ['bond', 'debt', 'credit', 'treasury', 'yield', 'spread', 'default'],
    'CENTRAL_BANK': ['fed', 'federal reserve', 'ecb', 'boj', 'boe', 'central bank', 'interest rate', 'monetary policy']
}


class RSSFetcher:
    """
    Fetches and parses RSS feeds from news sources.
    """

    def __init__(self):
        if not FEEDPARSER_AVAILABLE:
            logger.error("feedparser package not installed")

    def fetch_feed(self, source: str, url: str, max_articles: int = 20) -> Optional[NewsFeed]:
        """
        Fetch and parse a single RSS feed.

        Args:
            source: Source name (bloomberg, cnbc, yahoo)
            url: RSS feed URL
            max_articles: Maximum number of articles to fetch

        Returns:
            NewsFeed object or None
        """
        if not FEEDPARSER_AVAILABLE:
            return None

        try:
            logger.info(f"Fetching RSS feed from {source}...")
            feed = feedparser.parse(url)

            if feed.bozo:
                logger.warning(f"Feed parsing error for {source}: {feed.bozo_exception}")

            articles = []
            for entry in feed.entries[:max_articles]:
                try:
                    # Parse article
                    article = self._parse_entry(entry, source)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.error(f"Error parsing entry from {source}: {e}")

            news_feed = NewsFeed(
                articles=articles,
                source=source,
                timestamp=datetime.utcnow(),
                success=True
            )

            logger.info(f"Fetched {len(articles)} articles from {source}")
            return news_feed

        except Exception as e:
            logger.error(f"Error fetching feed from {source}: {e}")
            return NewsFeed(
                articles=[],
                source=source,
                success=False,
                errors=[str(e)]
            )

    def _parse_entry(self, entry: Any, source: str) -> Optional[NewsArticle]:
        """Parse a single feed entry into a NewsArticle."""
        try:
            # Extract basic info
            headline = entry.get('title', '').strip()
            url = entry.get('link', '').strip()

            if not headline or not url:
                return None

            # Parse publish date
            published_at = self._parse_date(entry)

            # Get summary
            summary = entry.get('summary', '') or entry.get('description', '')
            if summary:
                summary = self._clean_html(summary)

            # Tag article
            country_tags = self._tag_countries(headline, summary)
            category = self._tag_category(headline, summary)
            severity = self._tag_severity(headline, summary)
            keyword_matches = self._extract_keywords(headline, summary)

            article = NewsArticle(
                headline=headline,
                source=source,
                url=url,
                published_at=published_at,
                country_tags=country_tags,
                category=category,
                severity=severity,
                summary=summary[:500] if summary else None,  # Limit summary length
                keyword_matches=keyword_matches
            )

            return article

        except Exception as e:
            logger.error(f"Error parsing entry: {e}")
            return None

    def _parse_date(self, entry: Any) -> datetime:
        """Parse entry publish date."""
        # Try different date fields
        for field in ['published_parsed', 'updated_parsed', 'created_parsed']:
            if hasattr(entry, field):
                date_tuple = getattr(entry, field)
                if date_tuple:
                    try:
                        return datetime(*date_tuple[:6])
                    except:
                        pass

        # Fallback to current time
        return datetime.utcnow()

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags and clean text."""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _tag_countries(self, headline: str, summary: str) -> List[str]:
        """Tag article with relevant countries."""
        text = f"{headline} {summary}".lower()
        countries = []

        for country, keywords in COUNTRY_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text:
                    countries.append(country)
                    break

        return list(set(countries))  # Remove duplicates

    def _tag_category(self, headline: str, summary: str) -> str:
        """Tag article with category."""
        text = f"{headline} {summary}".lower()

        # Check each category
        category_scores = {}
        for category, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword.lower() in text)
            if score > 0:
                category_scores[category] = score

        # Return category with highest score
        if category_scores:
            return max(category_scores, key=category_scores.get)

        return 'GENERAL'

    def _tag_severity(self, headline: str, summary: str) -> str:
        """Tag article with severity level."""
        text = f"{headline} {summary}".lower()

        # Check critical first
        for keyword in CRITICAL_KEYWORDS:
            if keyword.lower() in text:
                return 'CRITICAL'

        # Then high
        for keyword in HIGH_KEYWORDS:
            if keyword.lower() in text:
                return 'HIGH'

        # Then medium
        for keyword in MEDIUM_KEYWORDS:
            if keyword.lower() in text:
                return 'MEDIUM'

        return 'LOW'

    def _extract_keywords(self, headline: str, summary: str) -> List[str]:
        """Extract matched keywords from article."""
        text = f"{headline} {summary}".lower()
        matches = []

        # Check all severity keywords
        for keyword in CRITICAL_KEYWORDS + HIGH_KEYWORDS + MEDIUM_KEYWORDS:
            if keyword.lower() in text:
                matches.append(keyword)

        return matches[:10]  # Limit to 10 keywords

    def fetch_all_feeds(self, max_articles: int = 20) -> List[NewsFeed]:
        """
        Fetch all RSS feeds.

        Args:
            max_articles: Maximum articles per feed

        Returns:
            List of NewsFeed objects
        """
        feeds = []

        for source, url in RSS_FEEDS.items():
            feed = self.fetch_feed(source, url, max_articles)
            if feed:
                feeds.append(feed)

        return feeds

    def check_status(self) -> Dict[str, Any]:
        """Check RSS fetcher status."""
        return {
            'feedparser_available': FEEDPARSER_AVAILABLE,
            'sources': list(RSS_FEEDS.keys()),
            'source_count': len(RSS_FEEDS)
        }