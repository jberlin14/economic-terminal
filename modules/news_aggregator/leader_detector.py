"""
Leader Detection and Event Analysis

Detects mentions of world leaders, central bankers, and key figures in news articles.
Analyzes action words and event types to determine severity.
"""

import re
from typing import List, Dict, Any, Optional
from loguru import logger

from .config import (
    LEADERS,
    CRITICAL_ACTIONS,
    HIGH_ACTIONS,
    EVENT_TYPES,
    GEOPOLITICAL_CRITICAL,
    COUNTRY_KEYWORDS
)


class LeaderDetector:
    """
    Detects leaders, actions, and events in news articles.
    """

    def __init__(self):
        self.leaders = LEADERS
        self.critical_actions = CRITICAL_ACTIONS
        self.high_actions = HIGH_ACTIONS
        self.event_types = EVENT_TYPES
        self.geopolitical_critical = GEOPOLITICAL_CRITICAL
        self.country_keywords = COUNTRY_KEYWORDS

    def detect_leaders(self, text: str) -> List[str]:
        """
        Detect leader mentions in text.

        Args:
            text: Article headline and/or summary

        Returns:
            List of leader keys (e.g., ['powell', 'lagarde'])
        """
        if not text:
            return []

        text_lower = text.lower()
        found_leaders = []

        for leader_key, leader_data in self.leaders.items():
            for name in leader_data['names']:
                # Case-insensitive search for leader names
                if re.search(r'\b' + re.escape(name.lower()) + r'\b', text_lower):
                    found_leaders.append(leader_key)
                    break  # Found this leader, move to next

        return list(set(found_leaders))  # Remove duplicates

    def detect_actions(self, text: str) -> Dict[str, List[str]]:
        """
        Detect action words in text.

        Args:
            text: Article headline and/or summary

        Returns:
            Dict with 'critical' and 'high' action lists
        """
        if not text:
            return {'critical': [], 'high': []}

        text_lower = text.lower()
        critical_found = []
        high_found = []

        # Check for critical actions
        for action in self.critical_actions:
            if re.search(r'\b' + re.escape(action.lower()) + r'\b', text_lower):
                critical_found.append(action)

        # Check for high actions
        for action in self.high_actions:
            if re.search(r'\b' + re.escape(action.lower()) + r'\b', text_lower):
                high_found.append(action)

        return {
            'critical': list(set(critical_found)),
            'high': list(set(high_found))
        }

    def detect_events(self, text: str) -> List[str]:
        """
        Detect event types in text.

        Args:
            text: Article headline and/or summary

        Returns:
            List of event type keys (e.g., ['RATE_DECISION', 'TRADE_POLICY'])
        """
        if not text:
            return []

        text_lower = text.lower()
        found_events = []

        for event_type, keywords in self.event_types.items():
            for keyword in keywords:
                if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', text_lower):
                    found_events.append(event_type)
                    break  # Found this event type, move to next

        return list(set(found_events))

    def detect_countries_from_leaders(self, leader_keys: List[str]) -> List[str]:
        """
        Extract countries from detected leaders.

        Args:
            leader_keys: List of leader keys

        Returns:
            List of country codes
        """
        countries = []
        for leader_key in leader_keys:
            if leader_key in self.leaders:
                countries.extend(self.leaders[leader_key]['countries'])

        return list(set(countries))

    def detect_countries_from_keywords(self, text: str) -> List[str]:
        """
        Detect countries from keyword matching.

        Args:
            text: Article text

        Returns:
            List of country codes
        """
        if not text:
            return []

        text_lower = text.lower()
        found_countries = []

        for country, keywords in self.country_keywords.items():
            for keyword in keywords:
                if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', text_lower):
                    found_countries.append(country)
                    break

        return list(set(found_countries))

    def get_institutions(self, leader_keys: List[str]) -> List[str]:
        """
        Extract institutions from detected leaders.

        Args:
            leader_keys: List of leader keys

        Returns:
            List of institution names
        """
        institutions = []
        for leader_key in leader_keys:
            if leader_key in self.leaders:
                institutions.append(self.leaders[leader_key]['institution'])

        return list(set(institutions))

    def calculate_severity(
        self,
        leaders: List[str],
        actions: Dict[str, List[str]],
        events: List[str],
        text: str
    ) -> str:
        """
        Calculate article severity based on detected elements.

        Args:
            leaders: Detected leader keys
            actions: Detected actions dict
            events: Detected event types
            text: Full article text

        Returns:
            Severity level: CRITICAL, HIGH, MEDIUM, or LOW
        """
        text_lower = text.lower() if text else ''

        # CRITICAL: Leader + critical action, or geopolitical critical keywords
        if leaders and actions['critical']:
            return 'CRITICAL'

        # Check for geopolitical critical keywords
        for keyword in self.geopolitical_critical:
            if keyword.lower() in text_lower:
                return 'CRITICAL'

        # HIGH: Leader + high action, or major events without leader
        if leaders and actions['high']:
            return 'HIGH'

        # HIGH: Military, sanctions, or trade war events
        high_events = ['MILITARY', 'SANCTIONS', 'TRADE_POLICY']
        if any(event in high_events for event in events):
            return 'HIGH'

        # MEDIUM: Leader mentioned or rate decision
        if leaders or 'RATE_DECISION' in events:
            return 'MEDIUM'

        # MEDIUM: Economic data or market move
        medium_events = ['ECONOMIC_DATA', 'MARKET_MOVE', 'DEBT_CREDIT']
        if any(event in medium_events for event in events):
            return 'MEDIUM'

        return 'LOW'

    def analyze_article(
        self,
        headline: str,
        summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform full analysis of an article.

        Args:
            headline: Article headline
            summary: Article summary (optional)

        Returns:
            Dict with comprehensive analysis:
            {
                'leaders': [{'key': 'powell', 'name': 'Powell', 'countries': ['US'], ...}],
                'actions': {'critical': [...], 'high': [...]},
                'events': ['RATE_DECISION'],
                'countries': ['US'],
                'institutions': ['FED'],
                'severity': 'CRITICAL',
                'tags': ['FED', 'RATE_DECISION', 'POWELL']
            }
        """
        # Combine headline and summary for analysis
        text = headline
        if summary:
            text = f"{headline} {summary}"

        # Detect leaders
        leader_keys = self.detect_leaders(text)
        leaders_details = []
        for key in leader_keys:
            if key in self.leaders:
                leader_data = self.leaders[key].copy()
                leader_data['key'] = key
                leaders_details.append(leader_data)

        # Detect actions
        actions = self.detect_actions(text)

        # Detect events
        events = self.detect_events(text)

        # Detect countries
        countries_from_leaders = self.detect_countries_from_leaders(leader_keys)
        countries_from_keywords = self.detect_countries_from_keywords(text)
        all_countries = list(set(countries_from_leaders + countries_from_keywords))

        # Get institutions
        institutions = self.get_institutions(leader_keys)

        # Calculate severity
        severity = self.calculate_severity(leader_keys, actions, events, text)

        # Generate tags
        tags = []
        tags.extend(institutions)
        tags.extend(events)
        tags.extend([key.upper() for key in leader_keys])
        tags = list(set(tags))  # Remove duplicates

        return {
            'leaders': leaders_details,
            'leader_keys': leader_keys,
            'actions': actions,
            'events': events,
            'countries': all_countries,
            'institutions': institutions,
            'severity': severity,
            'tags': tags
        }

    def get_leader_info(self, leader_key: str) -> Optional[Dict[str, Any]]:
        """
        Get full information about a leader.

        Args:
            leader_key: Leader key (e.g., 'powell')

        Returns:
            Leader data dict or None
        """
        if leader_key in self.leaders:
            leader_data = self.leaders[leader_key].copy()
            leader_data['key'] = leader_key
            return leader_data
        return None

    def get_all_leaders_by_institution(self, institution: str) -> List[Dict[str, Any]]:
        """
        Get all leaders from a specific institution.

        Args:
            institution: Institution name (e.g., 'FED', 'ECB')

        Returns:
            List of leader data dicts
        """
        leaders = []
        for key, data in self.leaders.items():
            if data['institution'] == institution:
                leader_data = data.copy()
                leader_data['key'] = key
                leaders.append(leader_data)
        return leaders

    def get_all_leaders_by_country(self, country: str) -> List[Dict[str, Any]]:
        """
        Get all leaders from a specific country.

        Args:
            country: Country code (e.g., 'US', 'EU')

        Returns:
            List of leader data dicts
        """
        leaders = []
        for key, data in self.leaders.items():
            if country in data['countries']:
                leader_data = data.copy()
                leader_data['key'] = key
                leaders.append(leader_data)
        return leaders