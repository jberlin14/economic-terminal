#!/usr/bin/env python3
"""
Health Check Script

Comprehensive health check for the Economic Terminal.
Tests database, API connections, and module functionality.
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import traceback

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.data_storage.database import check_connection, get_db_context
from modules.utils.timezone import get_current_time, format_timestamp

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    """Print formatted header"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'=' * 60}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}{text.center(60)}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}{'=' * 60}{Colors.END}\n")

def print_test(name, status, message=""):
    """Print test result"""
    status_icon = {
        'pass': f"{Colors.GREEN}[+]{Colors.END}",
        'fail': f"{Colors.RED}[x]{Colors.END}",
        'warn': f"{Colors.YELLOW}[!]{Colors.END}",
        'info': f"{Colors.BLUE}[i]{Colors.END}"
    }
    icon = status_icon.get(status, status_icon['info'])
    print(f"{icon} {name}: {message}")

def test_environment():
    """Test environment variables"""
    print_header("ENVIRONMENT CONFIGURATION")

    required_vars = ['DATABASE_URL', 'FRED_API_KEY']
    optional_vars = ['ALPHA_VANTAGE_KEY', 'SENDGRID_API_KEY', 'TIMEZONE']

    all_good = True

    for var in required_vars:
        if os.getenv(var):
            print_test(var, 'pass', 'Configured')
        else:
            print_test(var, 'fail', 'MISSING - Required')
            all_good = False

    for var in optional_vars:
        if os.getenv(var):
            print_test(var, 'pass', 'Configured')
        else:
            print_test(var, 'warn', 'Not configured (optional)')

    # Timezone check
    from modules.utils.timezone import eastern_tz
    current_time = get_current_time()
    print_test('Current Time', 'info', format_timestamp(current_time))
    print_test('Timezone', 'info', str(eastern_tz))

    return all_good

def test_database():
    """Test database connection and tables"""
    print_header("DATABASE")

    try:
        # Test connection
        if check_connection():
            print_test('Connection', 'pass', 'Successfully connected')
        else:
            print_test('Connection', 'fail', 'Cannot connect to database')
            return False

        # Test tables
        with get_db_context() as db:
            from modules.data_storage.schema import (
                FXUpdate, YieldCurveSnapshot, CreditSpread,
                NewsArticle, RiskAlert, EconomicIndicator, IndicatorValue
            )

            tables = [
                ('fx_updates', FXUpdate),
                ('yield_curves', YieldCurveSnapshot),
                ('credit_spreads', CreditSpread),
                ('news_articles', NewsArticle),
                ('risk_alerts', RiskAlert),
                ('economic_indicators', EconomicIndicator),
                ('indicator_values', IndicatorValue),
            ]

            for table_name, model in tables:
                try:
                    count = db.query(model).count()
                    print_test(f'Table: {table_name}', 'pass', f'{count} records')
                except Exception as e:
                    print_test(f'Table: {table_name}', 'fail', str(e))
                    return False

        return True

    except Exception as e:
        print_test('Database', 'fail', str(e))
        traceback.print_exc()
        return False

def test_economic_indicators():
    """Test economic indicators module"""
    print_header("ECONOMIC INDICATORS")

    try:
        from modules.economic_indicators import IndicatorDataFetcher, IndicatorStorage
        from modules.data_storage.database import get_db_context

        # Test FRED API
        fetcher = IndicatorDataFetcher()
        if fetcher.is_available():
            print_test('FRED API', 'pass', 'Connected')
        else:
            print_test('FRED API', 'fail', 'Cannot connect (check FRED_API_KEY)')
            return False

        # Test database
        with get_db_context() as db:
            storage = IndicatorStorage(db)
            indicators = storage.get_all_indicators()
            print_test('Indicators in DB', 'info', f'{len(indicators)} series')

            if len(indicators) == 0:
                print_test('Indicators', 'warn', 'No data - run scripts/init_indicators.py')
            else:
                # Check for recent data
                sample = indicators[0]
                date_range = storage.get_date_range(sample.series_id)
                if date_range:
                    print_test(f'Sample: {sample.series_id}', 'info',
                              f"Latest: {date_range['end_date']}")
                else:
                    print_test(f'Sample: {sample.series_id}', 'warn', 'No data points')

        return True

    except Exception as e:
        print_test('Economic Indicators', 'fail', str(e))
        traceback.print_exc()
        return False

