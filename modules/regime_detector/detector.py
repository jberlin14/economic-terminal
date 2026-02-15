"""
Regime Change Detector

Monitors multiple economic signals for regime shifts and generates
AI-powered explanations of detected changes.
"""

import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from loguru import logger

from pathlib import Path
from dotenv import load_dotenv
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / '.env')

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from modules.utils.timezone import get_current_time
from modules.data_storage.queries import QueryHelper


# Signal severity levels
SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"

# Regime classifications
REGIME_CRISIS = "CRISIS"
REGIME_RISK_OFF = "RISK_OFF"
REGIME_CAUTIOUS = "CAUTIOUS"
REGIME_RISK_ON = "RISK_ON"


def _get_indicator_values(db: Session, series_id: str, limit: int = 20) -> List[float]:
    """Get recent indicator values as a list of floats (most recent first)."""
    try:
        from modules.economic_indicators import IndicatorStorage
        storage = IndicatorStorage(db)
        df = storage.get_values(series_id)
        if df.empty:
            return []
        # Sort descending (most recent first) and return values
        df = df.sort_values('date', ascending=False).head(limit)
        return [float(v) for v in df['value'].tolist() if v is not None]
    except Exception as e:
        logger.debug(f"Failed to get indicator {series_id}: {e}")
        return []


