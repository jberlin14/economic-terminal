"""
Regime Change Detection Engine

Monitors multiple economic signals for regime shifts and generates
AI-powered explanations of what changed and why it matters.
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


# Regime shift detection rules
REGIME_RULES = {
    "sahm_rule": {
        "name": "Sahm Rule",
        "description": "Unemployment rate 3-month MA rises 0.50pp+ above prior 12-month low",
        "severity": "CRITICAL",
        "threshold": 0.50,
        "warning_threshold": 0.30,
    },
    "yield_curve_steepening": {
        "name": "Yield Curve Steepening",
        "description": "2s10s spread widens >20bp in a week",
        "severity": "HIGH",
        "threshold_bps": 20,
    },
    "yield_curve_inversion": {
        "name": "Yield Curve Inversion",
        "description": "10Y-2Y spread turns negative",
        "severity": "CRITICAL",
        "threshold_bps": 0,
    },
    "vix_spike": {
        "name": "VIX Spike",
        "description": "VIX rises >5 points from prior close",
        "severity": "HIGH",
        "threshold_points": 5,
        "critical_threshold": 10,
    },
    "credit_stress": {
        "name": "Credit Stress",
        "description": "HY spreads widen >50bp in a week",
        "severity": "HIGH",
        "threshold_bps": 50,
    },
    "fed_policy_shift": {
        "name": "Fed Policy Shift",
        "description": "Fed speaker contradicts market consensus",
        "severity": "HIGH",
    },
    "inflation_breakout": {
        "name": "Inflation Breakout",
        "description": "CPI YoY accelerates >0.3pp month-over-month",
        "severity": "HIGH",
        "threshold_pp": 0.3,
    },
}


EXPLANATION_PROMPT = """You are a senior macro strategist explaining a regime shift detection to a portfolio manager.

Given the detected regime change and supporting data, write a concise explanation (100-200 words) covering:
1. What triggered the signal
2. Historical context (when has this happened before?)
3. What typically follows
4. Key risks and implications
5. What to watch next

