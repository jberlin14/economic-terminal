#!/usr/bin/env python3
"""
Economic Indicators Initialization Script

Fetches historical data for all economic indicators from FRED API.
Safe to run multiple times - only adds new data points.

Usage:
    python scripts/init_indicators.py                    # Fetch all indicators, 10 years
    python scripts/init_indicators.py --years 5          # Fetch 5 years of data
    python scripts/init_indicators.py --series PAYEMS,UNRATE  # Fetch specific series only
    python scripts/init_indicators.py --report "CPI Report"   # Fetch one report group
"""

import sys
import os
import argparse
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from loguru import logger

# Configure logger for console
logger.remove()
logger.add(
    sys.stdout,
    format="<level>{level: <8}</level> | {message}",
    level="INFO"
)

from modules.economic_indicators import (
    IndicatorDataFetcher,
    IndicatorStorage,
    get_all_indicators,
    REPORT_GROUPS
)
from modules.data_storage.database import get_db_context


def print_header():
    """Print script header"""
    print("\n" + "=" * 70)
    print("ECONOMIC INDICATORS - HISTORICAL DATA INITIALIZATION")
    print("=" * 70 + "\n")


def print_summary(results: dict, elapsed_time: float):
    """Print summary of fetch operation"""
    print("\n" + "=" * 70)
    print("INITIALIZATION COMPLETE")
    print("=" * 70)

    total = results['total']
    fetched = results['fetched']
    stored = results['stored']
    errors = results['errors']
    data_points = results['data_points']

    print(f"\nTotal indicators configured: {total}")
    print(f"Successfully fetched: {fetched}")
    print(f"Failed: {len(errors)}")

    if errors:
        print(f"\nFailed series:")
        for series_id in errors:
            print(f"  - {series_id}")

    print(f"\nTotal data points stored: {data_points:,}")

    minutes = int(elapsed_time // 60)
    seconds = int(elapsed_time % 60)
    print(f"Time elapsed: {minutes}m {seconds}s")

    print("\n" + "=" * 70 + "\n")


def progress_callback(current: int, total: int, series_id: str, name: str):
    """Display progress for each indicator"""
    pct = (current / total) * 100
    print(f"[{current}/{total}] ({pct:.1f}%) Fetching: {series_id} - {name}")


def init_all_indicators(years_back: int = 10):
    """
    Initialize all indicators with historical data.

    Args:
        years_back: Number of years of historical data to fetch

    Returns:
        dict: Summary of operation
    """
    fetcher = IndicatorDataFetcher()

    if not fetcher.is_available():
        logger.error("FRED API not available. Check FRED_API_KEY in .env file")
        return {
            'total': 0,
            'fetched': 0,
            'stored': 0,
            'errors': ['FRED_UNAVAILABLE'],
            'data_points': 0
        }

    all_indicators = get_all_indicators()
    total = len(all_indicators)

    results = {
        'total': total,
        'fetched': 0,
        'stored': 0,
        'errors': [],
        'data_points': 0
    }

    print(f"Initializing {total} economic indicators...")
    print(f"Fetching {years_back} years of historical data from FRED\n")

    with get_db_context() as db:
        storage = IndicatorStorage(db)

        # Initialize indicator metadata
        print("Initializing indicator metadata...")
        count = storage.initialize_indicators()
        print(f"[OK] {count} new indicators added to database\n")

        # Fetch historical data for each indicator
        for i, (series_id, config) in enumerate(all_indicators.items(), 1):
            progress_callback(i, total, series_id, config['name'])

            try:
                # Fetch data from FRED
                df = fetcher.fetch_series(series_id, years_back=years_back)

                if df is not None and not df.empty:
                    results['fetched'] += 1

                    # Store values
                    stored_count = storage.store_values(series_id, df)

                    if stored_count > 0:
                        results['stored'] += 1
                        results['data_points'] += stored_count
                        logger.debug(f"  Stored {stored_count} data points")
                    else:
                        logger.debug(f"  No new data points (already exists)")
                else:
                    results['errors'].append(series_id)
                    logger.warning(f"  No data returned from FRED")

            except Exception as e:
                results['errors'].append(series_id)
                logger.error(f"  Error: {e}")

            # Small delay to be nice to FRED
            time.sleep(0.1)

    return results


def init_specific_series(series_ids: list, years_back: int = 10):
    """
    Initialize specific series with historical data.

    Args:
        series_ids: List of FRED series IDs to fetch
        years_back: Number of years of historical data

    Returns:
        dict: Summary of operation
    """
    fetcher = IndicatorDataFetcher()

    if not fetcher.is_available():
        logger.error("FRED API not available")
        return {
            'total': 0,
            'fetched': 0,
            'stored': 0,
            'errors': ['FRED_UNAVAILABLE'],
            'data_points': 0
        }

    total = len(series_ids)
    all_indicators = get_all_indicators()

    results = {
        'total': total,
        'fetched': 0,
        'stored': 0,
        'errors': [],
        'data_points': 0
    }

    print(f"Fetching {total} specific indicators...")
    print(f"Years of data: {years_back}\n")

    with get_db_context() as db:
        storage = IndicatorStorage(db)
        storage.initialize_indicators()

        for i, series_id in enumerate(series_ids, 1):
            config = all_indicators.get(series_id)
            name = config['name'] if config else series_id

            progress_callback(i, total, series_id, name)

            try:
                df = fetcher.fetch_series(series_id, years_back=years_back)

                if df is not None and not df.empty:
                    results['fetched'] += 1
                    stored_count = storage.store_values(series_id, df)

                    if stored_count > 0:
                        results['stored'] += 1
                        results['data_points'] += stored_count

                else:
                    results['errors'].append(series_id)

            except Exception as e:
                results['errors'].append(series_id)
                logger.error(f"  Error: {e}")

            time.sleep(0.1)

    return results


def init_report_group(report_name: str, years_back: int = 10):
    """
    Initialize all indicators in a specific report group.

    Args:
        report_name: Name of report group (e.g., 'CPI Report')
        years_back: Number of years of historical data

    Returns:
        dict: Summary of operation
    """
    # Find all series in this report group
    series_ids = []
    all_indicators = get_all_indicators()

    for series_id, config in all_indicators.items():
        if config['report_group'] == report_name:
            series_ids.append(series_id)

    if not series_ids:
        logger.error(f"No indicators found in report group: {report_name}")
        logger.info(f"Available report groups: {list(REPORT_GROUPS.keys())}")
        return {
            'total': 0,
            'fetched': 0,
            'stored': 0,
            'errors': [],
            'data_points': 0
        }

    print(f"Report group: {report_name}")
    print(f"Found {len(series_ids)} indicators\n")

    return init_specific_series(series_ids, years_back)


def main():
    parser = argparse.ArgumentParser(
        description='Initialize economic indicators with historical data from FRED',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/init_indicators.py
  python scripts/init_indicators.py --years 5
  python scripts/init_indicators.py --series PAYEMS,UNRATE
  python scripts/init_indicators.py --report "CPI Report"
        """
    )

    parser.add_argument('--years', type=int, default=10,
                        help='Years of historical data to fetch (default: 10)')
    parser.add_argument('--series', type=str,
                        help='Comma-separated list of specific series IDs to fetch')
    parser.add_argument('--report', type=str,
                        help='Fetch only indicators from a specific report group')

    args = parser.parse_args()

    print_header()

    start_time = time.time()

    # Determine which indicators to fetch
    if args.series:
        series_ids = [s.strip() for s in args.series.split(',')]
        results = init_specific_series(series_ids, args.years)
    elif args.report:
        results = init_report_group(args.report, args.years)
    else:
        results = init_all_indicators(args.years)

    elapsed = time.time() - start_time

    print_summary(results, elapsed)

    # Exit code: 0 if all successful, 1 if any failed
    sys.exit(0 if len(results['errors']) == 0 else 1)


if __name__ == '__main__':
    main()
