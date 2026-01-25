#!/usr/bin/env python3
"""
Test News Analysis System

Tests leader detection, event categorization, and article analysis.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.news_aggregator.leader_detector import LeaderDetector
from modules.news_aggregator.config import LEADERS, RSS_FEEDS


def print_separator(title):
    """Print a formatted separator."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_leader_detection():
    """Test leader detection with sample headlines."""
    print_separator("LEADER DETECTION TEST")

    detector = LeaderDetector()

    test_headlines = [
        "Fed Chair Powell signals potential rate cut in March",
        "ECB's Lagarde warns of persistent inflation risks",
        "Trump announces new tariffs on Chinese imports",
        "Bank of Japan's Ueda hints at policy normalization",
        "Trudeau faces pressure as Carney enters race",
        "Milei orders emergency spending cuts in Argentina",
        "Putin threatens response to NATO expansion",
        "Xi Jinping meets with European leaders on trade",
    ]

    for headline in test_headlines:
        print(f"\nHeadline: {headline}")

        leaders = detector.detect_leaders(headline)
        print(f"  Leaders found: {leaders}")

        if leaders:
            for leader_key in leaders:
                info = detector.get_leader_info(leader_key)
                if info:
                    print(f"    - {info['names'][0]}: {info['role']} at {info['institution']} ({', '.join(info['countries'])})")


def test_action_detection():
    """Test action word detection."""
    print_separator("ACTION DETECTION TEST")

    detector = LeaderDetector()

    test_headlines = [
        "Fed announces emergency rate cut",
        "ECB considering dovish policy shift",
        "Trump threatens tariffs on European goods",
        "Bank of Japan may raise rates next month",
        "Putin orders military deployment to border",
        "Lagarde warns of recession risks",
    ]

    for headline in test_headlines:
        print(f"\nHeadline: {headline}")

        actions = detector.detect_actions(headline)
        if actions['critical']:
            print(f"  CRITICAL actions: {', '.join(actions['critical'])}")
        if actions['high']:
            print(f"  HIGH actions: {', '.join(actions['high'])}")
        if not actions['critical'] and not actions['high']:
            print("  No significant actions detected")


def test_event_detection():
    """Test event type detection."""
    print_separator("EVENT TYPE DETECTION TEST")

    detector = LeaderDetector()

    test_headlines = [
        "Fed cuts rates by 50 basis points in emergency move",
        "Trump announces 25% tariffs on Mexican imports",
        "Russia deploys troops to Ukraine border",
        "US GDP grows 3.2% in Q4, beating estimates",
        "Stock market crashes amid recession fears",
        "Bank of England downgrades UK credit rating",
        "Hurricane causes emergency in Florida",
        "China announces currency intervention",
    ]

    for headline in test_headlines:
        print(f"\nHeadline: {headline}")

        events = detector.detect_events(headline)
        if events:
            print(f"  Event types: {', '.join(events)}")
        else:
            print("  No specific events detected")


def test_full_analysis():
    """Test complete article analysis."""
    print_separator("FULL ARTICLE ANALYSIS TEST")

    detector = LeaderDetector()

    test_articles = [
        {
            'headline': "Powell announces emergency rate cut to combat recession fears",
            'summary': "Federal Reserve Chair Jerome Powell announced a 50 basis point rate cut in an emergency meeting today."
        },
        {
            'headline': "Trump threatens tariffs as trade war with China escalates",
            'summary': "President Trump warned of new tariffs on Chinese goods if trade negotiations fail."
        },
        {
            'headline': "Lagarde signals ECB may hold rates steady amid uncertainty",
            'summary': "ECB President Christine Lagarde suggested the central bank is considering keeping rates unchanged."
        },
        {
            'headline': "Russia invades Ukraine; NATO considers Article 5 response",
            'summary': "Russian military forces crossed into Ukrainian territory as NATO leaders meet in emergency session."
        },
        {
            'headline': "Milei orders drastic spending cuts in Argentina",
            'summary': "Argentine President Javier Milei signed executive orders slashing government spending by 40%."
        }
    ]

    for article in test_articles:
        print(f"\nHeadline: {article['headline']}")
        print(f"Summary: {article['summary'][:80]}...")

        analysis = detector.analyze_article(article['headline'], article['summary'])

        print(f"\n  Severity: {analysis['severity']}")

        if analysis['leaders']:
            print(f"  Leaders: {', '.join([l['names'][0] for l in analysis['leaders']])}")

        if analysis['institutions']:
            print(f"  Institutions: {', '.join(analysis['institutions'])}")

        if analysis['events']:
            print(f"  Events: {', '.join(analysis['events'])}")

        if analysis['countries']:
            print(f"  Countries: {', '.join(analysis['countries'])}")

        if analysis['actions']['critical']:
            print(f"  Critical actions: {', '.join(analysis['actions']['critical'])}")

        if analysis['actions']['high']:
            print(f"  High actions: {', '.join(analysis['actions']['high'])}")

        if analysis['tags']:
            print(f"  Tags: {', '.join(analysis['tags'][:5])}...")


def test_leader_database():
    """Test leader database queries."""
    print_separator("LEADER DATABASE TEST")

    detector = LeaderDetector()

    print("\nLeaders by institution:")

    institutions = ['FED', 'ECB', 'WHITE_HOUSE', 'BOJ', 'KREMLIN']
    for inst in institutions:
        leaders = detector.get_all_leaders_by_institution(inst)
        print(f"\n  {inst}:")
        for leader in leaders:
            print(f"    - {leader['names'][0]} ({leader['role']})")

    print("\n\nLeaders by country:")

    countries = ['US', 'EU', 'JP', 'CA', 'MX', 'RU']
    for country in countries:
        leaders = detector.get_all_leaders_by_country(country)
        print(f"\n  {country}:")
        for leader in leaders[:3]:  # Limit to 3 per country
            print(f"    - {leader['names'][0]} ({leader['role']})")


def test_rss_feeds():
    """Test RSS feed configuration."""
    print_separator("RSS FEED CONFIGURATION TEST")

    print(f"\nTotal RSS feeds configured: {len(RSS_FEEDS)}")

    categories = {}
    for feed_key, feed_data in RSS_FEEDS.items():
        category = feed_data['category']
        if category not in categories:
            categories[category] = []
        categories[category].append(feed_data['name'])

    print("\nFeeds by category:")
    for category, feeds in sorted(categories.items()):
        print(f"\n  {category}:")
        for feed in feeds:
            print(f"    - {feed}")


def test_leader_stats():
    """Test leader database statistics."""
    print_separator("LEADER DATABASE STATISTICS")

    total_leaders = len(LEADERS)
    print(f"\nTotal leaders tracked: {total_leaders}")

    # Count by role type
    roles = {}
    institutions_set = set()
    countries_set = set()

    for leader_data in LEADERS.values():
        role = leader_data['role']
        roles[role] = roles.get(role, 0) + 1
        institutions_set.add(leader_data['institution'])
        countries_set.update(leader_data['countries'])

    print(f"Total institutions: {len(institutions_set)}")
    print(f"Total countries covered: {len(countries_set)}")

    print("\nMost common roles:")
    for role, count in sorted(roles.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {role}: {count}")


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("  NEWS ANALYSIS SYSTEM TEST SUITE")
    print("=" * 70)

    try:
        # Run tests
        test_leader_detection()
        test_action_detection()
        test_event_detection()
        test_full_analysis()
        test_leader_database()
        test_rss_feeds()
        test_leader_stats()

        print("\n" + "=" * 70)
        print("  ALL TESTS COMPLETED SUCCESSFULLY")
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()