def test_fx_monitor():
    """Test FX monitor module"""
    print_header("FX MONITOR")

    try:
        from modules.fx_monitor.data_fetcher import FXDataFetcher
        from modules.fx_monitor.storage import get_latest_update

        # Check API key
        if not os.getenv('ALPHA_VANTAGE_KEY'):
            print_test('Alpha Vantage API', 'warn', 'API key not configured')
            return False

        print_test('Alpha Vantage API', 'pass', 'Key configured')

        # Check database
        latest = get_latest_update()
        if latest:
            print_test('Latest Data', 'info', f'{latest.timestamp.strftime("%Y-%m-%d %H:%M:%S")}')
            print_test('Pairs Tracked', 'info', f'{len(latest.rates)} currency pairs')
        else:
            print_test('Latest Data', 'warn', 'No data - scheduler will populate')

        return True

    except Exception as e:
        print_test('FX Monitor', 'fail', str(e))
        return False

def test_yields_monitor():
    """Test yields monitor module"""
    print_header("YIELDS MONITOR")

    try:
        from modules.yields_monitor.data_fetcher import YieldsDataFetcher
        from modules.yields_monitor.storage import get_latest_curve

        # Check API
        print_test('Treasury API', 'pass', 'Using treasury.gov (no key required)')

        # Check database
        latest = get_latest_curve()
        if latest:
            print_test('Latest Curve', 'info', f'{latest.timestamp.strftime("%Y-%m-%d %H:%M:%S")}')
            print_test('10Y-2Y Spread', 'info', f'{latest.spread_10y2y:.2f} bps')
        else:
            print_test('Latest Curve', 'warn', 'No data - scheduler will populate')

        return True

    except Exception as e:
        print_test('Yields Monitor', 'fail', str(e))
        return False

def test_news_aggregator():
    """Test news aggregator module"""
    print_header("NEWS AGGREGATOR")

    try:
        from modules.news_aggregator.storage import get_recent_articles

        # Check database
        recent = get_recent_articles(hours=24, limit=5)
        if recent:
            print_test('Recent Articles', 'info', f'{len(recent)} in last 24 hours')
            print_test('Latest Article', 'info', recent[0].title[:60] + '...')
        else:
            print_test('Recent Articles', 'warn', 'No recent articles - scheduler will fetch')

        return True

    except Exception as e:
        print_test('News Aggregator', 'fail', str(e))
        return False

def test_risk_detector():
    """Test risk detector module"""
    print_header("RISK DETECTOR")

    try:
        from modules.risk_detector.alert_manager import AlertManager
        from modules.data_storage.database import get_db_context

        with get_db_context() as db:
            manager = AlertManager(db)
            active = manager.get_active_alerts()
            critical = manager.get_critical_alerts()

            print_test('Active Alerts', 'info', f'{len(active)} alerts')
            print_test('Critical Alerts', 'info', f'{len(critical)} critical')

            if len(critical) > 0:
                print_test('Latest Critical', 'warn', critical[0].title)

        return True

    except Exception as e:
        print_test('Risk Detector', 'fail', str(e))
        return False

def main():
    """Run all health checks"""
    print(f"\n{Colors.BOLD}Economic Terminal - Health Check{Colors.END}")
    print(f"Timestamp: {format_timestamp()}")

    results = {
        'Environment': test_environment(),
        'Database': test_database(),
        'Economic Indicators': test_economic_indicators(),
        'FX Monitor': test_fx_monitor(),
        'Yields Monitor': test_yields_monitor(),
        'News Aggregator': test_news_aggregator(),
        'Risk Detector': test_risk_detector(),
    }

    # Summary
    print_header("SUMMARY")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for module, status in results.items():
        status_str = f"{Colors.GREEN}PASS{Colors.END}" if status else f"{Colors.RED}FAIL{Colors.END}"
        print(f"  {module}: {status_str}")

    print(f"\n{Colors.BOLD}Overall: {passed}/{total} modules healthy{Colors.END}\n")

    if passed == total:
        print(f"{Colors.GREEN}System is healthy and ready!{Colors.END}\n")
        return 0
    else:
        print(f"{Colors.YELLOW}Some modules need attention.{Colors.END}\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())
