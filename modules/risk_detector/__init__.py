"""
Risk Detector Module - Centralized Risk Detection Engine

This module:
- Monitors outputs from all data modules
- Applies rule-based risk detection
- Generates and manages alerts
- Routes critical alerts for immediate notification

Risk Types (Priority Order):
1. ECON - Economic data surprises
2. FX - Currency volatility
3. POLITICAL - Geopolitical developments
4. CREDIT - Credit market stress
5. CAT - Catastrophic events
"""

from .config import RISK_HIERARCHY, ALERT_THRESHOLDS
from .fx_rules import detect_fx_risks
from .yield_rules import detect_yield_risks
from .credit_rules import detect_credit_risks
from .geopolitical_rules import detect_geopolitical_risks
from .economic_rules import detect_economic_risks
from .alert_manager import AlertManager
from .models import RiskAlertData

__all__ = [
    'RISK_HIERARCHY',
    'ALERT_THRESHOLDS',
    'detect_fx_risks',
    'detect_yield_risks',
    'detect_credit_risks',
    'detect_geopolitical_risks',
    'detect_economic_risks',
    'AlertManager',
    'RiskAlertData'
]
