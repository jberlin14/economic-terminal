#!/usr/bin/env python3
"""
Manual data fetch script for Economic Terminal.
Fetches and stores all data types: FX rates, yields, credit spreads, and news.

Usage:
    python scripts/manual_fetch.py              # Fetch everything
    python scripts/manual_fetch.py --fx         # Only FX rates
    python scripts/manual_fetch.py --yields     # Only yield curves
    python scripts/manual_fetch.py --credit     # Only credit spreads
    python scripts/manual_fetch.py --news       # Only news feeds
    python scripts/manual_fetch.py --all        # Fetch everything (explicit)
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
env_file = project_root / '.env'
if env_file.exists():
    load_dotenv(env_file)
    print(f"Loaded environment from: {env_file}")
else:
    print(f"Warning: .env file not found at {env_file}")

from loguru import logger

# Configure logger for console output
logger.remove()
logger.add(
    sys.stdout,
    format="<level>{level: <8}</level> | {message}",
    level="INFO"
)


def fetch_fx_rates() -> dict:
    """Fetch and store FX rates."""
    print("\n" + "=" * 60)
    print("FETCHING FX RATES")
    print("=" * 60)

    result = {
        'success': False,
        'count': 0,
        'error': None
    }

    try:
        import asyncio
        from modules.fx_monitor.data_fetcher import FXDataFetcher
        from modules.fx_monitor.storage import store_fx_update

        print("Initializing FX data fetcher...")
        fetcher = FXDataFetcher()

        print("Fetching current FX rates...")
        # FX fetcher is async
        update = asyncio.run(fetcher.fetch_all())
        asyncio.run(fetcher.close())

        if update and update.rates:
            print(f"\nFetched {len(update.rates)} currency pairs:")
            for rate in update.rates:
                print(f"  {rate.pair:7} {rate.rate:8.4f}")

            print("\nStoring to database...")
            stored = store_fx_update(update)
            result['success'] = True
            result['count'] = len(update.rates)

            print(f"SUCCESS: Stored {len(update.rates)} FX rates")
        else:
            result['error'] = "No rates returned from API"
            print("ERROR: No rates returned from API")

    except Exception as e:
        result['error'] = str(e)
        logger.error(f"FX fetch failed: {e}")
        print(f"ERROR: {e}")

    return result


def fetch_yield_curve() -> dict:
    """Fetch and store yield curve."""
    print("\n" + "=" * 60)
    print("FETCHING YIELD CURVE")
    print("=" * 60)

    result = {
        'success': False,
        'count': 0,
        'error': None
    }

    try:
        from modules.yields_monitor.data_fetcher import YieldsDataFetcher
        from modules.yields_monitor.storage import store_yield_curve

        print("Initializing yield curve fetcher...")
        fetcher = YieldsDataFetcher()

        print("Fetching US Treasury yields...")
        curve = fetcher.fetch_yield_curve()

        if curve and hasattr(curve, 'curve_dict') and curve.curve_dict:
            print(f"\nFetched yield curve:")
            for maturity, rate in curve.curve_dict.items():
                print(f"  {maturity:4} {rate:6.3f}%")
            if hasattr(curve, 'spread_10y2y') and curve.spread_10y2y is not None:
                print(f"\n  10Y-2Y Spread: {curve.spread_10y2y:6.3f}%")

            print("\nStoring to database...")
            stored = store_yield_curve(curve)
            result['success'] = True
            result['count'] = len(curve.curve_dict)

            print(f"SUCCESS: Stored yield curve with {len(curve.curve_dict)} points")
        else:
            result['error'] = "No yield data returned from API"
            print("ERROR: No yield data returned from API")

    except Exception as e:
        result['error'] = str(e)
        logger.error(f"Yield curve fetch failed: {e}")
        print(f"ERROR: {e}")

    return result


def fetch_credit_spreads() -> dict:
    """Fetch and store credit spreads."""
    print("\n" + "=" * 60)
    print("FETCHING CREDIT SPREADS")
    print("=" * 60)

    result = {
        'success': False,
        'count': 0,
        'error': None
    }

    try:
        from modules.credit_monitor.data_fetcher import CreditDataFetcher
        from modules.credit_monitor.storage import store_credit_update

        print("Initializing credit data fetcher...")
        fetcher = CreditDataFetcher()

        print("Checking FRED API status...")
        status = fetcher.check_api_status()
        if not status.get('connected', False):
            result['error'] = f"FRED API not available: {status.get('error')}"
            print(f"ERROR: {result['error']}")
            return result

        print("FRED API: OK")
        print("\nFetching ICE BofA credit indices...")
        update = fetcher.fetch_all_spreads()

        if update and update.spreads:
            print(f"\nFetched {len(update.spreads)} credit indices:")
            for spread in update.spreads:
                pct_str = f"(p90d: {spread.percentile_90d:.1f}%)" if spread.percentile_90d else ""
                print(f"  {spread.index_name:12} {spread.spread_bps:7.2f} bps  {pct_str}")

            print("\nStoring to database...")
            stored = store_credit_update(update)
            result['success'] = True
            result['count'] = len(update.spreads)

            print(f"SUCCESS: Stored {len(update.spreads)} credit spreads")
        else:
            result['error'] = "No credit spreads returned from API"
            print("ERROR: No credit spreads returned from API")

    except Exception as e:
        result['error'] = str(e)
        logger.error(f"Credit spreads fetch failed: {e}")
        print(f"ERROR: {e}")

    return result


def fetch_news() -> dict:
    """Fetch and store news from RSS feeds."""
    print("\n" + "=" * 60)
    print("FETCHING NEWS FEEDS")
    print("=" * 60)

    result = {
        'success': False,
        'count': 0,
        'duplicates': 0,
        'error': None
    }

    try:
        from modules.news_aggregator.rss_fetcher import RSSFetcher
        from modules.news_aggregator.storage import store_news_feed

        print("Initializing RSS fetcher...")
        fetcher = RSSFetcher()

        print("Fetching from all RSS feeds...")
        feeds = fetcher.fetch_all_feeds(max_articles=10)

        total_stored = 0
        total_duplicates = 0
        total_articles = 0

        for feed in feeds:
            print(f"\nSource: {feed.source.upper()}")
            print(f"  Articles fetched: {len(feed.articles)}")

            if feed.articles:
                # Show sample of articles
                for article in feed.articles[:3]:
                    severity_badge = {
                        'CRITICAL': 'CRIT',
                        'HIGH': 'HIGH',
                        'MEDIUM': 'MED',
                        'LOW': 'LOW'
                    }.get(article.severity, 'LOW ')

                    countries = ','.join(article.country_tags) if article.country_tags else 'None'
                    print(f"  [{severity_badge}] [{article.category}] [{countries}]")
                    print(f"  {article.headline[:70]}...")

                # Store articles
                counts = store_news_feed(feed)
                total_stored += counts['stored']
                total_duplicates += counts['duplicates']
                total_articles += len(feed.articles)

                print(f"  Stored: {counts['stored']}, Duplicates: {counts['duplicates']}")

        result['success'] = True
        result['count'] = total_stored
        result['duplicates'] = total_duplicates

        print(f"\nSUCCESS: Processed {total_articles} articles")
        print(f"  New: {total_stored}, Duplicates: {total_duplicates}")

    except Exception as e:
        result['error'] = str(e)
        logger.error(f"News fetch failed: {e}")
        print(f"ERROR: {e}")

    return result


def print_summary(results: dict):
    """Print summary of all fetch operations."""
    print("\n" + "=" * 60)
    print("FETCH SUMMARY")
    print("=" * 60)

    for name, result in results.items():
        status = "SUCCESS" if result['success'] else "FAILED"
        status_symbol = "[+]" if result['success'] else "[x]"

        print(f"{status_symbol} {name:20} {status:7}", end="")

        if result['success']:
            if 'duplicates' in result:
                print(f"  {result['count']} new, {result['duplicates']} duplicates")
            else:
                print(f"  {result['count']} items")
        else:
            print(f"  {result.get('error', 'Unknown error')}")

    # Count successes
    total = len(results)
    successes = sum(1 for r in results.values() if r['success'])

    print("\n" + "=" * 60)
    print(f"Completed: {successes}/{total} successful")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Manual data fetch for Economic Terminal',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/manual_fetch.py              # Fetch everything
  python scripts/manual_fetch.py --fx         # Only FX rates
  python scripts/manual_fetch.py --yields     # Only yield curves
  python scripts/manual_fetch.py --credit     # Only credit spreads
  python scripts/manual_fetch.py --news       # Only news feeds
        """
    )

    parser.add_argument('--fx', action='store_true', help='Fetch FX rates only')
    parser.add_argument('--yields', action='store_true', help='Fetch yield curve only')
    parser.add_argument('--credit', action='store_true', help='Fetch credit spreads only')
    parser.add_argument('--news', action='store_true', help='Fetch news only')
    parser.add_argument('--all', action='store_true', help='Fetch everything (default)')

    args = parser.parse_args()

    # If no specific flags, fetch all
    fetch_all = args.all or not (args.fx or args.yields or args.credit or args.news)

    print("=" * 60)
    print("ECONOMIC TERMINAL - MANUAL DATA FETCH")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    results = {}

    if fetch_all or args.fx:
        results['FX Rates'] = fetch_fx_rates()

    if fetch_all or args.yields:
        results['Yield Curve'] = fetch_yield_curve()

    if fetch_all or args.credit:
        results['Credit Spreads'] = fetch_credit_spreads()

    if fetch_all or args.news:
        results['News Feeds'] = fetch_news()

    # Print summary
    print_summary(results)

    # Exit code: 0 if all successful, 1 if any failed
    all_success = all(r['success'] for r in results.values())
    sys.exit(0 if all_success else 1)


if __name__ == '__main__':
    main()