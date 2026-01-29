"""
Timezone Utilities

Centralized timezone handling for the application.
All times use US Eastern timezone for consistency with market hours.
"""

import os
from datetime import datetime
from typing import Optional
import pytz

# US Eastern timezone (handles EDT/EST automatically)
eastern_tz = pytz.timezone(os.getenv('TIMEZONE', 'America/New_York'))


def get_current_time() -> datetime:
    """
    Get current time in Eastern timezone.

    Returns:
        Timezone-aware datetime object in US Eastern time

    Example:
        >>> now = get_current_time()
        >>> print(now)
        2026-01-26 10:30:45.123456-05:00
    """
    return datetime.now(eastern_tz)


def format_timestamp(dt: Optional[datetime] = None, format_str: str = '%Y-%m-%d %H:%M:%S %Z') -> str:
    """
    Format a datetime object as a string in Eastern timezone.

    Args:
        dt: Datetime to format (defaults to current time)
        format_str: strftime format string

    Returns:
        Formatted timestamp string

    Example:
        >>> format_timestamp()
        '2026-01-26 10:30:45 EST'
        >>> format_timestamp(some_dt, '%Y-%m-%d')
        '2026-01-26'
    """
    if dt is None:
        dt = get_current_time()
    elif dt.tzinfo is None:
        # Convert naive datetime to Eastern
        dt = eastern_tz.localize(dt)
    elif dt.tzinfo != eastern_tz:
        # Convert to Eastern if in different timezone
        dt = dt.astimezone(eastern_tz)

    return dt.strftime(format_str)


def convert_to_eastern(dt: datetime) -> datetime:
    """
    Convert any datetime to Eastern timezone.

    Args:
        dt: Datetime to convert (can be naive or timezone-aware)

    Returns:
        Timezone-aware datetime in Eastern time

    Example:
        >>> utc_time = datetime.utcnow()
        >>> eastern_time = convert_to_eastern(utc_time)
    """
    if dt.tzinfo is None:
        # Assume UTC if naive
        dt = pytz.utc.localize(dt)

    return dt.astimezone(eastern_tz)


def get_market_hours() -> dict:
    """
    Get US market hours in Eastern time.

    Returns:
        Dictionary with market open/close times

    Example:
        >>> hours = get_market_hours()
        >>> print(hours['market_open'])  # 9:30 AM ET
        >>> print(hours['market_close'])  # 4:00 PM ET
    """
    return {
        'market_open': '09:30',
        'market_close': '16:00',
        'pre_market': '04:00',
        'after_hours': '20:00',
        'timezone': 'America/New_York'
    }


def is_market_hours() -> bool:
    """
    Check if current time is during regular market hours (9:30 AM - 4:00 PM ET, Mon-Fri).

    Returns:
        True if during market hours, False otherwise

    Example:
        >>> if is_market_hours():
        ...     print("Markets are open!")
    """
    now = get_current_time()

    # Check if weekday (0 = Monday, 4 = Friday)
    if now.weekday() > 4:
        return False

    # Check if between 9:30 AM and 4:00 PM ET
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

    return market_open <= now <= market_close