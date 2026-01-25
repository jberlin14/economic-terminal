"""
Geopolitical Risk Detection Rules

Detects geopolitical events with market impact from news feeds.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from .config import (
    CRITICAL_KEYWORDS, HIGH_KEYWORDS, HIGH_CREDIBILITY_SOURCES,
    is_critical_keyword, is_high_keyword, get_source_credibility,
    is_trump_related, COUNTRY_PRIORITY
)
from .models import RiskAlertData


def detect_geopolitical_risks(
    news_articles: List[Dict[str, Any]]
) -> List[RiskAlertData]:
    """
    Scan news articles for geopolitical risks.
    
    Args:
        news_articles: List of news article dictionaries with headline, source, etc.
        
    Returns:
        List of RiskAlertData for detected risks
    """
    risks = []
    
    for article in news_articles:
        headline = article.get('headline', '')
        source = article.get('source', '')
        url = article.get('url', '')
        published_at = article.get('published_at')
        country_tags = article.get('country_tags', [])
        
        # Skip if already processed
        if article.get('processed'):
            continue
        
        # Check for critical keywords
        if is_critical_keyword(headline):
            credibility = get_source_credibility(source)
            
            # Only flag as CRITICAL if from high-credibility source
            if credibility == 'HIGH':
                severity = 'CRITICAL'
            else:
                severity = 'HIGH'
            
            # Determine primary country
            country = _get_primary_country(country_tags)
            
            risk = RiskAlertData(
                alert_type='POLITICAL',
                severity=severity,
                title="Geopolitical Alert",
                message=headline[:200],
                related_entity=source,
                source=source,
                url=url,
                country=country,
                details={
                    'headline': headline,
                    'source': source,
                    'source_credibility': credibility,
                    'country_tags': country_tags,
                    'published_at': published_at.isoformat() if isinstance(published_at, datetime) else published_at,
                    'matched_keywords': _find_matching_keywords(headline, CRITICAL_KEYWORDS)
                }
            )
            risks.append(risk)
            logger.warning(f"{severity}: {headline[:100]}")
            
        # Check for high-priority keywords
        elif is_high_keyword(headline):
            credibility = get_source_credibility(source)
            
            if credibility in ['HIGH', 'MEDIUM']:
                country = _get_primary_country(country_tags)
                
                risk = RiskAlertData(
                    alert_type='POLITICAL',
                    severity='HIGH',
                    title="Market-Moving News",
                    message=headline[:200],
                    related_entity=source,
                    source=source,
                    url=url,
                    country=country,
                    details={
                        'headline': headline,
                        'source': source,
                        'source_credibility': credibility,
                        'country_tags': country_tags,
                        'matched_keywords': _find_matching_keywords(headline, HIGH_KEYWORDS)
                    }
                )
                risks.append(risk)
                logger.info(f"HIGH: {headline[:100]}")
    
    # Sort by country priority
    risks.sort(key=lambda r: COUNTRY_PRIORITY.get(r.country, 99))
    
    return risks


def detect_trump_alerts(
    posts: List[Dict[str, Any]]
) -> List[RiskAlertData]:
    """
    Detect market-relevant Trump social media posts.
    
    Args:
        posts: List of social media posts
        
    Returns:
        List of RiskAlertData for relevant posts
    """
    risks = []
    
    for post in posts:
        text = post.get('text', '')
        timestamp = post.get('timestamp')
        
        if is_trump_related(text):
            # Determine severity based on content
            if is_critical_keyword(text):
                severity = 'CRITICAL'
            else:
                severity = 'HIGH'
            
            risk = RiskAlertData(
                alert_type='POLITICAL',
                severity=severity,
                title="Trump Policy Statement",
                message=text[:200],
                related_entity='@realDonaldTrump',
                source='Twitter/X',
                country='US',
                details={
                    'full_text': text,
                    'timestamp': timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
                    'matched_keywords': _find_matching_keywords(text, CRITICAL_KEYWORDS + HIGH_KEYWORDS)
                }
            )
            risks.append(risk)
            logger.warning(f"Trump alert ({severity}): {text[:100]}")
    
    return risks


def _get_primary_country(country_tags: List[str]) -> str:
    """Get highest priority country from tags."""
    if not country_tags:
        return 'US'
    
    # Sort by priority
    sorted_tags = sorted(
        country_tags,
        key=lambda c: COUNTRY_PRIORITY.get(c, 99)
    )
    
    return sorted_tags[0] if sorted_tags else 'US'


def _find_matching_keywords(text: str, keywords: List[str]) -> List[str]:
    """Find which keywords matched in text."""
    text_lower = text.lower()
    matched = []
    
    for kw in keywords:
        if kw.lower() in text_lower:
            matched.append(kw)
    
    return matched


def assess_geopolitical_climate(
    recent_articles: List[Dict[str, Any]],
    hours: int = 24
) -> Dict[str, Any]:
    """
    Assess overall geopolitical climate from recent news.
    
    Returns summary of geopolitical risk levels by region.
    """
    assessment = {
        'timestamp': datetime.utcnow().isoformat(),
        'overall_risk': 'NORMAL',
        'regions': {},
        'top_stories': []
    }
    
    # Count articles by region and severity
    region_counts = {}
    
    for article in recent_articles:
        severity = article.get('severity', 'LOW')
        countries = article.get('country_tags', [])
        
        for country in countries:
            if country not in region_counts:
                region_counts[country] = {'critical': 0, 'high': 0, 'total': 0}
            
            region_counts[country]['total'] += 1
            if severity == 'CRITICAL':
                region_counts[country]['critical'] += 1
            elif severity == 'HIGH':
                region_counts[country]['high'] += 1
    
    # Assess each region
    for region, counts in region_counts.items():
        if counts['critical'] > 0:
            assessment['regions'][region] = 'CRITICAL'
            assessment['overall_risk'] = 'HIGH'
        elif counts['high'] >= 3:
            assessment['regions'][region] = 'ELEVATED'
            if assessment['overall_risk'] == 'NORMAL':
                assessment['overall_risk'] = 'ELEVATED'
        else:
            assessment['regions'][region] = 'NORMAL'
    
    return assessment
