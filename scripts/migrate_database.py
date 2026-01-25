#!/usr/bin/env python3
"""
Database Migration Script

Safely migrates database schema by backing up and recreating tables.
"""

import sys
import os
import shutil
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def main():
    print("\n" + "="*60)
    print("DATABASE MIGRATION")
    print("="*60 + "\n")

    # Get database path
    db_url = os.getenv('DATABASE_URL', 'sqlite:///./economic_data.db')

    if not db_url.startswith('sqlite:///'):
        print("ERROR: This script only works with SQLite databases")
        print(f"Current DATABASE_URL: {db_url}")
        return 1

    # Extract file path from URL
    db_path = db_url.replace('sqlite:///', '')
    db_path = db_path.lstrip('/')  # Remove leading slash for relative paths

    # Handle absolute paths (4 slashes in URL)
    if db_url.startswith('sqlite:////'):
        db_path = '/' + db_path

    print(f"Database path: {db_path}")

    # Check if database exists
    if os.path.exists(db_path):
        # Create backup
        backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"\nBacking up database to: {backup_path}")
        shutil.copy2(db_path, backup_path)
        print("[OK] Backup created")

        # Remove old database
        print(f"\nRemoving old database: {db_path}")
        os.remove(db_path)
        print("[OK] Old database removed")
    else:
        print(f"\nNo existing database found at: {db_path}")

    # Initialize new database
    print("\nInitializing database with new schema...")

    from modules.data_storage.database import init_db, check_connection

    if not check_connection():
        print("[ERROR] Database connection failed!")
        return 1

    print("[OK] Database connection successful")

    init_db()

    print("\n" + "="*60)
    print("MIGRATION COMPLETE")
    print("="*60)
    print("\nNext steps:")
    print("  1. Run: python scripts/manual_fetch.py")
    print("  2. Verify data in dashboard")
    print()

    return 0


if __name__ == '__main__':
    sys.exit(main())
