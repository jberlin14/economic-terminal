"""
FX Data Fetcher

Fetches FX rates from multiple sources with automatic fallback.
Primary: Alpha Vantage (free tier: 500 calls/day)
Fallback: Yahoo Finance (yfinance - unlimited, free)
"""

import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import aiohttp
import yfinance as yf
from loguru import logger

from .config import FX_PAIRS, DXY_CONFIG, ALPHA_VANTAGE_API_KEY
from .rate_calculator import RateCalculator
from .models import FXRateData, FXUpdate


class FXDataFetcher:
    """
    Multi-source FX data fetcher with automatic fallback.
    """

    def __init__(self):
        self.api_key = ALPHA_VANTAGE_API_KEY or os.getenv('ALPHA_VANTAGE_KEY', '')
        self.base_url = 'https://www.alphavantage.co/query'
        self.call_count = 0
        self.last_reset = datetime.utcnow().date()
        self._session: Optional[aiohttp.ClientSession] = None
        self._av_semaphore = asyncio.Semaphore(1)  # Only 1 Alpha Vantage request at a time
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _check_rate_limit(self) -> bool:
        """Check if we're within API rate limits."""
        today = datetime.utcnow().date()
        if today != self.last_reset:
            self.call_count = 0
            self.last_reset = today
        return self.call_count < 500
    
    async def fetch_alpha_vantage(
        self,
        from_currency: str,
        to_currency: str = 'USD'
    ) -> Optional[float]:
        """
        Fetch rate from Alpha Vantage API with rate limiting.
        Uses semaphore to ensure only 1 request per second.

        Args:
            from_currency: Source currency code (e.g., 'EUR')
            to_currency: Target currency code (default: 'USD')

        Returns:
            Exchange rate or None if failed
        """
        if not self.api_key:
            logger.warning("Alpha Vantage API key not configured")
            return None

        if not self._check_rate_limit():
            logger.warning("Alpha Vantage daily rate limit reached")
            return None

        # Use semaphore to ensure only 1 request at a time
        async with self._av_semaphore:
            try:
                session = await self._get_session()
                params = {
                    'function': 'CURRENCY_EXCHANGE_RATE',
                    'from_currency': from_currency,
                    'to_currency': to_currency,
                    'apikey': self.api_key
                }

                async with session.get(self.base_url, params=params) as response:
                    self.call_count += 1

                    if response.status != 200:
                        logger.error(f"Alpha Vantage returned status {response.status}")
                        await asyncio.sleep(1.1)  # Rate limit: 1 req/sec
                        return None

                    data = await response.json()

                    # Check for API error messages
                    if 'Error Message' in data:
                        logger.error(f"Alpha Vantage error: {data['Error Message']}")
                        await asyncio.sleep(1.1)  # Rate limit: 1 req/sec
                        return None

                    if 'Note' in data:
                        # Rate limit warning
                        logger.warning(f"Alpha Vantage: {data['Note']}")
                        await asyncio.sleep(1.1)  # Rate limit: 1 req/sec
                        return None

                    if 'Information' in data:
                        # Rate limit message - fall back to Yahoo Finance
                        logger.debug(f"Alpha Vantage rate limit hit for {from_currency}/{to_currency}")
                        await asyncio.sleep(1.1)  # Rate limit: 1 req/sec
                        return None

                    # Extract rate
                    rate_data = data.get('Realtime Currency Exchange Rate', {})
                    rate_str = rate_data.get('5. Exchange Rate')

                    if rate_str:
                        # Successful request - respect rate limit
                        await asyncio.sleep(1.1)  # Rate limit: 1 req/sec
                        return float(rate_str)

                    logger.error(f"Unexpected Alpha Vantage response: {data}")
                    await asyncio.sleep(1.1)  # Rate limit: 1 req/sec
                    return None

            except Exception as e:
                logger.error(f"Alpha Vantage fetch error: {e}")
                await asyncio.sleep(1.1)  # Rate limit: 1 req/sec
                return None
    
    def fetch_yahoo_finance(
        self,
        symbol: str
    ) -> Optional[float]:
        """
        Fetch rate from Yahoo Finance (synchronous fallback).
        
        Args:
            symbol: Yahoo Finance ticker symbol (e.g., 'EURUSD=X')
            
        Returns:
            Exchange rate or None if failed
        """
        try:
            ticker = yf.Ticker(symbol)
            
            # Try to get the most recent price
            data = ticker.history(period='1d', interval='1m')
            
            if data.empty:
                # Try longer period if 1d is empty
                data = ticker.history(period='5d')
            
            if data.empty:
                logger.warning(f"No data from Yahoo Finance for {symbol}")
                return None
            
            # Get the most recent close price
            rate = float(data['Close'].iloc[-1])
            return rate
            
        except Exception as e:
            logger.error(f"Yahoo Finance fetch error for {symbol}: {e}")
            return None
    
    async def fetch_pair(
        self,
        pair: str
    ) -> Optional[FXRateData]:
        """
        Fetch a single currency pair from best available source.
        
        Args:
            pair: Currency pair (e.g., 'USD/EUR')
            
        Returns:
            FXRateData or None if all sources failed
        """
        if pair == 'USDX':
            return await self._fetch_dxy()
        
        if pair not in FX_PAIRS:
            logger.error(f"Unknown currency pair: {pair}")
            return None
        
        config = FX_PAIRS[pair]
        rate = None
        source = None
        
        # Try Alpha Vantage first
        if self.api_key and self._check_rate_limit():
            av_currency = config.get('alpha_vantage')
            if av_currency:
                rate = await self.fetch_alpha_vantage(av_currency, 'USD')
                if rate:
                    source = 'alpha_vantage'
                    logger.debug(f"Fetched {pair} from Alpha Vantage: {rate}")
        
        # Fallback to Yahoo Finance
        if rate is None:
            yahoo_symbol = config.get('yahoo')
            if yahoo_symbol:
                # Run sync function in executor to not block
                loop = asyncio.get_event_loop()
                rate = await loop.run_in_executor(
                    None,
                    self.fetch_yahoo_finance,
                    yahoo_symbol
                )
                if rate:
                    source = 'yahoo_finance'
                    logger.debug(f"Fetched {pair} from Yahoo Finance: {rate}")
        
        if rate is None:
            logger.error(f"Failed to fetch {pair} from all sources")
            return None
        
        # Convert to USD/XXX convention
        _, converted_rate = RateCalculator.convert_to_usd_base(pair, rate)
        
        return FXRateData(
            pair=pair,
            rate=converted_rate,
            timestamp=datetime.utcnow(),
            source=source
        )
    
    async def _fetch_dxy(self) -> Optional[FXRateData]:
        """Fetch Dollar Index (DXY)."""
        try:
            yahoo_symbol = DXY_CONFIG['yahoo']
            loop = asyncio.get_event_loop()
            rate = await loop.run_in_executor(
                None,
                self.fetch_yahoo_finance,
                yahoo_symbol
            )
            
            if rate:
                return FXRateData(
                    pair='USDX',
                    rate=round(rate, 3),
                    timestamp=datetime.utcnow(),
                    source='yahoo_finance'
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to fetch DXY: {e}")
            return None
    
    async def fetch_all(self) -> FXUpdate:
        """
        Fetch all configured currency pairs.
        
        Returns:
            FXUpdate containing all rates
        """
        rates = []
        errors = []
        
        # Fetch DXY first
        dxy = await self._fetch_dxy()
        if dxy:
            rates.append(dxy)
        else:
            errors.append("Failed to fetch DXY")
        
        # Fetch all currency pairs
        # Use asyncio.gather for concurrent fetching
        tasks = [self.fetch_pair(pair) for pair in FX_PAIRS.keys()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for pair, result in zip(FX_PAIRS.keys(), results):
            if isinstance(result, Exception):
                errors.append(f"{pair}: {str(result)}")
                logger.error(f"Error fetching {pair}: {result}")
            elif result is None:
                errors.append(f"{pair}: No data available")
            else:
                rates.append(result)
        
        return FXUpdate(
            rates=rates,
            timestamp=datetime.utcnow(),
            source='mixed',
            success=len(errors) == 0,
            errors=errors
        )
    
    def fetch_historical_yahoo(
        self,
        symbol: str,
        period: str = '1mo',
        interval: str = '1h'
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical data from Yahoo Finance.
        
        Args:
            symbol: Yahoo Finance ticker symbol
            period: Time period (1d, 5d, 1mo, 3mo, 1y)
            interval: Data interval (1m, 5m, 15m, 1h, 1d)
            
        Returns:
            List of historical data points
        """
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period, interval=interval)
            
            if data.empty:
                return []
            
            history = []
            for idx, row in data.iterrows():
                history.append({
                    'timestamp': idx.to_pydatetime(),
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': float(row['Volume'])
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return []
    
    async def fetch_sparkline_data(
        self,
        pair: str,
        hours: int = 24
    ) -> List[float]:
        """
        Fetch sparkline data for a currency pair.
        
        Args:
            pair: Currency pair
            hours: Hours of history to fetch
            
        Returns:
            List of rate values for sparkline
        """
        if pair == 'USDX':
            symbol = DXY_CONFIG['yahoo']
        elif pair in FX_PAIRS:
            symbol = FX_PAIRS[pair].get('yahoo')
        else:
            logger.error(f"Unknown pair for sparkline: {pair}")
            return []
        
        if not symbol:
            return []
        
        try:
            # Determine period based on hours
            if hours <= 24:
                period = '1d'
                interval = '15m'
            elif hours <= 168:  # 1 week
                period = '5d'
                interval = '1h'
            else:
                period = '1mo'
                interval = '1h'
            
            loop = asyncio.get_event_loop()
            history = await loop.run_in_executor(
                None,
                self.fetch_historical_yahoo,
                symbol,
                period,
                interval
            )
            
            if not history:
                return []
            
            # Extract close prices
            sparkline = [h['close'] for h in history]
            
            # If pair needs inversion, invert all values
            if pair in FX_PAIRS and FX_PAIRS[pair].get('invert', False):
                sparkline = [1.0 / v if v != 0 else 0 for v in sparkline]
            
            return sparkline[-96:]  # Last 96 points (24 hours at 15-min intervals)
            
        except Exception as e:
            logger.error(f"Error fetching sparkline for {pair}: {e}")
            return []
    
    def get_api_status(self) -> Dict[str, Any]:
        """Get current API status and usage."""
        return {
            'alpha_vantage': {
                'configured': bool(self.api_key),
                'calls_today': self.call_count,
                'calls_remaining': max(0, 500 - self.call_count),
                'last_reset': self.last_reset.isoformat()
            },
            'yahoo_finance': {
                'configured': True,
                'status': 'unlimited'
            }
        }
