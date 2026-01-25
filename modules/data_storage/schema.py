"""
Database Schema Definitions

Defines all tables for the Economic Terminal using SQLAlchemy ORM.
Includes proper indexing for query performance.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, JSON, Boolean, 
    Index, Text, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class FXRate(Base):
    """
    Foreign Exchange Rate Storage
    
    Stores currency pair rates with change calculations.
    All rates stored in USD/XXX convention (how many units of foreign currency per 1 USD).
    """
    __tablename__ = 'fx_rates'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    pair = Column(String(10), nullable=False, index=True)
    rate = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True, default=datetime.utcnow)
    
    # Change percentages
    change_1h = Column(Float)   # 1-hour change %
    change_24h = Column(Float)  # 24-hour change %
    change_1w = Column(Float)   # 1-week change %
    change_ytd = Column(Float)  # Year-to-date change %
    
    # Mini chart data (JSON array of last 24 hours, 15-min intervals)
    sparkline_data = Column(JSON)
    
    # Metadata
    source = Column(String(50), default='alpha_vantage')  # Data source
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_fx_pair_timestamp', 'pair', 'timestamp'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            'pair': self.pair,
            'rate': self.rate,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'change_1h': self.change_1h,
            'change_24h': self.change_24h,
            'change_1w': self.change_1w,
            'change_ytd': self.change_ytd,
            'sparkline': self.sparkline_data or []
        }


class YieldCurve(Base):
    """
    Treasury Yield Curve Storage
    
    Stores complete yield curves with all standard tenors.
    Includes calculated spreads for quick risk detection.
    """
    __tablename__ = 'yield_curves'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    country = Column(String(50), nullable=False, default='US', index=True)
    timestamp = Column(DateTime, nullable=False, index=True, default=datetime.utcnow)
    
    # US Treasury tenors (in percentage, e.g., 4.25 = 4.25%)
    tenor_1m = Column(Float)
    tenor_3m = Column(Float)
    tenor_6m = Column(Float)
    tenor_1y = Column(Float)
    tenor_2y = Column(Float)
    tenor_5y = Column(Float)
    tenor_10y = Column(Float)
    tenor_20y = Column(Float)
    tenor_30y = Column(Float)
    
    # Calculated spreads
    spread_10y2y = Column(Float)   # 10Y - 2Y (classic recession indicator)
    spread_10y3m = Column(Float)   # 10Y - 3M (alternative recession indicator)
    spread_30y10y = Column(Float)  # 30Y - 10Y (long end steepness)
    
    # Real yields (TIPS)
    tips_5y = Column(Float)
    tips_10y = Column(Float)
    
    # Metadata
    source = Column(String(50), default='fred')
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_yield_country_timestamp', 'country', 'timestamp'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            'country': self.country,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'curve': {
                '1M': self.tenor_1m,
                '3M': self.tenor_3m,
                '6M': self.tenor_6m,
                '1Y': self.tenor_1y,
                '2Y': self.tenor_2y,
                '5Y': self.tenor_5y,
                '10Y': self.tenor_10y,
                '20Y': self.tenor_20y,
                '30Y': self.tenor_30y,
            },
            'spreads': {
                '10Y-2Y': self.spread_10y2y,
                '10Y-3M': self.spread_10y3m,
                '30Y-10Y': self.spread_30y10y,
            },
            'tips': {
                '5Y': self.tips_5y,
                '10Y': self.tips_10y,
            }
        }


class CreditSpread(Base):
    """
    Credit Spread Storage
    
    Stores corporate bond spreads (OAS - Option-Adjusted Spread).
    Includes percentile calculations for risk detection.
    """
    __tablename__ = 'credit_spreads'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    index_name = Column(String(50), nullable=False, index=True)
    spread_bps = Column(Float, nullable=False)  # Spread in basis points
    timestamp = Column(DateTime, nullable=False, index=True, default=datetime.utcnow)
    
    # Historical percentile ranks
    percentile_90d = Column(Float)  # Percentile vs 90-day rolling window
    percentile_1y = Column(Float)   # Percentile vs 1-year history
    
    # Rolling averages
    avg_30d = Column(Float)
    avg_90d = Column(Float)
    
    # Daily change
    change_1d = Column(Float)
    change_1w = Column(Float)
    
    # FRED series ID for reference
    fred_series = Column(String(50))
    
    # Metadata
    source = Column(String(50), default='fred')
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_credit_index_timestamp', 'index_name', 'timestamp'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            'index_name': self.index_name,
            'spread_bps': self.spread_bps,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'percentile_90d': self.percentile_90d,
            'percentile_1y': self.percentile_1y,
            'avg_30d': self.avg_30d,
            'avg_90d': self.avg_90d,
            'change_1d': self.change_1d,
            'change_1w': self.change_1w
        }


class EconomicRelease(Base):
    """
    Economic Data Release Storage
    
    Stores economic indicator releases with consensus vs actual comparisons.
    Used for surprise detection and calendar tracking.
    """
    __tablename__ = 'economic_releases'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    indicator = Column(String(100), nullable=False, index=True)
    country = Column(String(50), nullable=False, default='US', index=True)
    release_date = Column(DateTime, nullable=False, index=True)
    
    # Values
    actual = Column(Float)
    consensus = Column(Float)
    previous = Column(Float)
    revised = Column(Float)  # Revision to previous value
    
    # Calculations
    surprise_pct = Column(Float)  # (Actual - Consensus) / Consensus * 100
    surprise_direction = Column(String(10))  # 'BEAT', 'MISS', 'INLINE'
    
    # Display formatting
    unit = Column(String(20))  # %, K, $B, index points, etc.
    frequency = Column(String(20))  # monthly, weekly, quarterly
    
    # FRED series ID
    fred_series = Column(String(50))
    
    # Status
    is_preliminary = Column(Boolean, default=True)
    
    # Metadata
    source = Column(String(50), default='fred')
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_econ_indicator_date', 'indicator', 'release_date'),
        Index('ix_econ_country_date', 'country', 'release_date'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            'indicator': self.indicator,
            'country': self.country,
            'release_date': self.release_date.isoformat() if self.release_date else None,
            'actual': self.actual,
            'consensus': self.consensus,
            'previous': self.previous,
            'surprise_pct': self.surprise_pct,
            'surprise_direction': self.surprise_direction,
            'unit': self.unit
        }


class NewsArticle(Base):
    """
    News Article Storage
    
    Stores aggregated news from multiple sources with severity tagging.
    Includes content hash for deduplication.
    """
    __tablename__ = 'news_articles'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    headline = Column(String(500), nullable=False)
    source = Column(String(100), nullable=False, index=True)
    url = Column(String(1000))
    
    # Timestamps
    published_at = Column(DateTime, nullable=False, index=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    
    # Categorization
    country_tags = Column(JSON)  # ['US', 'JAPAN', 'MEXICO']
    category = Column(String(50), index=True)  # ECON, FX, POLITICAL, CREDIT, CAT
    severity = Column(String(20), index=True)  # CRITICAL, HIGH, MEDIUM, LOW

    # Leader and institution detection (NEW)
    leader_mentions = Column(JSON)  # List of leader keys ['powell', 'lagarde']
    institutions = Column(JSON)  # List of institutions ['FED', 'ECB', 'WHITE_HOUSE']
    event_types = Column(JSON)  # List of event types ['RATE_DECISION', 'TRADE_POLICY']
    action_words = Column(JSON)  # List of action words detected ['announces', 'threatens']

    # For deduplication
    content_hash = Column(String(64), unique=True, index=True)

    # Optional full text (if scraped)
    full_text = Column(Text)
    summary = Column(Text)

    # Relevance scoring
    relevance_score = Column(Float)
    keyword_matches = Column(JSON)  # List of matched keywords
    
    # Processing status
    processed = Column(Boolean, default=False)
    alert_generated = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_news_source_published', 'source', 'published_at'),
        Index('ix_news_severity_published', 'severity', 'published_at'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            'id': self.id,
            'headline': self.headline,
            'source': self.source,
            'url': self.url,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'country_tags': self.country_tags or [],
            'category': self.category,
            'severity': self.severity,
            'summary': self.summary,
            'leader_mentions': self.leader_mentions or [],
            'institutions': self.institutions or [],
            'event_types': self.event_types or [],
            'action_words': self.action_words or []
        }


class RiskAlert(Base):
    """
    Risk Alert Storage
    
    Stores generated risk alerts with full audit trail.
    Used for email routing and dashboard display.
    """
    __tablename__ = 'risk_alerts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_type = Column(String(50), nullable=False, index=True)  # FX, YIELDS, CREDIT, POLITICAL, ECON, CAT
    severity = Column(String(20), nullable=False, index=True)    # CRITICAL, HIGH, MEDIUM
    
    # Alert content
    title = Column(String(200), nullable=False)
    message = Column(String(500), nullable=False)
    details = Column(JSON)  # Type-specific additional data
    
    # Timestamps
    triggered_at = Column(DateTime, nullable=False, index=True, default=datetime.utcnow)
    resolved_at = Column(DateTime)
    expires_at = Column(DateTime)  # Auto-expire old alerts
    
    # Related entities
    related_entity = Column(String(100))  # e.g., 'USD/JPY', 'HY_OAS', 'NFP'
    related_value = Column(Float)         # The value that triggered the alert
    threshold_value = Column(Float)       # The threshold that was breached
    
    # Status tracking
    is_active = Column(Boolean, default=True)
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime)
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime)
    
    # Deduplication
    alert_hash = Column(String(64), index=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_alert_type_severity', 'alert_type', 'severity'),
        Index('ix_alert_active_triggered', 'is_active', 'triggered_at'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            'id': self.id,
            'alert_type': self.alert_type,
            'severity': self.severity,
            'title': self.title,
            'message': self.message,
            'details': self.details,
            'triggered_at': self.triggered_at.isoformat() if self.triggered_at else None,
            'is_active': self.is_active,
            'acknowledged': self.acknowledged,
            'related_entity': self.related_entity,
            'related_value': self.related_value
        }


class SystemHealth(Base):
    """
    System Health Monitoring
    
    Tracks the health status of each module for dashboard display.
    Used for debugging and monitoring system stability.
    """
    __tablename__ = 'system_health'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    module_name = Column(String(50), nullable=False, index=True)
    
    # Status
    status = Column(String(20), nullable=False)  # OK, WARNING, ERROR, OFFLINE
    status_message = Column(String(500))
    
    # Timing
    last_successful_update = Column(DateTime)
    last_attempted_update = Column(DateTime)
    next_scheduled_update = Column(DateTime)
    
    # Error tracking
    last_error = Column(String(500))
    last_error_at = Column(DateTime)
    consecutive_failures = Column(Integer, default=0)
    total_errors_24h = Column(Integer, default=0)
    
    # Performance metrics
    avg_update_time_ms = Column(Float)
    records_processed = Column(Integer)
    
    # Metadata
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_health_module_timestamp', 'module_name', 'timestamp'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            'module_name': self.module_name,
            'status': self.status,
            'status_message': self.status_message,
            'last_successful_update': self.last_successful_update.isoformat() if self.last_successful_update else None,
            'consecutive_failures': self.consecutive_failures,
            'last_error': self.last_error
        }


class UserPreference(Base):
    """
    User Preferences Storage (for future multi-user support)
    
    Stores user-specific settings like alert thresholds and email preferences.
    """
    __tablename__ = 'user_preferences'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_email = Column(String(255), nullable=False, unique=True, index=True)
    
    # Email preferences
    receive_daily_digest = Column(Boolean, default=True)
    receive_critical_alerts = Column(Boolean, default=True)
    receive_high_alerts = Column(Boolean, default=True)
    digest_time = Column(String(5), default='07:00')  # HH:MM format
    
    # Custom thresholds (JSON to allow flexibility)
    custom_thresholds = Column(JSON)
    
    # Watched items
    watched_fx_pairs = Column(JSON)
    watched_indicators = Column(JSON)
    watched_countries = Column(JSON)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            'user_email': self.user_email,
            'receive_daily_digest': self.receive_daily_digest,
            'receive_critical_alerts': self.receive_critical_alerts,
            'digest_time': self.digest_time,
            'custom_thresholds': self.custom_thresholds
        }
