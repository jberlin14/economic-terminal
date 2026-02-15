"""
Article Full-Text Scraper

Fetches full article content from stored URLs, extracts the main body text,
and populates the full_text column on NewsArticle records.

Respects robots.txt, rate limits per domain, and handles common failure modes.
"""

import time
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from loguru import logger

from ..data_storage.schema import NewsArticle as NewsArticleDB
from ..data_storage.database import get_db_context

# User agent for scraper requests
USER_AGENT = "EconomicTerminal/1.0 (news aggregator; +https://github.com/economic-terminal)"

# Rate limit: minimum seconds between requests to the same domain
DOMAIN_RATE_LIMIT_SECONDS = 2.0

# Request timeout in seconds
REQUEST_TIMEOUT = 15

# Maximum article text length to store (chars)
MAX_TEXT_LENGTH = 50_000

# Maximum number of articles to scrape per batch
DEFAULT_BATCH_SIZE = 25

# How far back to look for articles missing full_text (hours)
DEFAULT_LOOKBACK_HOURS = 48

# Domains to skip (paywalled, bot-blocking, or no useful text)
SKIP_DOMAINS = {
    "twitter.com",
    "x.com",
    "youtube.com",
    "facebook.com",
    "linkedin.com",
    "instagram.com",
}

# Phrases that indicate a paywall or login wall (lowercase)
PAYWALL_MARKERS = [
    "subscribe to continue reading",
    "subscribe to read",
    "subscribe for full access",
    "sign in to read",
    "sign up to read",
    "log in to continue",
    "log in to read",
    "create a free account",
    "create an account to read",
    "become a member",
    "start your free trial",
    "already a subscriber",
    "for subscribers only",
    "exclusive to subscribers",
    "premium content",
    "premium article",
    "this content is for subscribers",
    "this article is for subscribers",
    "unlock this article",
    "to unlock full access",
    "register to continue",
    "register for free to read",
    "you've reached your limit",
    "you have reached your limit",
    "free articles remaining",
    "articles remaining this month",
]

# Scraped text must be at least this ratio longer than the summary to be worth storing
MIN_LENGTH_RATIO_VS_SUMMARY = 1.5

# Tags to remove before extracting text
REMOVE_TAGS = [
    "script", "style", "nav", "header", "footer", "aside",
    "iframe", "noscript", "form", "button", "svg",
    "figure", "figcaption",
]

# CSS selectors to try for article body, in priority order
ARTICLE_SELECTORS = [
    "article",
    '[role="main"]',
    ".article-body",
    ".article-content",
    ".story-body",
    ".post-content",
    ".entry-content",
    ".content-body",
    "#article-body",
    "#story-body",
    "main",
    ".main-content",
]


