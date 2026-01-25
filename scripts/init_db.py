#!/usr/bin/env python3
"""
Database Initialization Script

Creates all necessary database tables.
Safe to run multiple times - won't destroy existing data.

Usage:
    python scripts/init_db.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | {message}")


def main():
    print("\n" + "="*60)
    print("ECONOMIC TERMINAL - DATABASE INITIALIZATION")
    print("="*60 + "\n")
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Get database URL
    db_url = os.getenv('DATABASE_URL', 'sqlite:///./economic_data.db')
    print(f"Database: {db_url[:50]}...")
    
    # Initialize database
    print("\nCreating database tables...")
    
    try:
        from modules.data_storage.database import init_db, check_connection
        
        # Check connection first
        if not check_connection():
            print("❌ Database connection failed!")
            print("   Check your DATABASE_URL in .env file")
            return 1
        
        print("✓ Database connection successful")
        
        # Create tables
        init_db()
        
        print("\n" + "="*60)
        print("DATABASE INITIALIZATION COMPLETE")
        print("="*60 + "\n")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
