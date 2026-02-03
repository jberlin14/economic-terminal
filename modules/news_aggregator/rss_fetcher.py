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
from .leader_detector import LeaderDetector
from .config import RSS_FEEDS as CONFIGURED_RSS_FEEDS


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
    'ECON': ['gdp', 'employment', 'jobs', 'unemployment', 'inflation', 'cpi', 'ppi', 'retail sales',
             'consumer confidence', 'consumer spending', 'economic growth', 'nonfarm', 'payrolls',
             'housing starts', 'industrial production', 'pmi', 'ism'],
    'FX': ['currency', 'dollar', 'euro', 'yen', 'pound', 'forex', 'exchange rate', 'fx ',
           'devaluation', 'appreciation', 'depreciation'],
    'POLITICAL': ['election', 'congress', 'senate', 'government', 'policy',
                  'legislation', 'bipartisan', 'democrat', 'republican', 'vote', 'referendum'],
    'CREDIT': ['bond', 'debt', 'credit', 'treasury', 'yield', 'spread', 'default',
               'downgrade', 'upgrade', 'sovereign debt', 'corporate bond', 'high yield',
               'investment grade', 'credit rating'],
    'CENTRAL_BANK': ['fed', 'federal reserve', 'ecb', 'boj', 'boe', 'central bank', 'interest rate',
                     'monetary policy', 'fomc', 'rate decision', 'rate cut', 'rate hike', 'rate hold',
                     'rate steady', 'dovish', 'hawkish', 'quantitative', 'taper'],
    'GEOPOLITICAL': ['geopolitical', 'nato', 'military', 'defense', 'troops', 'missile',
                     'invasion', 'conflict', 'war ', 'ceasefire', 'nuclear', 'weapon'],
    'TRADE_POLICY': ['tariff', 'trade war', 'trade deal', 'trade policy', 'trade deficit',
                     'sanctions', 'embargo', 'export controls', 'import duty', 'trade agreement',
                     'usmca', 'nafta', 'wto'],
}

# Map event types from leader_detector to display categories
EVENT_TO_CATEGORY = {
    'RATE_DECISION': 'CENTRAL_BANK',
    'TRADE_POLICY': 'TRADE_POLICY',
    'SANCTIONS': 'TRADE_POLICY',
    'MILITARY': 'GEOPOLITICAL',
    'ELECTION': 'POLITICAL',
    'ECONOMIC_DATA': 'ECON',
    'MARKET_MOVE': 'CREDIT',
    'CURRENCY': 'FX',
    'DEBT_CREDIT': 'CREDIT',
    'DISASTER': 'GEOPOLITICAL',
}

# Sources that are inherently central bank feeds
CENTRAL_BANK_SOURCES = {'fed', 'ecb', 'boe', 'boj', 'boc', 'rba', 'rbnz'}