class ArticleScraper:
    """
    Scrapes full article text from news URLs with rate limiting
    and robots.txt compliance.
    """

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        })
        # Track last request time per domain for rate limiting
        self._domain_last_request: Dict[str, float] = {}
        # Cache robots.txt parsers per domain
        self._robots_cache: Dict[str, Optional[RobotFileParser]] = {}

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc.lower()

    def _should_skip_domain(self, url: str) -> bool:
        """Check if domain is in the skip list."""
        domain = self._get_domain(url)
        for skip in SKIP_DOMAINS:
            if skip in domain:
                return True
        return False

    def _check_robots_txt(self, url: str) -> bool:
        """Check if robots.txt allows fetching this URL. Returns True if allowed."""
        domain = self._get_domain(url)
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{domain}/robots.txt"

        if domain not in self._robots_cache:
            try:
                rp = RobotFileParser()
                rp.set_url(robots_url)
                rp.read()
                self._robots_cache[domain] = rp
            except Exception:
                # If we can't fetch robots.txt, assume allowed
                self._robots_cache[domain] = None

        rp = self._robots_cache[domain]
        if rp is None:
            return True
        return rp.can_fetch(USER_AGENT, url)

    def _rate_limit(self, url: str):
        """Enforce per-domain rate limiting."""
        domain = self._get_domain(url)
        last = self._domain_last_request.get(domain, 0)
        elapsed = time.time() - last
        if elapsed < DOMAIN_RATE_LIMIT_SECONDS:
            sleep_time = DOMAIN_RATE_LIMIT_SECONDS - elapsed
            time.sleep(sleep_time)
        self._domain_last_request[domain] = time.time()

    def _detect_paywall(self, text: str) -> bool:
        """Check if extracted text looks like a paywall stub."""
        text_lower = text.lower()
        for marker in PAYWALL_MARKERS:
            if marker in text_lower:
                return True
        return False

    def _extract_text(self, html: str) -> Optional[str]:
        """Extract main article text from HTML."""
        soup = BeautifulSoup(html, "html.parser")

        # Remove unwanted tags
        for tag_name in REMOVE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # Try article-specific selectors first
        content_element = None
        for selector in ARTICLE_SELECTORS:
            content_element = soup.select_one(selector)
            if content_element:
                break

        if content_element is None:
            # Fallback: use body
            content_element = soup.find("body")

        if content_element is None:
            return None

        # Get text from paragraphs within the content element
        paragraphs = content_element.find_all("p")
        if paragraphs:
            text_parts = []
            for p in paragraphs:
                text = p.get_text(separator=" ", strip=True)
                # Skip very short paragraphs (likely captions or nav items)
                if len(text) > 30:
                    text_parts.append(text)
            full_text = "\n\n".join(text_parts)
        else:
            # No <p> tags — get all text
            full_text = content_element.get_text(separator="\n", strip=True)

        # Clean up whitespace
        lines = [line.strip() for line in full_text.splitlines() if line.strip()]
        full_text = "\n\n".join(lines)

        # Minimum viable article length
        if len(full_text) < 100:
            return None

        # Check for paywall markers — if the text is short AND has paywall
        # language, it's a stub. If it's long despite having a paywall marker
        # (e.g. a "subscribe" footer on a full article), keep it.
        if self._detect_paywall(full_text) and len(full_text) < 500:
            logger.debug("Paywall stub detected, skipping")
            return None

        return full_text[:MAX_TEXT_LENGTH]

    def scrape_article(self, url: str) -> Optional[str]:
        """
        Fetch and extract full text from a single article URL.

        Returns extracted text or None on failure.
        """
        if not url:
            return None

        if self._should_skip_domain(url):
            logger.debug(f"Skipping blocked domain: {url[:80]}")
            return None

        if not self._check_robots_txt(url):
            logger.debug(f"Blocked by robots.txt: {url[:80]}")
            return None

        self._rate_limit(url)

        try:
            response = self._session.get(
                url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                logger.debug(f"Non-HTML content type ({content_type}): {url[:80]}")
                return None

            return self._extract_text(response.text)

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout scraping: {url[:80]}")
        except requests.exceptions.HTTPError as e:
            logger.warning(f"HTTP {e.response.status_code} scraping: {url[:80]}")
        except requests.exceptions.ConnectionError:
            logger.warning(f"Connection error scraping: {url[:80]}")
        except Exception as e:
            logger.error(f"Unexpected error scraping {url[:80]}: {e}")

        return None

    def close(self):
        """Close the HTTP session."""
        self._session.close()


def scrape_missing_articles(
    batch_size: int = DEFAULT_BATCH_SIZE,
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
) -> Dict[str, int]:
    """
    Find articles without full_text and scrape them.

    Called as a background task after RSS fetching.

    Returns:
        Dictionary with counts: scraped, failed, skipped
    """
    counts = {"scraped": 0, "failed": 0, "skipped": 0}

    with get_db_context() as db:
        cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)

        # Get articles missing full_text, ordered by most recent first
        articles: List[NewsArticleDB] = (
            db.query(NewsArticleDB)
            .filter(
                NewsArticleDB.full_text.is_(None),
                NewsArticleDB.published_at >= cutoff,
                NewsArticleDB.url.isnot(None),
                NewsArticleDB.url != "",
            )
            .order_by(NewsArticleDB.published_at.desc())
            .limit(batch_size)
            .all()
        )

        if not articles:
            logger.debug("No articles need scraping")
            return counts

        logger.info(f"Scraping full text for {len(articles)} articles...")
        scraper = ArticleScraper()

        try:
            for article in articles:
                try:
                    if scraper._should_skip_domain(article.url):
                        counts["skipped"] += 1
                        continue

                    text = scraper.scrape_article(article.url)
                    if text:
                        # Only store if meaningfully longer than the RSS summary
                        summary_len = len(article.summary or "")
                        if summary_len and len(text) < summary_len * MIN_LENGTH_RATIO_VS_SUMMARY:
                            logger.debug(
                                f"Scraped text not longer than summary "
                                f"({len(text)} vs {summary_len}): {article.headline[:50]}..."
                            )
                            counts["skipped"] += 1
                            continue

                        article.full_text = text
                        db.commit()
                        counts["scraped"] += 1
                        logger.debug(
                            f"Scraped ({len(text)} chars): {article.headline[:50]}..."
                        )
                    else:
                        counts["failed"] += 1

                except Exception as e:
                    db.rollback()
                    counts["failed"] += 1
                    logger.error(f"Error processing article {article.id}: {e}")
        finally:
            scraper.close()

    logger.info(
        f"Scraping complete: {counts['scraped']} scraped, "
        f"{counts['failed']} failed, {counts['skipped']} skipped"
    )
    return counts
