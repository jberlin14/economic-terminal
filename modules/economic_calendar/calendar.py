"""
Economic Calendar - Release Tracking and Fetching

Tracks major economic releases with their schedules, estimates, and historical surprises.
"""

import os
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
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

    # Release-specific data (populated when fetched)
    release_date: Optional[date] = None
    previous_value: Optional[float] = None
    previous_date: Optional[date] = None
    consensus_estimate: Optional[float] = None
    actual_value: Optional[float] = None
    surprise: Optional[float] = None  # actual - consensus
    surprise_percent: Optional[float] = None


# Key economic releases to track
TRACKED_RELEASES = {
    # Employment
    "employment_situation": Release(
        id="employment_situation",
        name="Employment Situation (NFP)",
        series_id="PAYEMS",
        importance=ReleaseImportance.HIGH,
        typical_time="08:30 ET",
        frequency="monthly",
        description="Nonfarm payrolls, unemployment rate - First Friday of month"
    ),
    "jobless_claims": Release(
        id="jobless_claims",
        name="Initial Jobless Claims",
        series_id="ICSA",
        importance=ReleaseImportance.HIGH,
        typical_time="08:30 ET",
        frequency="weekly",
        description="Weekly unemployment claims - Every Thursday"
    ),
    "jolts": Release(
        id="jolts",
        name="JOLTS Job Openings",
        series_id="JTSJOL",
        importance=ReleaseImportance.MEDIUM,
        typical_time="10:00 ET",
        frequency="monthly",
        description="Job openings and labor turnover"
    ),

    # Inflation
    "cpi": Release(
        id="cpi",
        name="Consumer Price Index (CPI)",
        series_id="CPIAUCSL",
        importance=ReleaseImportance.HIGH,
        typical_time="08:30 ET",
        frequency="monthly",
        description="Consumer inflation - Mid-month release"
    ),
    "pce": Release(
        id="pce",
        name="PCE Price Index",
        series_id="PCEPI",
        importance=ReleaseImportance.HIGH,
        typical_time="08:30 ET",
        frequency="monthly",
        description="Fed's preferred inflation measure"
    ),
    "ppi": Release(
        id="ppi",
        name="Producer Price Index (PPI)",
        series_id="PPIACO",
        importance=ReleaseImportance.MEDIUM,
        typical_time="08:30 ET",
        frequency="monthly",
        description="Wholesale/producer inflation"
    ),

    # GDP & Output
    "gdp": Release(
        id="gdp",
        name="GDP (Advance/Preliminary/Final)",
        series_id="GDP",
        importance=ReleaseImportance.HIGH,
        typical_time="08:30 ET",
        frequency="quarterly",
        description="Gross Domestic Product"
    ),
    "industrial_production": Release(
        id="industrial_production",
        name="Industrial Production",
        series_id="INDPRO",
        importance=ReleaseImportance.MEDIUM,
        typical_time="09:15 ET",
        frequency="monthly",
        description="Manufacturing and industrial output"
    ),

    # Consumer
    "retail_sales": Release(
        id="retail_sales",
        name="Retail Sales",
        series_id="RSXFS",
        importance=ReleaseImportance.HIGH,
        typical_time="08:30 ET",
        frequency="monthly",
        description="Consumer spending indicator"
    ),
    "consumer_confidence": Release(
        id="consumer_confidence",
        name="Consumer Confidence",
        series_id="UMCSENT",
        importance=ReleaseImportance.MEDIUM,
        typical_time="10:00 ET",
        frequency="monthly",
        description="University of Michigan Consumer Sentiment"
    ),

    # Housing
    "housing_starts": Release(
        id="housing_starts",
        name="Housing Starts",
        series_id="HOUST",
        importance=ReleaseImportance.MEDIUM,
        typical_time="08:30 ET",
        frequency="monthly",
        description="New residential construction"
    ),
    "existing_home_sales": Release(
        id="existing_home_sales",
        name="Existing Home Sales",
        series_id="EXHOSLUSM495S",
        importance=ReleaseImportance.MEDIUM,
        typical_time="10:00 ET",
        frequency="monthly",
        description="Sales of existing homes"
    ),

    # Fed & Rates
    "fomc_decision": Release(
        id="fomc_decision",
        name="FOMC Rate Decision",
        series_id="FEDFUNDS",
        importance=ReleaseImportance.HIGH,
        typical_time="14:00 ET",
        frequency="monthly",
        description="Federal Reserve interest rate decision"
    ),
}