Be specific with numbers. No hedging. Direct and actionable."""


class RegimeShift:
    """Represents a detected regime change event."""

    def __init__(
        self,
        rule_id: str,
        name: str,
        severity: str,
        description: str,
        current_value: float,
        threshold: float,
        prior_value: Optional[float] = None,
        change: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.rule_id = rule_id
        self.name = name
        self.severity = severity
        self.description = description
        self.current_value = current_value
        self.threshold = threshold
        self.prior_value = prior_value
        self.change = change
        self.details = details or {}
        self.detected_at = datetime.utcnow()
        self.explanation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "severity": self.severity,
            "description": self.description,
            "current_value": self.current_value,
            "threshold": self.threshold,
            "prior_value": self.prior_value,
            "change": self.change,
            "details": self.details,
            "detected_at": self.detected_at.isoformat(),
            "explanation": self.explanation,
        }


class RegimeChangeDetector:
    """
    Detects economic regime shifts across multiple signal types
    and generates AI-powered explanations.
    """

    # Cache recent detections to avoid duplicate alerts
    _recent_detections: Dict[str, datetime] = {}
    _cooldown_minutes = 60

    def __init__(self, db: Session, api_key: Optional[str] = None):
        self.db = db
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        self._client = None

    def _get_client(self):
        if not self._client and ANTHROPIC_AVAILABLE and self.api_key:
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def _is_on_cooldown(self, rule_id: str) -> bool:
        if rule_id not in self._recent_detections:
            return False
        elapsed = (datetime.utcnow() - self._recent_detections[rule_id]).total_seconds() / 60
        return elapsed < self._cooldown_minutes

    def _mark_detected(self, rule_id: str):
        self._recent_detections[rule_id] = datetime.utcnow()

    def detect_all(self) -> List[RegimeShift]:
        """Run all regime detection rules and return any triggered shifts."""
        shifts = []

        shifts.extend(self._check_sahm_rule())
        shifts.extend(self._check_yield_curve())
        shifts.extend(self._check_vix())
        shifts.extend(self._check_credit_stress())
        shifts.extend(self._check_inflation())
        shifts.extend(self._check_fed_policy())

        return shifts

    async def detect_and_explain(self) -> List[Dict[str, Any]]:
        """Detect regime shifts and generate AI explanations for each."""
        shifts = self.detect_all()

        if not shifts:
            return []

        # Generate explanations for each shift
        for shift in shifts:
            if not self._is_on_cooldown(shift.rule_id):
                shift.explanation = await self._generate_explanation(shift)
                self._mark_detected(shift.rule_id)

        return [s.to_dict() for s in shifts if shift.explanation or not self._is_on_cooldown(s.rule_id)]

    def _check_sahm_rule(self) -> List[RegimeShift]:
        """Check Sahm Rule: unemployment 3mo MA vs 12mo low."""
        import numpy as np
        shifts = []

        try:
            from modules.economic_indicators import IndicatorStorage
            storage = IndicatorStorage(self.db)

            start = datetime.utcnow().date() - timedelta(days=730)
            df = storage.get_values("UNRATE", start_date=start)

            if df is None or df.empty or len(df) < 15:
                return shifts

            values = df['value'].values
            ma3 = np.convolve(values, np.ones(3) / 3, mode='valid')

            if len(ma3) >= 13:
                current_ma3 = float(ma3[-1])
                min_ma3_12m = float(np.min(ma3[-13:-1]))
                sahm = round(current_ma3 - min_ma3_12m, 2)

                rule = REGIME_RULES["sahm_rule"]

                if sahm >= rule["threshold"]:
                    shifts.append(RegimeShift(
                        rule_id="sahm_rule",
                        name=rule["name"],
                        severity="CRITICAL",
                        description=f"Sahm Rule TRIGGERED at {sahm:.2f} (threshold: {rule['threshold']})",
                        current_value=sahm,
                        threshold=rule["threshold"],
                        details={
                            "current_ma3": round(current_ma3, 2),
                            "min_ma3_12m": round(min_ma3_12m, 2),
                            "latest_unrate": float(values[-1]),
                        }
                    ))
                elif sahm >= rule["warning_threshold"]:
                    shifts.append(RegimeShift(
                        rule_id="sahm_rule_warning",
                        name=f"{rule['name']} Warning",
                        severity="HIGH",
                        description=f"Sahm Rule approaching trigger at {sahm:.2f} (threshold: {rule['threshold']})",
                        current_value=sahm,
                        threshold=rule["threshold"],
                        details={
                            "current_ma3": round(current_ma3, 2),
                            "min_ma3_12m": round(min_ma3_12m, 2),
                        }
                    ))
        except Exception as e:
            logger.debug(f"Sahm Rule check error: {e}")

        return shifts

    def _check_yield_curve(self) -> List[RegimeShift]:
        """Check yield curve for steepening/flattening and inversions."""
        shifts = []

        try:
            from modules.data_storage.schema import YieldCurve
            from modules.data_storage.queries import QueryHelper

            helper = QueryHelper(self.db)
            current = self.db.query(YieldCurve).order_by(YieldCurve.timestamp.desc()).first()

            if not current or current.tenor_10y is None or current.tenor_2y is None:
                return shifts

            current_spread = current.tenor_10y - current.tenor_2y
            current_spread_bps = current_spread * 100

            # Check inversion
            if current_spread_bps < 0:
                shifts.append(RegimeShift(
                    rule_id="yield_curve_inversion",
                    name="Yield Curve Inversion",
                    severity="CRITICAL",
                    description=f"2s10s spread inverted at {current_spread_bps:+.0f}bps",
                    current_value=current_spread_bps,
                    threshold=0,
                    details={
                        "tenor_10y": current.tenor_10y,
                        "tenor_2y": current.tenor_2y,
                    }
                ))

            # Check weekly steepening/flattening
            history = helper.get_yield_curve_history(days=10)
            week_ago = None
            for h in history:
                if h.timestamp and h.tenor_10y and h.tenor_2y:
                    diff = (datetime.utcnow() - h.timestamp).total_seconds() / 86400
                    if 5 <= diff <= 10:
                        week_ago = h
                        break

            if week_ago and week_ago.tenor_10y and week_ago.tenor_2y:
                prev_spread = week_ago.tenor_10y - week_ago.tenor_2y
                change_bps = (current_spread - prev_spread) * 100

                rule = REGIME_RULES["yield_curve_steepening"]
                if abs(change_bps) >= rule["threshold_bps"]:
                    direction = "steepening" if change_bps > 0 else "flattening"
                    shifts.append(RegimeShift(
                        rule_id="yield_curve_steepening",
                        name=f"Rapid Curve {direction.title()}",
                        severity="HIGH",
                        description=f"2s10s spread changed {change_bps:+.0f}bps in one week",
                        current_value=current_spread_bps,
                        threshold=rule["threshold_bps"],
                        prior_value=prev_spread * 100,
                        change=change_bps,
                        details={
                            "direction": direction,
                            "current_10y": current.tenor_10y,
                            "current_2y": current.tenor_2y,
                            "prior_10y": week_ago.tenor_10y,
                            "prior_2y": week_ago.tenor_2y,
                        }
                    ))

        except Exception as e:
            logger.debug(f"Yield curve check error: {e}")

        return shifts

    def _check_vix(self) -> List[RegimeShift]:
        """Check VIX for spikes."""
        shifts = []

        try:
            from modules.economic_indicators import IndicatorStorage
            storage = IndicatorStorage(self.db)

            start = datetime.utcnow().date() - timedelta(days=30)
            df = storage.get_values("VIXCLS", start_date=start)

            if df is None or df.empty or len(df) < 2:
                return shifts

            current_vix = float(df['value'].iloc[-1])
            prior_vix = float(df['value'].iloc[-2])
            change = current_vix - prior_vix

            rule = REGIME_RULES["vix_spike"]

            if change >= rule.get("critical_threshold", 10):
                shifts.append(RegimeShift(
                    rule_id="vix_spike",
                    name="VIX Spike - Critical",
                    severity="CRITICAL",
                    description=f"VIX surged {change:+.1f} points to {current_vix:.1f}",
                    current_value=current_vix,
                    threshold=rule["critical_threshold"],
                    prior_value=prior_vix,
                    change=change,
                    details={"level_assessment": "PANIC" if current_vix > 30 else "FEAR"}
                ))
            elif change >= rule["threshold_points"]:
                shifts.append(RegimeShift(
                    rule_id="vix_spike",
                    name="VIX Spike",
                    severity="HIGH",
                    description=f"VIX rose {change:+.1f} points to {current_vix:.1f}",
                    current_value=current_vix,
                    threshold=rule["threshold_points"],
                    prior_value=prior_vix,
                    change=change,
                    details={"level_assessment": "ELEVATED" if current_vix > 20 else "NERVOUS"}
                ))

        except Exception as e:
            logger.debug(f"VIX check error: {e}")

        return shifts

    def _check_credit_stress(self) -> List[RegimeShift]:
        """Check credit spreads for stress signals."""
        shifts = []

        try:
            from modules.data_storage.queries import QueryHelper
            helper = QueryHelper(self.db)

            spreads = helper.get_latest_credit_spreads()
            for spread in spreads:
                if 'HY' in (spread.index_name or '').upper() or 'HIGH' in (spread.index_name or '').upper():
                    if spread.change_1w is not None:
                        rule = REGIME_RULES["credit_stress"]
                        if spread.change_1w >= rule["threshold_bps"]:
                            shifts.append(RegimeShift(
                                rule_id="credit_stress",
                                name="Credit Stress - HY Widening",
                                severity="HIGH",
                                description=f"HY spreads widened {spread.change_1w:+.0f}bps to {spread.spread_bps:.0f}bps",
                                current_value=spread.spread_bps,
                                threshold=rule["threshold_bps"],
                                change=spread.change_1w,
                                details={
                                    "index": spread.index_name,
                                    "percentile_90d": spread.percentile_90d,
                                    "percentile_1y": spread.percentile_1y,
                                }
                            ))

        except Exception as e:
            logger.debug(f"Credit stress check error: {e}")

        return shifts

    def _check_inflation(self) -> List[RegimeShift]:
        """Check for inflation regime shifts."""
        shifts = []

        try:
            from modules.economic_indicators import IndicatorStorage
            from modules.economic_indicators.transformer import DataTransformer
            storage = IndicatorStorage(self.db)
            transformer = DataTransformer()

            start = datetime.utcnow().date() - timedelta(days=730)
            df = storage.get_values("CPIAUCSL", start_date=start)

            if df is None or df.empty or len(df) < 14:
                return shifts

            values = df['value'].values

            # Compute YoY for last two months
            if len(values) >= 14:
                current_yoy = ((values[-1] - values[-13]) / abs(values[-13])) * 100
                prior_yoy = ((values[-2] - values[-14]) / abs(values[-14])) * 100
                acceleration = current_yoy - prior_yoy

                rule = REGIME_RULES["inflation_breakout"]
                if acceleration >= rule["threshold_pp"]:
                    shifts.append(RegimeShift(
                        rule_id="inflation_breakout",
                        name="Inflation Acceleration",
                        severity="HIGH",
                        description=f"CPI YoY accelerated {acceleration:+.2f}pp to {current_yoy:.2f}%",
                        current_value=current_yoy,
                        threshold=rule["threshold_pp"],
                        prior_value=prior_yoy,
                        change=acceleration,
                        details={
                            "current_yoy": round(current_yoy, 2),
                            "prior_yoy": round(prior_yoy, 2),
                        }
                    ))

        except Exception as e:
            logger.debug(f"Inflation check error: {e}")

        return shifts

    def _check_fed_policy(self) -> List[RegimeShift]:
        """Check news for Fed policy shift signals."""
        shifts = []

        try:
            from modules.data_storage.schema import NewsArticle
            from sqlalchemy import or_

            two_days_ago = datetime.utcnow() - timedelta(days=2)

            # Look for Fed-related high-severity news
            fed_news = self.db.query(NewsArticle).filter(
                NewsArticle.published_at >= two_days_ago,
                NewsArticle.severity.in_(['CRITICAL', 'HIGH']),
                or_(
                    NewsArticle.headline.ilike('%fed %'),
                    NewsArticle.headline.ilike('%fomc%'),
                    NewsArticle.headline.ilike('%powell%'),
                    NewsArticle.headline.ilike('%rate cut%'),
                    NewsArticle.headline.ilike('%rate hike%'),
                    NewsArticle.headline.ilike('%hawkish%'),
                    NewsArticle.headline.ilike('%dovish%'),
                )
            ).order_by(NewsArticle.published_at.desc()).limit(5).all()

            # Check for contradictory signals (hawkish + dovish in same period)
            hawkish_count = 0
            dovish_count = 0
            headlines = []

            for article in fed_news:
                title = (article.headline or "").lower()
                headlines.append(article.headline)
                if any(kw in title for kw in ['hawkish', 'rate hike', 'higher for longer', 'tighten']):
                    hawkish_count += 1
                if any(kw in title for kw in ['dovish', 'rate cut', 'pivot', 'pause', 'easing']):
                    dovish_count += 1

            if hawkish_count >= 2 and dovish_count == 0:
                shifts.append(RegimeShift(
                    rule_id="fed_policy_shift",
                    name="Fed Hawkish Shift",
                    severity="HIGH",
                    description=f"Multiple hawkish Fed signals detected ({hawkish_count} headlines)",
                    current_value=hawkish_count,
                    threshold=2,
                    details={"headlines": headlines[:3], "direction": "hawkish"}
                ))
            elif dovish_count >= 2 and hawkish_count == 0:
                shifts.append(RegimeShift(
                    rule_id="fed_policy_shift",
                    name="Fed Dovish Shift",
                    severity="HIGH",
                    description=f"Multiple dovish Fed signals detected ({dovish_count} headlines)",
                    current_value=dovish_count,
                    threshold=2,
                    details={"headlines": headlines[:3], "direction": "dovish"}
                ))

        except Exception as e:
            logger.debug(f"Fed policy check error: {e}")

        return shifts

    async def _generate_explanation(self, shift: RegimeShift) -> Optional[str]:
        """Generate an AI explanation for a regime shift."""
        client = self._get_client()
        if not client:
            return self._generate_template_explanation(shift)

        try:
            details_str = "\n".join(f"  {k}: {v}" for k, v in shift.details.items())

            user_msg = f"""Regime shift detected:

