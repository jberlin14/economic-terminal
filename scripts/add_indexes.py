#!/usr/bin/env python3
"""
Add Database Indexes

Adds performance indexes to existing tables.
Run this to improve query performance.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.data_storage.database import get_engine, init_db
from sqlalchemy import text
from loguru import logger

def add_indexes():
    """Add indexes for better query performance"""

    engine = get_engine()

    # Define indexes to add (only if they don't exist)
    indexes = [
        # News articles - frequently queried by timestamp
        "CREATE INDEX IF NOT EXISTS ix_news_timestamp ON news_articles(timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS ix_news_source ON news_articles(source)",
        "CREATE INDEX IF NOT EXISTS ix_news_severity ON news_articles(severity)",

        # Risk alerts - queried by status and severity
        "CREATE INDEX IF NOT EXISTS ix_alerts_status ON risk_alerts(status)",
        "CREATE INDEX IF NOT EXISTS ix_alerts_severity ON risk_alerts(severity)",
        "CREATE INDEX IF NOT EXISTS ix_alerts_created ON risk_alerts(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS ix_alerts_status_severity ON risk_alerts(status, severity)",

        # FX updates - timestamp queries
        "CREATE INDEX IF NOT EXISTS ix_fx_timestamp ON fx_updates(timestamp DESC)",

        # Yield curves - timestamp queries
        "CREATE INDEX IF NOT EXISTS ix_yields_timestamp ON yield_curves(timestamp DESC)",

        # Credit spreads - timestamp and index queries
        "CREATE INDEX IF NOT EXISTS ix_credit_timestamp ON credit_spreads(timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS ix_credit_index ON credit_spreads(index_name)",

        # Economic indicators - report group queries
        "CREATE INDEX IF NOT EXISTS ix_indicators_report ON economic_indicators(report_group)",

        # Indicator values - date range queries are common
        "CREATE INDEX IF NOT EXISTS ix_values_date_desc ON indicator_values(date DESC)",
    ]

    logger.info("Adding database indexes for performance...")

    with engine.connect() as conn:
        for idx_sql in indexes:
            try:
                conn.execute(text(idx_sql))
                conn.commit()
                idx_name = idx_sql.split('INDEX')[1].split('ON')[0].strip()
                if 'IF NOT EXISTS' in idx_sql:
                    idx_name = idx_name.replace('IF NOT EXISTS', '').strip()
                logger.success(f"  Added/verified: {idx_name}")
            except Exception as e:
                logger.warning(f"  Could not add index: {e}")

    logger.success("Index creation complete!")

if __name__ == '__main__':
    try:
        add_indexes()
        print("\nIndexes have been added successfully!")
        print("This will improve query performance, especially for:")
        print("  - News article searches")
        print("  - Risk alert filtering")
        print("  - Historical data queries")
        print("  - Dashboard data loading")
    except Exception as e:
        print(f"\nError adding indexes: {e}")
        sys.exit(1)