class EconomicCalendar:
    """
    Fetches and manages economic calendar data.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or FRED_API_KEY
        self.releases = TRACKED_RELEASES.copy()

    def is_available(self) -> bool:
        """Check if FRED API is available."""
        return bool(self.api_key)

    def _get_fred_release_dates(self, release_id: int, limit: int = 10) -> List[Dict]:
        """Fetch release dates from FRED releases endpoint."""
        if not self.is_available():
            return []

        try:
            url = f"{FRED_BASE_URL}/release/dates"
            params = {
                "release_id": release_id,
                "api_key": self.api_key,
                "file_type": "json",
                "limit": limit,
                "sort_order": "desc",
                "include_release_dates_with_no_data": "true"
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            return data.get("release_dates", [])
        except Exception as e:
            logger.error(f"Failed to fetch FRED release dates: {e}")
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

        Uses a combination of known schedules and FRED release data.
        """
        upcoming = []
        today = date.today()
        end_date = today + timedelta(days=days_ahead)

        for release_id, release in self.releases.items():
            # Get latest observations for previous value
            observations = self._get_series_observations(release.series_id, limit=2)

            if observations:
                # Most recent observation
                latest = observations[0]
                try:
                    release.previous_value = float(latest["value"]) if latest["value"] != "." else None
                    release.previous_date = datetime.strptime(latest["date"], "%Y-%m-%d").date()
                except (ValueError, KeyError):
                    pass

            # Estimate next release date based on typical release schedules
            next_release = self._estimate_next_release_date(release, today)

            if next_release:
                release.release_date = next_release

                # Include if within our window
                if today <= next_release <= end_date:
                    upcoming.append(release)

        # Sort by date
        upcoming.sort(key=lambda r: r.release_date or date.max)

        return upcoming

    def _estimate_next_release_date(self, release: Release, today: date) -> Optional[date]:
        """
        Estimate the next release date based on typical schedules.

        Release schedules:
        - Employment Situation: First Friday of month
        - CPI: Usually 12th-15th of month (for prior month data)
        - PPI: Usually 13th-16th of month
        - Jobless Claims: Every Thursday
        - GDP: End of month (advance), then revisions
        - Retail Sales: Mid-month
        - PCE: End of month
        """
        import calendar as cal_module

        if release.frequency == "weekly":
            # Jobless claims - next Thursday
            days_until_thursday = (3 - today.weekday()) % 7
            if days_until_thursday == 0:
                days_until_thursday = 7  # If today is Thursday, get next Thursday
            return today + timedelta(days=days_until_thursday)

        elif release.frequency == "monthly":
            # Determine typical release day based on report type
            if release.id == "employment_situation":
                # First Friday of the month
                return self._get_first_friday(today)
            elif release.id == "cpi":
                # Usually around the 12th
                return self._get_monthly_release_day(today, typical_day=12)
            elif release.id == "ppi":
                # Usually around the 14th
                return self._get_monthly_release_day(today, typical_day=14)
            elif release.id == "retail_sales":
                # Usually around the 15th
                return self._get_monthly_release_day(today, typical_day=15)
            elif release.id == "pce":
                # Usually end of month (around 28th)
                return self._get_monthly_release_day(today, typical_day=28)
            elif release.id == "consumer_confidence":
                # Usually end of month
                return self._get_monthly_release_day(today, typical_day=25)
            elif release.id in ["housing_starts", "existing_home_sales"]:
                # Usually mid-month
                return self._get_monthly_release_day(today, typical_day=18)
            elif release.id == "jolts":
                # Usually around the 7th
                return self._get_monthly_release_day(today, typical_day=7)
            elif release.id == "industrial_production":
                # Usually around the 16th
                return self._get_monthly_release_day(today, typical_day=16)
            elif release.id == "fomc_decision":
                # FOMC meetings - roughly every 6 weeks, use approximation
                return self._get_monthly_release_day(today, typical_day=20)
            else:
                # Default to mid-month
                return self._get_monthly_release_day(today, typical_day=15)

        elif release.frequency == "quarterly":
            # GDP - end of month, quarterly
            return self._get_quarterly_release_day(today)

        return None

    def _get_first_friday(self, today: date) -> date:
        """Get the first Friday of this month or next month."""
        # Check this month first
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
        """Get the next occurrence of a typical monthly release day."""
        # Try this month
        try:
            this_month_release = today.replace(day=typical_day)
            if this_month_release >= today:
                return this_month_release
        except ValueError:
            pass  # Day doesn't exist in this month

        # Get next month
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)

        try:
            return next_month.replace(day=typical_day)
        except ValueError:
            # If day doesn't exist, use last day of month
            import calendar as cal_module
            last_day = cal_module.monthrange(next_month.year, next_month.month)[1]
            return next_month.replace(day=min(typical_day, last_day))

    def _get_quarterly_release_day(self, today: date) -> date:
        """Get the next quarterly release date (GDP)."""
        # GDP advance estimates: end of Jan (Q4), Apr (Q1), Jul (Q2), Oct (Q3)
        quarterly_months = [1, 4, 7, 10]
        typical_day = 28

        for month in quarterly_months:
            if month >= today.month:
                try:
                    release = today.replace(month=month, day=typical_day)
                    if release >= today:
                        return release
                except ValueError:
                    pass

        # Next year Q4 release
        return today.replace(year=today.year + 1, month=1, day=typical_day)

    def get_release_history(self, release_id: str, limit: int = 12) -> List[Dict[str, Any]]:
        """
        Get historical release data with surprises.

        Returns list of past releases with actual vs expected (where available).
        """
        if release_id not in self.releases:
            return []

        release = self.releases[release_id]
        observations = self._get_series_observations(release.series_id, limit=limit)

        history = []
        for i, obs in enumerate(observations):
            try:
                value = float(obs["value"]) if obs["value"] != "." else None
                release_date = datetime.strptime(obs["date"], "%Y-%m-%d").date()

                # Calculate change from previous
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
        """
        Get a summary of the economic calendar.
        """
        upcoming = self.get_upcoming_releases(days_ahead=14)

        # Group by importance
        high_importance = [r for r in upcoming if r.importance == ReleaseImportance.HIGH]
        medium_importance = [r for r in upcoming if r.importance == ReleaseImportance.MEDIUM]

        # Group by week
        today = date.today()
        this_week = [r for r in upcoming if r.release_date and r.release_date < today + timedelta(days=7)]
        next_week = [r for r in upcoming if r.release_date and today + timedelta(days=7) <= r.release_date < today + timedelta(days=14)]

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
