"""
Credit Monitor Module

Tracks corporate credit spreads (Investment Grade and High Yield).
"""

from .models import CreditSpreadData, CreditUpdate, CreditAlert, CreditSummary
from .data_fetcher import CreditDataFetcher
from .storage import CreditStorage, store_credit_update, get_latest_credit_spreads

__all__ = [
    'CreditSpreadData',
    'CreditUpdate',
    'CreditAlert',
    'CreditSummary',
    'CreditDataFetcher',
    'CreditStorage',
    'store_credit_update',
    'get_latest_credit_spreads',
]