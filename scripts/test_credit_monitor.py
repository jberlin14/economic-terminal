#!/usr/bin/env python3
"""Test Credit Monitor Module"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from modules.credit_monitor.data_fetcher import CreditDataFetcher
from modules.credit_monitor.storage import store_credit_update
from loguru import logger

logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | {message}")


def test_credit_monitor():
    """Test credit spread fetching and storage."""
    print("\n" + "="*60)
    print("TESTING CREDIT MONITOR MODULE")
    print("="*60 + "\n")

    # Check API status
    print("Checking FRED API status...")
    fetcher = CreditDataFetcher()
    status = fetcher.check_api_status()

    print(f"  FRED Available: {status['available']}")
    print(f"  API Key Configured: {status['configured']}")
    print(f"  Connection Test: {'Connected' if status['connected'] else 'Failed'}")
    print(f"  Pandas Available: {status['pandas_available']}")

    if not status['connected']:
        print("\nCannot connect to FRED API. Please check your FRED_API_KEY in .env")
        return

    # Fetch credit spreads
    print("\nFetching Credit Spreads...")
    try:
        update = fetcher.fetch_all_spreads()

        if update and update.spreads:
            print(f"\nFetched {len(update.spreads)} credit indices:")
            print()
            for spread in update.spreads:
                pct_str = f"(p90d: {spread.percentile_90d:.1f}%)" if spread.percentile_90d else ""
                avg_str = f"avg90d: {spread.avg_90d:.2f}" if spread.avg_90d else ""
                change_str = f"D1d: {spread.change_1d:+.2f}" if spread.change_1d else ""

                print(f"  {spread.index_name:12} {spread.spread_bps:7.2f} bps  {pct_str:15} {avg_str:15} {change_str}")

            # Store in database
            print("\nStoring to database...")
            stored = store_credit_update(update)
            print(f"Saved {len(stored)} spreads to database")

        else:
            print("No credit spread data returned")

    except Exception as e:
        print(f"Credit spread fetch failed: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)
    print("CREDIT MONITOR TEST COMPLETE!")
    print("="*60 + "\n")


if __name__ == '__main__':
    test_credit_monitor()