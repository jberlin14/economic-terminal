"""
FX Monitor Test Script

Tests all components of the FX Monitor module.
Run this to verify your setup before deployment.

Usage:
    python -m modules.fx_monitor.test
"""

import asyncio
import sys
from datetime import datetime
from loguru import logger

# Configure logging for tests
logger.remove()
logger.add(sys.stdout, level="DEBUG", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")


def test_config():
    """Test configuration loading."""
    print("\n" + "="*60)
    print("TEST: Configuration")
    print("="*60)
    
    from .config import (
        FX_PAIRS, DXY_CONFIG, RISK_THRESHOLDS,
        get_all_pairs, get_pair_config, get_decimal_places
    )
    
    # Test pair list
    pairs = get_all_pairs()
    print(f"✓ Configured {len(pairs)} currency pairs: {pairs}")
    
    # Test DXY config
    assert DXY_CONFIG['name'] == 'USDX'
    print(f"✓ DXY config loaded: {DXY_CONFIG}")
    
    # Test pair configs
    for pair in list(FX_PAIRS.keys())[:3]:
        config = get_pair_config(pair)
        decimals = get_decimal_places(pair)
        print(f"  {pair}: invert={config.get('invert')}, decimals={decimals}")
    
    # Test risk thresholds
    print(f"✓ Risk thresholds: HIGH={RISK_THRESHOLDS['FX_HIGH']}%, CRITICAL={RISK_THRESHOLDS['FX_CRITICAL']}%")
    
    print("✓ Configuration tests PASSED")
    return True


def test_rate_calculator():
    """Test rate calculations."""
    print("\n" + "="*60)
    print("TEST: Rate Calculator")
    print("="*60)
    
    from .rate_calculator import RateCalculator
    
    # Test inversion
    eur_usd = 1.0845
    usd_eur = RateCalculator.invert_rate(eur_usd)
    print(f"✓ Rate inversion: EUR/USD {eur_usd} → USD/EUR {usd_eur:.4f}")
    assert abs(usd_eur - 0.9221) < 0.001
    
    # Test convention conversion
    pair, rate = RateCalculator.convert_to_usd_base('USD/EUR', eur_usd)
    print(f"✓ Convention conversion: {pair} = {rate}")
    
    # Test change calculation
    change = RateCalculator.calculate_change(105.0, 100.0)
    print(f"✓ Change calculation: 100 → 105 = {change}%")
    assert change == 5.0
    
    # Test risk detection
    risk = RateCalculator.detect_risk('USD/JPY', 1.5)
    print(f"✓ Risk detection (1.5% move): {risk}")
    assert risk == 'HIGH'
    
    risk = RateCalculator.detect_risk('USD/JPY', 2.5)
    print(f"✓ Risk detection (2.5% move): {risk}")
    assert risk == 'CRITICAL'
    
    # Test formatting
    formatted = RateCalculator.format_rate('USD/JPY', 149.4567)
    print(f"✓ Rate formatting: USD/JPY = {formatted}")
    
    print("✓ Rate calculator tests PASSED")
    return True


def test_models():
    """Test Pydantic models."""
    print("\n" + "="*60)
    print("TEST: Data Models")
    print("="*60)
    
    from .models import FXRateData, FXUpdate, FXAlert
    
    # Test FXRateData
    rate = FXRateData(
        pair='USD/JPY',
        rate=149.50,
        change_1h=0.5,
        change_24h=1.2
    )
    print(f"✓ FXRateData created: {rate.pair} = {rate.rate}")
    
    # Test validation
    try:
        invalid = FXRateData(pair='EUR/USD', rate=1.08)  # Wrong convention
        print("✗ Should have rejected EUR/USD convention")
        return False
    except ValueError:
        print("✓ Correctly rejected non-USD/XXX pair")
    
    # Test FXUpdate
    update = FXUpdate(
        rates=[rate],
        source='test'
    )
    print(f"✓ FXUpdate created with {len(update.rates)} rates")
    
    # Test FXAlert
    alert = FXAlert(
        pair='USD/JPY',
        severity='HIGH',
        change_percent=1.5,
        current_rate=149.50,
        previous_rate=147.28,
        message='USD/JPY moved 1.5% in 1 hour'
    )
    print(f"✓ FXAlert created: {alert.severity}")
    
    print("✓ Model tests PASSED")
    return True


async def test_data_fetcher():
    """Test data fetching from APIs."""
    print("\n" + "="*60)
    print("TEST: Data Fetcher (Live API)")
    print("="*60)
    
    from .data_fetcher import FXDataFetcher
    
    fetcher = FXDataFetcher()
    
    try:
        # Check API status
        status = fetcher.get_api_status()
        print(f"  Alpha Vantage configured: {status['alpha_vantage']['configured']}")
        print(f"  Yahoo Finance configured: {status['yahoo_finance']['configured']}")
        
        # Fetch a single pair (using Yahoo as fallback if Alpha Vantage not configured)
        print("\nFetching USD/EUR...")
        rate = await fetcher.fetch_pair('USD/EUR')
        
        if rate:
            print(f"✓ Fetched USD/EUR: {rate.rate} from {rate.source}")
        else:
            print("✗ Failed to fetch USD/EUR")
            return False
        
        # Fetch DXY
        print("\nFetching DXY...")
        dxy = await fetcher.fetch_pair('USDX')
        
        if dxy:
            print(f"✓ Fetched USDX (DXY): {dxy.rate}")
        else:
            print("⚠ DXY fetch failed (might be outside market hours)")
        
        # Fetch all pairs (this might take a few seconds)
        print("\nFetching all pairs (this may take a moment)...")
        update = await fetcher.fetch_all()
        
        print(f"✓ Fetched {len(update.rates)} rates")
        if update.errors:
            print(f"  Errors: {update.errors}")
        
        for rate in update.rates[:5]:  # Show first 5
            print(f"  {rate.pair}: {rate.rate} ({rate.source})")
        
        if len(update.rates) > 5:
            print(f"  ... and {len(update.rates) - 5} more")
        
        print("✓ Data fetcher tests PASSED")
        return True
        
    except Exception as e:
        print(f"✗ Data fetcher test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await fetcher.close()


def test_all():
    """Run all tests."""
    print("\n" + "="*60)
    print("FX MONITOR MODULE TESTS")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    results = []
    
    # Synchronous tests
    results.append(("Configuration", test_config()))
    results.append(("Rate Calculator", test_rate_calculator()))
    results.append(("Data Models", test_models()))
    
    # Async tests
    results.append(("Data Fetcher", asyncio.run(test_data_fetcher())))
    
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
    
    print("\n" + ("="*60))
    if all_passed:
        print("ALL TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
    print("="*60 + "\n")
    
    return all_passed


if __name__ == '__main__':
    success = test_all()
    sys.exit(0 if success else 1)
