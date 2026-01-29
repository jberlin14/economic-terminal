#!/usr/bin/env python3
"""
Cleanup script to remove failed indicators from the database.

This script removes indicators that failed to fetch during initialization.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.data_storage.database import get_db_context
from modules.data_storage.schema import EconomicIndicator, IndicatorValue
from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stdout, format="<level>{level: <8}</level> | {message}", level="INFO")

# List of failed series IDs to remove
FAILED_SERIES = [
    'USUTIL',
    'CUSR0000SETE',
    'PPIFGS',
    'PPITMS',
    'PPIWTS',
    'PCU423830423830',
    'PPITRS',
    'PPIFFS',
    'PPIDCG',
    'PPIITM',
]


def cleanup_failed_indicators():
    """Remove failed indicators from the database."""

    print("=" * 60)
    print("CLEANUP FAILED INDICATORS")
    print("=" * 60)

    with get_db_context() as db:
        removed_count = 0
        values_removed = 0

        for series_id in FAILED_SERIES:
            # Check if indicator exists
            indicator = db.query(EconomicIndicator).filter(
                EconomicIndicator.series_id == series_id
            ).first()

            if indicator:
                # Delete associated values first
                values = db.query(IndicatorValue).filter(
                    IndicatorValue.series_id == series_id
                ).delete()

                # Delete indicator
                db.delete(indicator)
                db.commit()

                removed_count += 1
                values_removed += values
                logger.info(f"Removed {series_id} ({values} data points)")
            else:
                logger.debug(f"{series_id} not found in database")

        print("\n" + "=" * 60)
        print(f"Cleanup complete:")
        print(f"  Indicators removed: {removed_count}")
        print(f"  Data points removed: {values_removed}")
        print("=" * 60)


if __name__ == '__main__':
    cleanup_failed_indicators()
