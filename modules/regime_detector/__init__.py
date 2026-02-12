"""
Regime Change Detection & Alerts

Monitors for economic regime shifts and generates AI-powered explanations.
Detects events like Sahm Rule triggers, yield curve steepening, VIX spikes,
and Fed policy shifts with contextual narratives.
"""

from .detector import RegimeChangeDetector

__all__ = ['RegimeChangeDetector']
