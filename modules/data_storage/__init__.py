"""
Data Storage Module - Database Management for Economic Terminal

This module provides:
- SQLAlchemy database connection management
- Table schema definitions
- Common query helpers
- Migration support via Alembic
"""

from .database import get_db, init_db, engine, SessionLocal
from .schema import (
    Base,
    FXRate,
    YieldCurve,
    CreditSpread,
    EconomicRelease,
    NewsArticle,
    RiskAlert,
    SystemHealth
)
from .queries import QueryHelper

__all__ = [
    'get_db',
    'init_db',
    'engine',
    'SessionLocal',
    'Base',
    'FXRate',
    'YieldCurve',
    'CreditSpread',
    'EconomicRelease',
    'NewsArticle',
    'RiskAlert',
    'SystemHealth',
    'QueryHelper'
]
