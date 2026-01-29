#!/usr/bin/env python3
"""
Quick diagnostic script to check if specific series exist in the database.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.data_storage.database import get_db_context
from modules.economic_indicators.storage import IndicatorStorage

def check_series(series_ids: list):
    """Check if series exist and have data"""

    print("=" * 60)
    print("SERIES CHECK")
    print("=" * 60)

    with get_db_context() as db:
        storage = IndicatorStorage(db)

        for series_id in series_ids:
            print(f"\nSeries: {series_id}")
            print("-" * 40)

            # Check if indicator exists
            indicator = storage.get_indicator(series_id)
            if not indicator:
                print("  [x] NOT FOUND in database")
                continue

            print(f"  [+] Name: {indicator.name}")
            print(f"  [+] Category: {indicator.category}")
            print(f"  [+] Frequency: {indicator.frequency}")
            print(f"  [+] Units: {indicator.units}")

            # Check date range
            date_range = storage.get_date_range(series_id)
            if date_range:
                print(f"  [+] Date range: {date_range['start_date']} to {date_range['end_date']}")
            else:
                print("  [!] No data points stored")
                continue

            # Check data count
            count = storage.get_value_count(series_id)
            print(f"  [+] Data points: {count}")

            # Get latest value
            latest = storage.get_latest_value(series_id)
            if latest:
                print(f"  [+] Latest: {latest['date']} = {latest['value']}")

if __name__ == '__main__':
    # Check the series that were failing in comparison
    series_to_check = ['AWHAETP', 'USCONS']

    if len(sys.argv) > 1:
        series_to_check = sys.argv[1:]

    check_series(series_to_check)