class RSSFetcher:
    """
    Fetches and parses RSS feeds from news sources.
    """

    def __init__(self):
        if not FEEDPARSER_AVAILABLE:
            logger.error("feedparser package not installed")
        self.detector = LeaderDetector()

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
            now = datetime.utcnow()
            for entry in feed.entries[:max_articles]:
                try:
                    # Parse article
                    article = self._parse_entry(entry, source)
                    if article:
                        # Skip articles with future dates (e.g., BOC schedule entries)
                        if article.published_at > now:
                            logger.debug(f"Skipping future-dated article: {article.headline[:50]}...")
                            continue
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

            # Perform comprehensive analysis using leader detector
            analysis = self.detector.analyze_article(headline, summary)

            # Tag article (keep existing methods for backward compatibility)
            country_tags_legacy = self._tag_countries(headline, summary)
            category_legacy = self._tag_category(headline, summary)
            keyword_matches = self._extract_keywords(headline, summary)

            # Merge analysis with legacy tags
            all_country_tags = list(set(country_tags_legacy + analysis['countries']))
            all_actions = analysis['actions']['critical'] + analysis['actions']['high']

            # Calculate relevance score
            relevance = self._calculate_relevance_score(headline, summary, analysis)

            # Determine best category
            category = self._resolve_category(
                source=source,
                events=analysis.get('events', []),
                legacy_category=category_legacy,
                headline=headline,
                summary=summary or '',
            )

            article = NewsArticle(
                headline=headline,
                source=source,
                url=url,
                published_at=published_at,
                country_tags=all_country_tags,
                category=category,
                severity=analysis['severity'],
                summary=summary[:500] if summary else None,
                keyword_matches=keyword_matches,
                relevance_score=relevance,
                # New fields from leader detection
                leader_mentions=analysis['leader_keys'],
                institutions=analysis['institutions'],
                event_types=analysis['events'],
                action_words=all_actions
            )

            return article

        except Exception as e:
            logger.error(f"Error parsing entry: {e}")
            return None

    def _calculate_relevance_score(
        self, headline: str, summary: str, analysis: Dict[str, Any]
    ) -> float:
        """
        Calculate relevance score for the Economic Terminal's focus areas.

        Higher scores for: bonds, rates, Fed, trade, geopolitics, government.
        Lower scores for: individual stocks, equities, IPOs, earnings, crypto.
        """
        text = f"{headline} {summary}".lower()
        score = 50.0  # Baseline

        # --- BOOST: topics the user cares about ---
        high_value_terms = [
            'treasury', 'treasuries', 'bond', 'bonds', 'yield', 'yields',
            'interest rate', 'rate cut', 'rate hike', 'rate decision',
            'federal reserve', 'fed ', 'fomc', 'monetary policy',
            'central bank', 'ecb', 'boj', 'boe',
            'tariff', 'trade war', 'trade policy', 'trade deal', 'trade deficit',
            'sanctions', 'embargo', 'export controls',
            'geopolitical', 'nato', 'military', 'defense',
            'government', 'congress', 'senate', 'white house', 'executive order',
            'fiscal policy', 'debt ceiling', 'budget', 'deficit', 'spending bill',
            'inflation', 'cpi', 'ppi', 'gdp', 'employment', 'jobs report',
            'unemployment', 'nonfarm', 'payrolls', 'retail sales',
            'recession', 'economic growth', 'consumer confidence',
            'credit spread', 'default', 'downgrade', 'sovereign debt',
            'currency', 'dollar', 'forex', 'exchange rate',
        ]
        for term in high_value_terms:
            if term in text:
                score += 8.0

        # Extra boost for leader/institution mentions
        if analysis.get('leader_keys'):
            score += 10.0
        if analysis.get('institutions'):
            score += 10.0

        # Boost based on severity
        severity = analysis.get('severity', 'LOW')
        if severity == 'CRITICAL':
            score += 20.0
        elif severity == 'HIGH':
            score += 10.0
        elif severity == 'MEDIUM':
            score += 5.0

        # --- PENALIZE: topics the user cares less about ---
        low_value_terms = [
            'stock pick', 'buy the dip', 'top stocks', 'best stocks',
            'ipo', 'initial public offering', 'going public',
            'earnings report', 'earnings beat', 'earnings miss',
            'quarterly results', 'revenue beat', 'profit margin',
            'share price', 'stock price', 'market cap',
            'analyst upgrade', 'analyst downgrade', 'price target',
            'dividend', 'stock split', 'buyback',
            'tech stocks', 'meme stock', 'penny stock',
            'crypto', 'bitcoin', 'ethereum', 'nft', 'dogecoin',
            'personal finance', 'retirement', '401k', 'savings account',
        ]
        for term in low_value_terms:
            if term in text:
                score -= 12.0

        # Cap score between 0 and 100
        return max(0.0, min(100.0, round(score, 1)))

    def _resolve_category(self, source: str, events: List[str], legacy_category: str, headline: str = '', summary: str = '') -> str:
        """Determine the best display category for an article.

        Priority: source type > event mapping > headline keywords > summary keywords.
        Headline matches are weighted 3x more than summary matches to avoid
        miscategorization from tangential mentions in summaries.
        """
        # Central bank sources always get CENTRAL_BANK
        if source in CENTRAL_BANK_SOURCES:
            return 'CENTRAL_BANK'

        # Collect candidate categories from events
        event_categories = []
        for event in events:
            mapped = EVENT_TO_CATEGORY.get(event)
            if mapped:
                event_categories.append(mapped)

        # Score categories primarily from headline, summary is tiebreaker only
        headline_lower = headline.lower() if headline else ''
        summary_lower = summary.lower() if summary else ''

        cat_scores: Dict[str, float] = {}
        for cat, keywords in CATEGORY_KEYWORDS.items():
            headline_hits = sum(1 for kw in keywords if kw in headline_lower)
            summary_hits = sum(1 for kw in keywords if kw in summary_lower)
            # Headline is primary signal; summary only counts if headline also matches
            if headline_hits > 0:
                cat_scores[cat] = (headline_hits * 3) + summary_hits
            elif summary_hits >= 3:
                # Strong summary signal (3+ keyword matches) still counts but weakly
                cat_scores[cat] = summary_hits * 0.5

        # Boost categories that also have event detection support
        for cat in event_categories:
            cat_scores[cat] = cat_scores.get(cat, 0) + 5

        if cat_scores:
            return max(cat_scores, key=cat_scores.get)

        return 'ECON'  # Default instead of GENERAL

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
        Fetch all configured RSS feeds.

        Args:
            max_articles: Maximum articles per feed

        Returns:
            List of NewsFeed objects
        """
        feeds = []

        for source, config in CONFIGURED_RSS_FEEDS.items():
            url = config['url']
            feed = self.fetch_feed(source, url, max_articles)
            if feed:
                feeds.append(feed)

        return feeds

    def check_status(self) -> Dict[str, Any]:
        """Check RSS fetcher status."""
        return {
            'feedparser_available': FEEDPARSER_AVAILABLE,
            'sources': list(CONFIGURED_RSS_FEEDS.keys()),
            'source_count': len(CONFIGURED_RSS_FEEDS)
        }