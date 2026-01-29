#!/usr/bin/env python3
"""
Test comparison logic directly to debug 404 errors.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.data_storage.database import get_db_context
from modules.economic_indicators.storage import IndicatorStorage

def test_comparison():
    """Test the comparison data retrieval"""

    print("=" * 60)
    print("COMPARISON TEST")
    print("=" * 60)

    series_ids = ['AWHAETP', 'USCONS']
    start_date = datetime.strptime('2024-01-26', '%Y-%m-%d').date()
    end_date = datetime.strptime('2026-01-26', '%Y-%m-%d').date()

    print(f"\nSeries: {', '.join(series_ids)}")
    print(f"Date range: {start_date} to {end_date}")
    print()

    with get_db_context() as db:
        storage = IndicatorStorage(db)

        # Test each series individually first
        print("Testing individual series:")
        print("-" * 60)
        for series_id in series_ids:
            df = storage.get_values(series_id, start_date, end_date)
            print(f"{series_id}: {len(df)} rows")
            if not df.empty:
                print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
                print(f"  Sample values: {df['value'].head(3).tolist()}")
            print()

        # Test comparison
        print("Testing comparison:")
        print("-" * 60)
        df = storage.get_comparison_data(series_ids, start_date, end_date, None)

        if df.empty:
            print("[x] FAILED: DataFrame is empty")
        else:
            print(f"[+] SUCCESS: {len(df)} rows, {len(df.columns)} columns")
            print(f"  Columns: {list(df.columns)}")
            print(f"  Date range: {df.index.min()} to {df.index.max()}")
            print(f"\nFirst 5 rows:")
            print(df.head())
            print(f"\nLast 5 rows:")
            print(df.tail())

if __name__ == '__main__':
    test_comparison()
