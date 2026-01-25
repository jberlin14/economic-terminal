"""
Economic Data Risk Detection Rules

Detects significant economic data surprises.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from .config import ALERT_THRESHOLDS
from .models import RiskAlertData


def detect_economic_risks(
    releases: List[Dict[str, Any]]
) -> List[RiskAlertData]:
    """
    Detect economic data surprises.
    
    Args:
        releases: List of economic data releases with actual vs consensus
        
    Returns:
        List of RiskAlertData for significant surprises
    """
    risks = []
    
    for release in releases:
        indicator = release.get('indicator', 'Unknown')
        actual = release.get('actual')
        consensus = release.get('consensus')
        previous = release.get('previous')
        country = release.get('country', 'US')
        
        if actual is None or consensus is None:
            continue
        
        # Calculate surprise percentage
        if consensus != 0:
            surprise_pct = ((actual - consensus) / abs(consensus)) * 100
        else:
            surprise_pct = 0
        
        # Determine direction
        direction = 'beat' if actual > consensus else 'miss'
        
        # Check thresholds (focus on downside surprises)
        abs_surprise = abs(surprise_pct)
        
        if abs_surprise >= ALERT_THRESHOLDS['ECON_SURPRISE_CRITICAL']:
            severity = 'CRITICAL'
        elif abs_surprise >= ALERT_THRESHOLDS['ECON_SURPRISE_HIGH']:
            severity = 'HIGH'
        else:
            continue
        
        # Create alert
        risk = RiskAlertData(
            alert_type='ECON',
            severity=severity,
            title=f"{indicator} {direction.title()}",
            message=f"{indicator}: Actual {actual} vs Consensus {consensus} ({surprise_pct:+.1f}%)",
            related_entity=indicator,
            related_value=actual,
            threshold_value=ALERT_THRESHOLDS[f'ECON_SURPRISE_{severity}'],
            country=country,
            details={
                'actual': actual,
                'consensus': consensus,
                'previous': previous,
                'surprise_pct': surprise_pct,
                'direction': direction,
                'is_downside': actual < consensus
            }
        )
        risks.append(risk)
        logger.info(f"{severity}: {indicator} {direction} by {abs_surprise:.1f}%")
    
    return risks


def categorize_indicator(indicator_name: str) -> str:
    """
    Categorize economic indicator by type.
    
    Returns: 'LABOR', 'INFLATION', 'ACTIVITY', 'SENTIMENT', 'OTHER'
    """
    name_lower = indicator_name.lower()
    
    labor_keywords = ['payroll', 'employment', 'jobless', 'claims', 'unemployment', 'labor']
    inflation_keywords = ['cpi', 'ppi', 'inflation', 'price']
    activity_keywords = ['gdp', 'retail', 'housing', 'ism', 'pmi', 'industrial', 'production']
    sentiment_keywords = ['confidence', 'sentiment', 'consumer', 'michigan']
    
    if any(kw in name_lower for kw in labor_keywords):
        return 'LABOR'
    elif any(kw in name_lower for kw in inflation_keywords):
        return 'INFLATION'
    elif any(kw in name_lower for kw in activity_keywords):
        return 'ACTIVITY'
    elif any(kw in name_lower for kw in sentiment_keywords):
        return 'SENTIMENT'
    
    return 'OTHER'


def assess_economic_momentum(
    recent_releases: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Assess economic momentum from recent data surprises.
    
    Returns momentum assessment by category.
    """
    assessment = {
        'timestamp': datetime.utcnow().isoformat(),
        'overall_momentum': 'NEUTRAL',
        'categories': {
            'LABOR': {'direction': 'NEUTRAL', 'surprise_avg': 0},
            'INFLATION': {'direction': 'NEUTRAL', 'surprise_avg': 0},
            'ACTIVITY': {'direction': 'NEUTRAL', 'surprise_avg': 0},
            'SENTIMENT': {'direction': 'NEUTRAL', 'surprise_avg': 0}
        }
    }
    
    # Collect surprises by category
    category_surprises = {cat: [] for cat in assessment['categories']}
    
    for release in recent_releases:
        indicator = release.get('indicator', '')
        surprise = release.get('surprise_pct')
        
        if surprise is None:
            continue
        
        category = categorize_indicator(indicator)
        if category in category_surprises:
            category_surprises[category].append(surprise)
    
    # Calculate averages and directions
    positive_count = 0
    negative_count = 0
    
    for category, surprises in category_surprises.items():
        if surprises:
            avg = sum(surprises) / len(surprises)
            assessment['categories'][category]['surprise_avg'] = round(avg, 1)
            
            if avg > 5:
                assessment['categories'][category]['direction'] = 'POSITIVE'
                positive_count += 1
            elif avg < -5:
                assessment['categories'][category]['direction'] = 'NEGATIVE'
                negative_count += 1
    
    # Overall momentum
    if positive_count >= 3:
        assessment['overall_momentum'] = 'POSITIVE'
    elif negative_count >= 3:
        assessment['overall_momentum'] = 'NEGATIVE'
    elif positive_count > negative_count:
        assessment['overall_momentum'] = 'SLIGHTLY_POSITIVE'
    elif negative_count > positive_count:
        assessment['overall_momentum'] = 'SLIGHTLY_NEGATIVE'
    
    return assessment
