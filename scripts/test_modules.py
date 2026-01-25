#!/usr/bin/env python3
"""
Module Test Runner

Tests all data modules individually to verify setup.

Usage:
    python scripts/test_modules.py
    python scripts/test_modules.py --module fx
"""

import sys
import os
import argparse
import asyncio
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")


def test_database():
    """Test database connection."""
    print("\n" + "="*50)
    print("Testing: DATABASE")
    print("="*50)
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        from modules.data_storage.database import check_connection, get_database_info
        
        info = get_database_info()
        print(f"  URL: {info['url']}")
        print(f"  SQLite: {info['is_sqlite']}")
        
        if check_connection():
            print("✓ Database connection successful")
            return True
        else:
            print("✗ Database connection failed")
            return False
            
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        return False


def test_fx_module():
    """Test FX monitor module."""
    print("\n" + "="*50)
    print("Testing: FX MONITOR")
    print("="*50)
    
    try:
        from modules.fx_monitor.config import FX_PAIRS, get_all_pairs
        from modules.fx_monitor.rate_calculator import RateCalculator
        from modules.fx_monitor.data_fetcher import FXDataFetcher
        
        # Test config
        pairs = get_all_pairs()
        print(f"  Configured pairs: {len(pairs)}")
        
        # Test rate calculator
        inverted = RateCalculator.invert_rate(1.0845)
        print(f"  Rate inversion: 1.0845 → {inverted:.4f} ✓")
        
        # Test API status
        fetcher = FXDataFetcher()
        status = fetcher.get_api_status()
        print(f"  Alpha Vantage configured: {status['alpha_vantage']['configured']}")
        print(f"  Yahoo Finance available: {status['yahoo_finance']['configured']}")
        
        # Test live fetch (one pair only)
        print("  Fetching USD/EUR (this may take a moment)...")
        
        async def fetch_test():
            rate = await fetcher.fetch_pair('USD/EUR')
            await fetcher.close()
            return rate
        
        rate = asyncio.run(fetch_test())
        
        if rate:
            print(f"✓ USD/EUR: {rate.rate} (from {rate.source})")
            return True
        else:
            print("✗ Failed to fetch USD/EUR")
            return False
            
    except Exception as e:
        print(f"✗ FX module test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_yields_module():
    """Test yields monitor module."""
    print("\n" + "="*50)
    print("Testing: YIELDS MONITOR")
    print("="*50)
    
    try:
        from modules.yields_monitor.config import YIELD_SERIES
        from modules.yields_monitor.data_fetcher import YieldsDataFetcher
        
        # Test config
        print(f"  Configured tenors: {len(YIELD_SERIES)}")
        
        # Test FRED connection
        fetcher = YieldsDataFetcher()
        status = fetcher.check_api_status()
        
        print(f"  FRED API configured: {status['configured']}")
        
        if status['configured']:
            print("  Fetching yield curve (this may take a moment)...")
            curve = fetcher.fetch_yield_curve()
            
            if curve:
                print(f"✓ Yield curve fetched:")
                print(f"    10Y: {curve.tenor_10y}%")
                print(f"    2Y: {curve.tenor_2y}%")
                print(f"    10Y-2Y spread: {curve.spread_10y2y}%")
                return True
            else:
                print("✗ Failed to fetch yield curve")
                return False
        else:
            print("⚠ FRED API key not configured - skipping live test")
            return True
            
    except Exception as e:
        print(f"✗ Yields module test failed: {e}")
        return False


def test_risk_detector():
    """Test risk detector module."""
    print("\n" + "="*50)
    print("Testing: RISK DETECTOR")
    print("="*50)
    
    try:
        from modules.risk_detector.config import ALERT_THRESHOLDS, CRITICAL_KEYWORDS
        from modules.risk_detector.fx_rules import detect_fx_risks
        from modules.risk_detector.yield_rules import detect_yield_risks
        from modules.risk_detector.models import RiskAlertData
        
        # Test config
        print(f"  FX threshold HIGH: {ALERT_THRESHOLDS['FX_HIGH']}%")
        print(f"  FX threshold CRITICAL: {ALERT_THRESHOLDS['FX_CRITICAL']}%")
        print(f"  Critical keywords: {len(CRITICAL_KEYWORDS)}")
        
        # Test FX risk detection
        test_fx_data = {
            'USD/JPY': {'change_1h': 1.5, 'rate': 149.50},
            'USD/EUR': {'change_1h': 0.3, 'rate': 0.92}
        }
        
        fx_risks = detect_fx_risks(test_fx_data)
        print(f"  FX risks detected: {len(fx_risks)}")
        
        if fx_risks:
            print(f"    → {fx_risks[0].message}")
        
        # Test yield risk detection
        test_yield_data = {'10Y': 4.25, '2Y': 4.50, '3M': 4.75}
        
        yield_risks = detect_yield_risks(test_yield_data)
        print(f"  Yield risks detected: {len(yield_risks)}")
        
        if yield_risks:
            print(f"    → {yield_risks[0].message}")
        
        print("✓ Risk detector working")
        return True
        
    except Exception as e:
        print(f"✗ Risk detector test failed: {e}")
        return False


def run_all_tests():
    """Run all module tests."""
    print("\n" + "="*60)
    print("ECONOMIC TERMINAL - MODULE TESTS")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    results = []
    
    results.append(("Database", test_database()))
    results.append(("FX Monitor", test_fx_module()))
    results.append(("Yields Monitor", test_yields_module()))
    results.append(("Risk Detector", test_risk_detector()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("ALL TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1


def main():
    parser = argparse.ArgumentParser(description='Test Economic Terminal modules')
    parser.add_argument('--module', '-m', choices=['db', 'fx', 'yields', 'risk', 'all'],
                       default='all', help='Module to test')
    
    args = parser.parse_args()
    
    from dotenv import load_dotenv
    load_dotenv()
    
    if args.module == 'all':
        return run_all_tests()
    elif args.module == 'db':
        return 0 if test_database() else 1
    elif args.module == 'fx':
        return 0 if test_fx_module() else 1
    elif args.module == 'yields':
        return 0 if test_yields_module() else 1
    elif args.module == 'risk':
        return 0 if test_risk_detector() else 1


if __name__ == '__main__':
    sys.exit(main())