class RegimeDetector:
    """Detects regime changes across multiple economic signal types."""

    # Cooldown tracking: {signal_type: last_trigger_time}
    _cooldowns: Dict[str, datetime] = {}
    _cooldown_hours = 24

    def __init__(self, db: Session, api_key: Optional[str] = None):
        self.db = db
        self.helper = QueryHelper(db)
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        self._client = None

    def _get_client(self):
        if not self._client and ANTHROPIC_AVAILABLE and self.api_key:
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def _is_on_cooldown(self, signal_type: str) -> bool:
        if signal_type not in self._cooldowns:
            return False
        elapsed = get_current_time() - self._cooldowns[signal_type]
        return elapsed < timedelta(hours=self._cooldown_hours)

    def _set_cooldown(self, signal_type: str):
        self._cooldowns[signal_type] = get_current_time()

    def assess_regime(self) -> Dict[str, Any]:
        """Run full regime assessment across all signal types."""
        start = time.time()
        shifts = []

        detectors = [
            self._check_sahm_rule,
            self._check_yield_curve_inversion,
            self._check_vix_spike,
            self._check_credit_stress,
            self._check_inflation_breakout,
            self._check_fed_policy_shift,
        ]

        for detector in detectors:
            try:
                result = detector()
                if result:
                    shifts.append(result)
            except Exception as e:
                logger.warning(f"Regime detector {detector.__name__} failed: {e}")

        regime = self._classify_regime(shifts)

        return {
            "regime": regime,
            "regime_description": self._regime_description(regime),
            "shifts": shifts,
            "critical_count": sum(1 for s in shifts if s["severity"] == SEVERITY_CRITICAL),
            "high_count": sum(1 for s in shifts if s["severity"] == SEVERITY_HIGH),
            "assessed_at": get_current_time().isoformat(),
            "elapsed_ms": round((time.time() - start) * 1000),
        }

    def get_shifts(self, include_ai: bool = True) -> Dict[str, Any]:
        """Get detected shifts with optional AI explanations."""
        assessment = self.assess_regime()

        if include_ai and assessment["shifts"]:
            for shift in assessment["shifts"]:
                if not self._is_on_cooldown(shift["signal"]):
                    shift["ai_explanation"] = self._generate_explanation(shift)
                    self._set_cooldown(shift["signal"])

        return assessment

    # ──────────────────────────────────────────────
    # Signal Detectors
    # ──────────────────────────────────────────────

    def _check_sahm_rule(self) -> Optional[Dict[str, Any]]:
        """Sahm Rule: 3-month avg unemployment rises 0.5pp+ above 12-month low."""
        values = _get_indicator_values(self.db, "UNRATE", limit=15)
        if len(values) < 12:
            return None

        ma_3 = sum(values[:3]) / 3
        low_12 = min(values[:12])
        sahm_value = ma_3 - low_12

        if sahm_value >= 0.5:
            severity = SEVERITY_CRITICAL if sahm_value >= 1.0 else SEVERITY_HIGH
            return {
                "signal": "sahm_rule",
                "signal_name": "Sahm Rule Recession Indicator",
                "severity": severity,
                "value": round(sahm_value, 2),
                "threshold": 0.5,
                "description": f"Sahm Rule triggered at {sahm_value:.2f}pp (threshold: 0.50pp). "
                               f"3-month avg unemployment ({ma_3:.1f}%) is {sahm_value:.2f}pp above "
                               f"12-month low ({low_12:.1f}%).",
                "detected_at": get_current_time().isoformat(),
            }
        return None

    def _check_yield_curve_inversion(self) -> Optional[Dict[str, Any]]:
        """Check if 10Y-2Y spread is inverted."""
        yc = self.helper.get_latest_yield_curve()
        if not yc:
            return None

        spread_10y2y = yc.spread_10y2y
        if spread_10y2y is not None and spread_10y2y < 0:
            severity = SEVERITY_CRITICAL if spread_10y2y < -0.5 else SEVERITY_HIGH
            return {
                "signal": "yield_curve_inversion",
                "signal_name": "Yield Curve Inversion",
                "severity": severity,
                "value": round(spread_10y2y, 3),
                "threshold": 0,
                "description": f"10Y-2Y spread inverted at {spread_10y2y:.3f}%. "
                               f"Historically precedes recessions by 12-18 months.",
                "detected_at": get_current_time().isoformat(),
            }
        return None

    def _check_vix_spike(self) -> Optional[Dict[str, Any]]:
        """Check if VIX is at elevated or extreme levels."""
        values = _get_indicator_values(self.db, "VIXCLS", limit=3)
        # Fall back to yfinance if not in FRED indicators DB
        if not values:
            try:
                import yfinance as yf
                import pandas as pd
                data = yf.download("^VIX", period="5d", progress=False, auto_adjust=True)
                if len(data) > 0:
                    close = data["Close"]
                    if isinstance(close, pd.DataFrame):
                        close = close.iloc[:, 0]
                    values = [float(close.iloc[-1])]
            except Exception:
                pass
        if not values:
            return None

        vix = values[0]

        if vix >= 40:
            return {
                "signal": "vix_extreme",
                "signal_name": "Extreme VIX Spike",
                "severity": SEVERITY_CRITICAL,
                "value": round(vix, 1),
                "threshold": 40,
                "description": f"VIX at extreme level ({vix:.1f}). Indicates panic-level "
                               f"volatility and severe market stress.",
                "detected_at": get_current_time().isoformat(),
            }
        elif vix >= 30:
            return {
                "signal": "vix_elevated",
                "signal_name": "Elevated VIX",
                "severity": SEVERITY_HIGH,
                "value": round(vix, 1),
                "threshold": 30,
                "description": f"VIX elevated at {vix:.1f}. Signals heightened market "
                               f"uncertainty and risk-off sentiment.",
                "detected_at": get_current_time().isoformat(),
            }
        return None

    def _check_credit_stress(self) -> Optional[Dict[str, Any]]:
        """Check if credit spreads indicate stress."""
        spreads = self.helper.get_latest_credit_spreads()
        if not spreads:
            return None

        for spread in spreads:
            index_name = spread.index_name
            current = spread.spread_bps
            avg = spread.avg_90d

            if current and avg and avg > 0:
                ratio = current / avg
                if ratio >= 2.0:
                    return {
                        "signal": "credit_stress",
                        "signal_name": "Credit Spread Blow-Out",
                        "severity": SEVERITY_CRITICAL if ratio >= 3.0 else SEVERITY_HIGH,
                        "value": round(current, 1),
                        "threshold": round(avg * 2, 1),
                        "description": f"{index_name} spread at {current:.0f}bps, "
                                       f"{ratio:.1f}x above 90d average ({avg:.0f}bps). "
                                       f"Indicates significant credit market stress.",
                        "detected_at": get_current_time().isoformat(),
                    }
        return None

    def _check_inflation_breakout(self) -> Optional[Dict[str, Any]]:
        """Check if inflation is breaking out above target."""
        values = _get_indicator_values(self.db, "CPIAUCSL", limit=15)
        if len(values) < 13:
            return None

        yoy = ((values[0] - values[12]) / values[12]) * 100

        if yoy >= 5.0:
            return {
                "signal": "inflation_breakout",
                "signal_name": "Inflation Breakout",
                "severity": SEVERITY_CRITICAL if yoy >= 7.0 else SEVERITY_HIGH,
                "value": round(yoy, 1),
                "threshold": 5.0,
                "description": f"CPI YoY at {yoy:.1f}%, well above 2% target. "
                               f"Persistent elevated inflation pressures policy response.",
                "detected_at": get_current_time().isoformat(),
            }
        elif yoy >= 3.5:
            return {
                "signal": "inflation_elevated",
                "signal_name": "Elevated Inflation",
                "severity": SEVERITY_MEDIUM,
                "value": round(yoy, 1),
                "threshold": 3.5,
                "description": f"CPI YoY at {yoy:.1f}%, above comfort zone. "
                               f"May constrain Fed easing options.",
                "detected_at": get_current_time().isoformat(),
            }
        return None

    def _check_fed_policy_shift(self) -> Optional[Dict[str, Any]]:
        """Check for Fed funds rate direction changes."""
        values = _get_indicator_values(self.db, "FEDFUNDS", limit=5)
        if len(values) < 3:
            return None

        recent_change = values[0] - values[1]
        prior_change = values[1] - values[2]

        if recent_change > 0 and prior_change <= 0:
            return {
                "signal": "fed_hike_pivot",
                "signal_name": "Fed Hawkish Pivot",
                "severity": SEVERITY_HIGH,
                "value": values[0],
                "threshold": None,
                "description": f"Fed funds rate increased to {values[0]:.2f}% after "
                               f"holding/cutting. Signals hawkish policy shift.",
                "detected_at": get_current_time().isoformat(),
            }
        elif recent_change < 0 and prior_change >= 0:
            return {
                "signal": "fed_cut_pivot",
                "signal_name": "Fed Dovish Pivot",
                "severity": SEVERITY_MEDIUM,
                "value": values[0],
                "threshold": None,
                "description": f"Fed funds rate cut to {values[0]:.2f}% after "
                               f"holding/hiking. Signals dovish policy shift.",
                "detected_at": get_current_time().isoformat(),
            }
        return None

    # ──────────────────────────────────────────────
    # Regime Classification
    # ──────────────────────────────────────────────

    def _classify_regime(self, shifts: List[Dict[str, Any]]) -> str:
        if not shifts:
            return REGIME_RISK_ON

        critical = sum(1 for s in shifts if s["severity"] == SEVERITY_CRITICAL)
        high = sum(1 for s in shifts if s["severity"] == SEVERITY_HIGH)

        if critical >= 2:
            return REGIME_CRISIS
        elif critical >= 1 or high >= 3:
            return REGIME_RISK_OFF
        elif high >= 1:
            return REGIME_CAUTIOUS
        return REGIME_RISK_ON

    def _regime_description(self, regime: str) -> str:
        descriptions = {
            REGIME_CRISIS: "Multiple critical stress signals detected. Crisis-level conditions.",
            REGIME_RISK_OFF: "Significant stress indicators present. Defensive positioning warranted.",
            REGIME_CAUTIOUS: "Elevated risk signals detected. Increased monitoring recommended.",
            REGIME_RISK_ON: "No significant stress signals. Normal market conditions.",
        }
        return descriptions.get(regime, "Unknown regime state.")

    # ──────────────────────────────────────────────
    # AI Explanation
    # ──────────────────────────────────────────────

    def _generate_explanation(self, shift: Dict[str, Any]) -> Optional[str]:
        client = self._get_client()
        if not client:
            return None

        try:
            prompt = (
                f"In 2-3 sentences, explain the economic significance of this regime shift signal "
                f"for institutional investors:\n\n"
                f"Signal: {shift['signal_name']}\n"
                f"Severity: {shift['severity']}\n"
                f"Details: {shift['description']}\n\n"
                f"Be specific about historical precedent and actionable implications."
            )

            message = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
                system="You are a senior macro strategist at a major investment bank. Be concise and precise.",
            )
            return message.content[0].text
        except Exception as e:
            logger.warning(f"AI explanation generation failed: {e}")
            return None
