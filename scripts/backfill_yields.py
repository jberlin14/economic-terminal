"""
Backfill Treasury Yield Data from FRED

Fetches 10 years of daily yield data for all 9 tenors and stores
them as YieldCurve records with source='fred_daily'.
These records are exempt from the 90-day cleanup.

Usage:
    python -m scripts.backfill_yields
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / '.env')

from loguru import logger

try:
    from fredapi import Fred
    import pandas as pd
except ImportError:
    logger.error("Required packages: pip install fredapi pandas")
    sys.exit(1)

from modules.data_storage.database import get_db_context, init_db
from modules.data_storage.schema import YieldCurve

# FRED series IDs for each tenor
TENOR_SERIES = {
    'tenor_1m': 'DGS1MO',
    'tenor_3m': 'DGS3MO',
    'tenor_6m': 'DGS6MO',
    'tenor_1y': 'DGS1',
    'tenor_2y': 'DGS2',
    'tenor_5y': 'DGS5',
    'tenor_10y': 'DGS10',
    'tenor_20y': 'DGS20',
    'tenor_30y': 'DGS30',
}

TIPS_SERIES = {
    'tips_5y': 'DFII5',
    'tips_10y': 'DFII10',
}


def backfill_yields(years: int = 10):
    api_key = os.getenv('FRED_API_KEY')
    if not api_key:
        logger.error("FRED_API_KEY not set in environment")
        sys.exit(1)

    fred = Fred(api_key=api_key)
    start_date = datetime.now() - timedelta(days=years * 365)

    logger.info(f"Fetching {years} years of Treasury yield data from FRED...")
    logger.info(f"Start date: {start_date.strftime('%Y-%m-%d')}")

    # Fetch all series
    all_series = {}
    for attr, series_id in {**TENOR_SERIES, **TIPS_SERIES}.items():
        try:
            logger.info(f"  Fetching {series_id} ({attr})...")
            data = fred.get_series(series_id, observation_start=start_date)
            all_series[attr] = data
            logger.info(f"    Got {len(data.dropna())} data points")
        except Exception as e:
            logger.error(f"    Failed: {e}")
            all_series[attr] = pd.Series(dtype=float)

    # Combine into a DataFrame aligned by date
    df = pd.DataFrame(all_series)
    df = df.dropna(how='all')  # Remove rows where all tenors are NaN
    logger.info(f"Total trading days with data: {len(df)}")

    # Store in database
    init_db()

    with get_db_context() as db:
        # Check existing daily records to avoid duplicates
        existing = db.query(YieldCurve.timestamp).filter(
            YieldCurve.source == 'fred_daily'
        ).all()
        existing_dates = {ts[0].date() for ts in existing}
        logger.info(f"Already have {len(existing_dates)} daily records in DB")

        inserted = 0
        skipped = 0

        for date, row in df.iterrows():
            date_dt = date.to_pydatetime()

            if date_dt.date() in existing_dates:
                skipped += 1
                continue

            # Build curve record
            curve = YieldCurve(
                country='US',
                timestamp=date_dt,
                source='fred_daily',
                tenor_1m=_clean(row.get('tenor_1m')),
                tenor_3m=_clean(row.get('tenor_3m')),
                tenor_6m=_clean(row.get('tenor_6m')),
                tenor_1y=_clean(row.get('tenor_1y')),
                tenor_2y=_clean(row.get('tenor_2y')),
                tenor_5y=_clean(row.get('tenor_5y')),
                tenor_10y=_clean(row.get('tenor_10y')),
                tenor_20y=_clean(row.get('tenor_20y')),
                tenor_30y=_clean(row.get('tenor_30y')),
                tips_5y=_clean(row.get('tips_5y')),
                tips_10y=_clean(row.get('tips_10y')),
            )

            # Calculate spreads
            if curve.tenor_10y is not None and curve.tenor_2y is not None:
                curve.spread_10y2y = round(curve.tenor_10y - curve.tenor_2y, 4)
            if curve.tenor_10y is not None and curve.tenor_3m is not None:
                curve.spread_10y3m = round(curve.tenor_10y - curve.tenor_3m, 4)
            if curve.tenor_30y is not None and curve.tenor_10y is not None:
                curve.spread_30y10y = round(curve.tenor_30y - curve.tenor_10y, 4)

            db.add(curve)
            inserted += 1

            if inserted % 500 == 0:
                db.commit()
                logger.info(f"  Inserted {inserted} records...")

        db.commit()
        logger.success(f"Backfill complete: {inserted} inserted, {skipped} skipped (already existed)")


def _clean(val) -> float | None:
    """Convert a pandas value to float or None."""
    if val is None:
        return None
    try:
        import math
        f = float(val)
        if math.isnan(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Backfill Treasury yield data from FRED')
    parser.add_argument('--years', type=int, default=10, help='Years of history to fetch (default: 10)')
    args = parser.parse_args()
    backfill_yields(args.years)
