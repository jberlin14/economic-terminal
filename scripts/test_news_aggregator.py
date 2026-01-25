#!/usr/bin/env python3
"""Test News Aggregator Module"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from modules.news_aggregator.rss_fetcher import RSSFetcher
from modules.news_aggregator.storage import store_news_feed
from loguru import logger

logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | {message}")


def test_news_aggregator():
    """Test news aggregator fetching and storage."""
    print("\n" + "="*60)
    print("TESTING NEWS AGGREGATOR MODULE")
    print("="*60 + "\n")

    # Check status
    print("Checking RSS Fetcher status...")
    fetcher = RSSFetcher()
    status = fetcher.check_status()

    print(f"  Feedparser Available: {status['feedparser_available']}")
    print(f"  Sources: {', '.join(status['sources'])}")
    print(f"  Source Count: {status['source_count']}")

    if not status['feedparser_available']:
        print("\nfeedparser not installed. Run: pip install feedparser")
        return

    # Fetch RSS feeds
    print("\nFetching RSS Feeds...")
    try:
        feeds = fetcher.fetch_all_feeds(max_articles=5)

        total_articles = 0
        total_stored = 0
        total_duplicates = 0

        for feed in feeds:
            print(f"\nSource: {feed.source}")
            print(f"  Articles fetched: {len(feed.articles)}")

            if feed.articles:
                # Show sample articles
                print("\n  Sample articles:")
                for i, article in enumerate(feed.articles[:3], 1):
                    severity_badge = {
                        'CRITICAL': 'CRIT',
                        'HIGH': 'HIGH',
                        'MEDIUM': 'MED ',
                        'LOW': 'LOW '
                    }.get(article.severity, 'LOW ')

                    countries = ','.join(article.country_tags) if article.country_tags else 'None'
                    print(f"    {i}. [{severity_badge}] [{article.category:12}] [{countries:10}]")
                    print(f"       {article.headline[:70]}...")
                    if article.keyword_matches:
                        print(f"       Keywords: {', '.join(article.keyword_matches[:5])}")

                # Store in database
                print(f"\n  Storing {feed.source} articles to database...")
                counts = store_news_feed(feed)
                print(f"  Stored: {counts['stored']}, Duplicates: {counts['duplicates']}, Errors: {counts['errors']}")

                total_articles += len(feed.articles)
                total_stored += counts['stored']
                total_duplicates += counts['duplicates']

        print("\n" + "="*60)
        print(f"TOTAL: {total_articles} articles fetched")
        print(f"       {total_stored} stored")
        print(f"       {total_duplicates} duplicates")
        print("="*60 + "\n")

    except Exception as e:
        print(f"News aggregator test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_news_aggregator()