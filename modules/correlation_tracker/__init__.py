"""
Cross-Asset Correlation Tracker

Real-time monitoring of cross-asset correlations to detect regime shifts.
Tracks stocks/bonds, currency-commodity, and credit-equity relationships.
"""

from .tracker import CorrelationTracker

__all__ = ['CorrelationTracker']
