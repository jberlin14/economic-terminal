"""
Economic Calendar - Release Tracking and Fetching

Tracks major economic releases using FRED's release dates API for accurate scheduling.
Falls back to heuristic estimation with weekend adjustment when API data unavailable.
"""

import os
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import requests
from loguru import logger

# FRED API configuration
FRED_API_KEY = os.getenv('FRED_API_KEY')
FRED_BASE_URL = "https://api.stlouisfed.org/fred"


class ReleaseImportance(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Release:
    """Represents an economic data release."""
    id: str
    name: str
    series_id: str  # FRED series ID for the main indicator
    importance: ReleaseImportance
    typical_time: str  # e.g., "08:30 ET"
    frequency: str  # monthly, weekly, quarterly
    description: str
    fred_release_id: Optional[int] = None  # FRED release ID for date lookup

    # Release-specific data (populated when fetched)
    release_date: Optional[date] = None
    previous_value: Optional[float] = None
    previous_date: Optional[date] = None
    consensus_estimate: Optional[float] = None
    actual_value: Optional[float] = None
    surprise: Optional[float] = None  # actual - consensus
    surprise_percent: Optional[float] = None


# Key economic releases to track
# fred_release_id values from https://fred.stlouisfed.org/releases
TRACKED_RELEASES = {
    # Employment
    "employment_situation": Release(
        id="employment_situation",
        name="Employment Situation (NFP)",
        series_id="PAYEMS",
        importance=ReleaseImportance.HIGH,
        typical_time="08:30 ET",
        frequency="monthly",
        description="Nonfarm payrolls, unemployment rate - First Friday of month",
        fred_release_id=50,
    ),
    "jobless_claims": Release(
        id="jobless_claims",
        name="Initial Jobless Claims",
        series_id="ICSA",
        importance=ReleaseImportance.HIGH,
        typical_time="08:30 ET",
        frequency="weekly",
        description="Weekly unemployment claims - Every Thursday",
        fred_release_id=113,
    ),
    "jolts": Release(
        id="jolts",
        name="JOLTS Job Openings",
        series_id="JTSJOL",
        importance=ReleaseImportance.MEDIUM,
        typical_time="10:00 ET",
        frequency="monthly",
        description="Job openings and labor turnover",
        fred_release_id=110,
    ),

    # Inflation
    "cpi": Release(
        id="cpi",
        name="Consumer Price Index (CPI)",
        series_id="CPIAUCSL",
        importance=ReleaseImportance.HIGH,
        typical_time="08:30 ET",
        frequency="monthly",
        description="Consumer inflation - Mid-month release",
        fred_release_id=10,
    ),
    "pce": Release(
        id="pce",
        name="PCE Price Index",
        series_id="PCEPI",
        importance=ReleaseImportance.HIGH,
        typical_time="08:30 ET",
        frequency="monthly",
        description="Fed's preferred inflation measure",
        fred_release_id=54,
    ),
    "ppi": Release(
        id="ppi",
        name="Producer Price Index (PPI)",
        series_id="PPIACO",
        importance=ReleaseImportance.MEDIUM,
        typical_time="08:30 ET",
        frequency="monthly",
        description="Wholesale/producer inflation",
        fred_release_id=46,
    ),

    # GDP & Output
    "gdp": Release(
        id="gdp",
        name="GDP (Advance/Preliminary/Final)",
        series_id="GDP",
        importance=ReleaseImportance.HIGH,
        typical_time="08:30 ET",
        frequency="quarterly",
        description="Gross Domestic Product",
        fred_release_id=53,
    ),
    "industrial_production": Release(
        id="industrial_production",
        name="Industrial Production",
        series_id="INDPRO",
        importance=ReleaseImportance.MEDIUM,
        typical_time="09:15 ET",
        frequency="monthly",
        description="Manufacturing and industrial output",
        fred_release_id=13,
    ),

    # Consumer
    "retail_sales": Release(
        id="retail_sales",
        name="Retail Sales",
        series_id="RSXFS",
        importance=ReleaseImportance.HIGH,
        typical_time="08:30 ET",
        frequency="monthly",
        description="Consumer spending indicator",
        fred_release_id=63,
    ),
    "consumer_confidence": Release(
        id="consumer_confidence",
        name="Consumer Confidence",
        series_id="UMCSENT",
        importance=ReleaseImportance.MEDIUM,
        typical_time="10:00 ET",
        frequency="monthly",
        description="University of Michigan Consumer Sentiment",
        fred_release_id=14,
    ),

    # Housing
    "housing_starts": Release(
        id="housing_starts",
        name="Housing Starts",
        series_id="HOUST",
        importance=ReleaseImportance.MEDIUM,
        typical_time="08:30 ET",
        frequency="monthly",
        description="New residential construction",
        fred_release_id=97,
    ),
    "existing_home_sales": Release(
        id="existing_home_sales",
        name="Existing Home Sales",
        series_id="EXHOSLUSM495S",
        importance=ReleaseImportance.MEDIUM,
        typical_time="10:00 ET",
        frequency="monthly",
        description="Sales of existing homes",
        fred_release_id=99,
    ),

    # Fed & Rates
    "fomc_decision": Release(
        id="fomc_decision",
        name="FOMC Rate Decision",
        series_id="FEDFUNDS",
        importance=ReleaseImportance.HIGH,
        typical_time="14:00 ET",
        frequency="monthly",
        description="Federal Reserve interest rate decision",
        fred_release_id=None,  # No FRED release for FOMC — use heuristic
    ),
}


def _skip_weekend(d: date) -> date:
    """Adjust a date to the next business day if it falls on a weekend."""
    if d.weekday() == 5:  # Saturday -> Monday
        return d + timedelta(days=2)
    elif d.weekday() == 6:  # Sunday -> Monday
        return d + timedelta(days=1)
    return d


class EconomicCalendar:
    """
    Fetches and manages economic calendar data.
    Uses FRED release dates API for accurate scheduling.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or FRED_API_KEY
        self.releases = TRACKED_RELEASES.copy()
        self._release_date_cache: Dict[int, List[date]] = {}

    def is_available(self) -> bool:
        """Check if FRED API is available."""
        return bool(self.api_key)

    def _get_fred_release_dates(self, fred_release_id: int) -> List[date]:
        """
        Fetch upcoming release dates from FRED's release/dates endpoint.
        Returns list of dates sorted ascending.
        """
        if fred_release_id in self._release_date_cache:
            return self._release_date_cache[fred_release_id]

        if not self.is_available():
            return []

        try:
            url = f"{FRED_BASE_URL}/release/dates"
            params = {
                "release_id": fred_release_id,
                "api_key": self.api_key,
                "file_type": "json",
                "limit": 10,
                "sort_order": "desc",
                "include_release_dates_with_no_data": "true"
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            dates = []
            for entry in data.get("release_dates", []):
                try:
                    d = datetime.strptime(entry["date"], "%Y-%m-%d").date()
                    dates.append(d)
                except (ValueError, KeyError):
                    continue

            dates.sort()
            self._release_date_cache[fred_release_id] = dates
            return dates

        except Exception as e:
            logger.error(f"Failed to fetch FRED release dates for release_id={fred_release_id}: {e}")
            return []

    def _get_series_observations(self, series_id: str, limit: int = 5) -> List[Dict]:
        """Fetch recent observations for a series."""
        if not self.is_available():
            return []

        try:
            url = f"{FRED_BASE_URL}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "limit": limit,
                "sort_order": "desc"
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            return data.get("observations", [])
        except Exception as e:
            logger.error(f"Failed to fetch observations for {series_id}: {e}")
            return []

    def get_upcoming_releases(self, days_ahead: int = 14) -> List[Release]:
        """
        Get list of upcoming economic releases.
        Uses FRED release dates API for accuracy, with heuristic fallback.
        """
        upcoming = []
        today = date.today()
        end_date = today + timedelta(days=days_ahead)

        for release_id, release in self.releases.items():
            # Get latest observations for previous value
            observations = self._get_series_observations(release.series_id, limit=2)

            if observations:
                latest = observations[0]
                try:
                    release.previous_value = float(latest["value"]) if latest["value"] != "." else None
                    release.previous_date = datetime.strptime(latest["date"], "%Y-%m-%d").date()
                except (ValueError, KeyError):
                    pass

            # Get next release date — prefer FRED API, fall back to heuristic
            next_release = None

            if release.fred_release_id:
                fred_dates = self._get_fred_release_dates(release.fred_release_id)
                # Find the next date >= today
                for d in fred_dates:
                    if d >= today:
                        next_release = d
                        break

            # Fallback to heuristic if FRED didn't give us a future date
            if next_release is None:
                next_release = self._estimate_next_release_date(release, today)

            if next_release:
                release.release_date = next_release
                if today <= next_release <= end_date:
                    upcoming.append(release)

        # Sort by date
        upcoming.sort(key=lambda r: r.release_date or date.max)
        return upcoming

    def _estimate_next_release_date(self, release: Release, today: date) -> Optional[date]:
        """
        Estimate the next release date based on typical schedules.
        All dates are adjusted to skip weekends.
        """
        if release.frequency == "weekly":
            # Jobless claims - next Thursday
            days_until_thursday = (3 - today.weekday()) % 7
            if days_until_thursday == 0:
                days_until_thursday = 7
            return today + timedelta(days=days_until_thursday)

        elif release.frequency == "monthly":
            if release.id == "employment_situation":
                return self._get_first_friday(today)
            elif release.id == "cpi":
                return self._get_monthly_release_day(today, typical_day=12)
            elif release.id == "ppi":
                return self._get_monthly_release_day(today, typical_day=14)
            elif release.id == "retail_sales":
                return self._get_monthly_release_day(today, typical_day=15)
            elif release.id == "pce":
                return self._get_monthly_release_day(today, typical_day=28)
            elif release.id == "consumer_confidence":
                return self._get_monthly_release_day(today, typical_day=25)
            elif release.id in ["housing_starts", "existing_home_sales"]:
                return self._get_monthly_release_day(today, typical_day=18)
            elif release.id == "jolts":
                return self._get_monthly_release_day(today, typical_day=7)
            elif release.id == "industrial_production":
                return self._get_monthly_release_day(today, typical_day=16)
            elif release.id == "fomc_decision":
                return self._get_monthly_release_day(today, typical_day=20)
            else:
                return self._get_monthly_release_day(today, typical_day=15)

        elif release.frequency == "quarterly":
            return self._get_quarterly_release_day(today)

        return None

    def _get_first_friday(self, today: date) -> date:
        """Get the first Friday of this month or next month."""
        first_day = today.replace(day=1)
        days_until_friday = (4 - first_day.weekday()) % 7
        first_friday = first_day + timedelta(days=days_until_friday)

        if first_friday >= today:
            return first_friday

        # Get first Friday of next month
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)

        days_until_friday = (4 - next_month.weekday()) % 7
        return next_month + timedelta(days=days_until_friday)

    def _get_monthly_release_day(self, today: date, typical_day: int) -> date:
        """Get the next occurrence of a typical monthly release day, skipping weekends."""
        # Try this month
        try:
            this_month_release = _skip_weekend(today.replace(day=typical_day))
            if this_month_release >= today:
                return this_month_release
        except ValueError:
            pass

        # Get next month
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)

        try:
            import calendar as cal_module
            last_day = cal_module.monthrange(next_month.year, next_month.month)[1]
            return _skip_weekend(next_month.replace(day=min(typical_day, last_day)))
        except ValueError:
            return _skip_weekend(next_month.replace(day=28))

    def _get_quarterly_release_day(self, today: date) -> date:
        """Get the next quarterly release date (GDP)."""
        quarterly_months = [1, 4, 7, 10]
        typical_day = 28

        for month in quarterly_months:
            if month >= today.month:
                try:
                    release = _skip_weekend(today.replace(month=month, day=typical_day))
                    if release >= today:
                        return release
                except ValueError:
                    pass

        return _skip_weekend(today.replace(year=today.year + 1, month=1, day=typical_day))

    def get_release_history(self, release_id: str, limit: int = 12) -> List[Dict[str, Any]]:
        """Get historical release data."""
        if release_id not in self.releases:
            return []

        release = self.releases[release_id]
        observations = self._get_series_observations(release.series_id, limit=limit)

        history = []
        for i, obs in enumerate(observations):
            try:
                value = float(obs["value"]) if obs["value"] != "." else None
                release_date = datetime.strptime(obs["date"], "%Y-%m-%d").date()

                change = None
                change_percent = None
                if i < len(observations) - 1 and value is not None:
                    prev = observations[i + 1]
                    prev_value = float(prev["value"]) if prev["value"] != "." else None
                    if prev_value is not None and prev_value != 0:
                        change = value - prev_value
                        change_percent = (change / abs(prev_value)) * 100

                history.append({
                    "date": release_date.isoformat(),
                    "value": value,
                    "change": change,
                    "change_percent": change_percent
                })
            except (ValueError, KeyError):
                continue

        return history

    def get_calendar_summary(self) -> Dict[str, Any]:
        """Get a summary of the economic calendar."""
        upcoming = self.get_upcoming_releases(days_ahead=21)

        # Group by importance
        high_importance = [r for r in upcoming if r.importance == ReleaseImportance.HIGH]

        # Group by week — use Monday-Sunday boundaries
        today = date.today()
        # Start of this week (Monday)
        week_start = today - timedelta(days=today.weekday())
        next_week_start = week_start + timedelta(days=7)
        week_after_start = week_start + timedelta(days=14)

        this_week = [r for r in upcoming if r.release_date and week_start <= r.release_date < next_week_start]
        next_week = [r for r in upcoming if r.release_date and next_week_start <= r.release_date < week_after_start]

        return {
            "total_upcoming": len(upcoming),
            "high_importance_count": len(high_importance),
            "this_week": [self._release_to_dict(r) for r in this_week],
            "next_week": [self._release_to_dict(r) for r in next_week],
            "all_upcoming": [self._release_to_dict(r) for r in upcoming]
        }

    def _release_to_dict(self, release: Release) -> Dict[str, Any]:
        """Convert Release to dictionary."""
        return {
            "id": release.id,
            "name": release.name,
            "series_id": release.series_id,
            "importance": release.importance.value,
            "typical_time": release.typical_time,
            "frequency": release.frequency,
            "description": release.description,
            "release_date": release.release_date.isoformat() if release.release_date else None,
            "previous_value": release.previous_value,
            "previous_date": release.previous_date.isoformat() if release.previous_date else None,
            "consensus_estimate": release.consensus_estimate,
            "actual_value": release.actual_value,
            "surprise": release.surprise,
            "surprise_percent": release.surprise_percent
        }
