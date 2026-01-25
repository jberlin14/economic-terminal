#!/usr/bin/env python3
"""
Fetch Initial Data Script

Manually fetches FX rates and yield curve data to populate the dashboard.
"""

import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from modules.fx_monitor.data_fetcher import FXDataFetcher
from modules.fx_monitor.storage import store_fx_update
from modules.yields_monitor.data_fetcher import YieldsDataFetcher
from modules.yields_monitor.storage import store_yield_curve
from loguru import logger

logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | {message}")

async def fetch_fx():
    """Fetch FX rates."""
    print("📊 Fetching FX Rates...")

    try:
        fetcher = FXDataFetcher()
        update = await fetcher.fetch_all()
        await fetcher.close()

        if update and update.rates:
            store_fx_update(update)
            print(f"✓ Saved {len(update.rates)} FX rates to database")
        else:
            print("⚠ No FX data returned")
    except Exception as e:
        print(f"❌ FX fetch failed: {e}")
        import traceback
        traceback.print_exc()

def fetch_yields():
    """Fetch yield curve."""
    print("\n📈 Fetching Treasury Yield Curve...")

    try:
        fetcher = YieldsDataFetcher()
        curve = fetcher.fetch_yield_curve()

        if curve:
            store_yield_curve(curve)
            print(f"✓ Saved yield curve data to database")
        else:
            print("⚠ No yield curve data returned")
    except Exception as e:
        print(f"❌ Yield curve fetch failed: {e}")
        import traceback
        traceback.print_exc()

async def main():
    print("\n" + "="*60)
    print("FETCHING INITIAL DATA FOR DASHBOARD")
    print("="*60 + "\n")

    # Fetch FX Rates (async)
    await fetch_fx()

    # Fetch Yield Curve (sync)
    fetch_yields()

    print("\n" + "="*60)
    print("DATA FETCH COMPLETE!")
    print("Refresh your dashboard to see the data.")
    print("="*60 + "\n")

if __name__ == '__main__':
    asyncio.run(main())