Signal: {shift.name}
Severity: {shift.severity}
Description: {shift.description}
Current Value: {shift.current_value}
Threshold: {shift.threshold}
{f'Prior Value: {shift.prior_value}' if shift.prior_value is not None else ''}
{f'Change: {shift.change}' if shift.change is not None else ''}
Additional Details:
{details_str}

Timestamp: {get_current_time().isoformat()}

Write a concise explanation for a portfolio manager."""

            message = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=400,
                system=EXPLANATION_PROMPT,
                messages=[{"role": "user", "content": user_msg}]
            )

            return message.content[0].text

        except Exception as e:
            logger.error(f"Failed to generate explanation: {e}")
            return self._generate_template_explanation(shift)

    def _generate_template_explanation(self, shift: RegimeShift) -> str:
        """Fallback template explanation when AI is unavailable."""
        templates = {
            "sahm_rule": f"The Sahm Rule indicator at {shift.current_value:.2f} has {'triggered' if shift.current_value >= 0.50 else 'approached the trigger'}. Historically, this signal has preceded every US recession since 1970. Monitor initial claims, JOLTS, and consumer spending for confirmation.",
            "yield_curve_inversion": f"The 2s10s spread has inverted to {shift.current_value:+.0f}bps. Yield curve inversions have preceded 7 of the last 7 recessions, typically 12-18 months ahead. Watch for steepening as the more immediate recession signal.",
            "yield_curve_steepening": f"The 2s10s spread moved {shift.change:+.0f}bps this week to {shift.current_value:+.0f}bps. Rapid {shift.details.get('direction', 'movement')} often signals shifting rate expectations. Monitor Fed Funds futures for policy repricing.",
            "vix_spike": f"VIX surged {shift.change:+.1f} to {shift.current_value:.1f}. Spikes of this magnitude typically reflect a risk-off event. Historical median drawdown following similar spikes is 3-5% over the next month. Watch for mean reversion or persistence.",
            "credit_stress": f"HY spreads widened {shift.change:+.0f}bps to {shift.current_value:.0f}bps. Credit stress of this magnitude warrants monitoring for contagion to IG and potential liquidity issues. Check CDS indices and loan markets.",
            "inflation_breakout": f"CPI YoY accelerated {shift.change:+.2f}pp to {shift.current_value:.2f}%. Inflation acceleration at this rate reprices Fed rate path expectations. Watch breakevens and Fed funds futures.",
            "fed_policy_shift": f"Multiple {shift.details.get('direction', 'policy')} Fed signals detected. This may indicate a shift in the Fed's reaction function. Monitor upcoming FOMC communications and dot plot revisions.",
        }

        return templates.get(shift.rule_id, shift.description)

    def get_current_regime(self) -> Dict[str, Any]:
        """Get a comprehensive regime assessment."""
        shifts = self.detect_all()

        # Classify overall regime
        critical_count = sum(1 for s in shifts if s.severity == "CRITICAL")
        high_count = sum(1 for s in shifts if s.severity == "HIGH")

        if critical_count >= 2:
            overall = "CRISIS"
        elif critical_count >= 1:
            overall = "RISK_OFF"
        elif high_count >= 2:
            overall = "CAUTIOUS"
        elif high_count >= 1:
            overall = "WATCHFUL"
        else:
            overall = "RISK_ON"

        return {
            "regime": overall,
            "timestamp": get_current_time().isoformat(),
            "active_shifts": [s.to_dict() for s in shifts],
            "shift_count": len(shifts),
            "critical_count": critical_count,
            "high_count": high_count,
            "rules_checked": list(REGIME_RULES.keys()),
        }
