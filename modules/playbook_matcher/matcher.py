"""
Historical Playbook Matching Engine

Compares current economic conditions against historical episodes to find
analogous periods. Shows what happened next in similar setups.
"""

import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
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

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

from modules.utils.timezone import get_current_time


# Historical episodes with their defining characteristics
HISTORICAL_EPISODES = {
    "2008_gfc": {
        "name": "2008 Global Financial Crisis",
        "period": "2007-06 to 2009-03",
        "peak_date": "2008-09",
        "characteristics": {
            "yield_curve_inverted": True,
            "credit_stress_high": True,
            "vix_elevated": True,
            "unemployment_rising": True,
            "inflation_declining": True,
            "fed_cutting": True,
        },
        "indicators": {
            "UNRATE": {"range": [4.5, 10.0], "direction": "rising"},
            "VIXCLS": {"range": [20, 80], "direction": "rising"},
            "FEDFUNDS": {"range": [0.0, 5.25], "direction": "falling"},
            "spread_10y2y_bps": {"range": [-20, 260], "direction": "steepening"},
        },
        "what_followed": "S&P 500 fell 57% peak-to-trough. Fed cut to zero. QE1 launched. Recovery began March 2009. Unemployment peaked at 10% in Oct 2009.",
        "duration_months": 18,
    },
    "2020_covid": {
        "name": "2020 COVID Crash",
        "period": "2020-02 to 2020-04",
        "peak_date": "2020-03",
        "characteristics": {
            "yield_curve_inverted": False,
            "credit_stress_high": True,
            "vix_elevated": True,
            "unemployment_rising": True,
            "inflation_declining": True,
            "fed_cutting": True,
        },
        "indicators": {
            "UNRATE": {"range": [3.5, 14.7], "direction": "rising"},
            "VIXCLS": {"range": [15, 82], "direction": "spiking"},
            "FEDFUNDS": {"range": [0.0, 1.75], "direction": "falling"},
        },
        "what_followed": "S&P 500 fell 34% in 33 days, recovered to new highs by August 2020. Massive fiscal/monetary stimulus. V-shaped recovery. Inflation surge followed in 2021-2022.",
        "duration_months": 2,
    },
    "1998_ltcm": {
        "name": "1998 LTCM/Russia Crisis",
        "period": "1998-07 to 1998-11",
        "peak_date": "1998-09",
        "characteristics": {
            "yield_curve_inverted": False,
            "credit_stress_high": True,
            "vix_elevated": True,
            "unemployment_rising": False,
            "inflation_declining": True,
            "fed_cutting": True,
        },
        "indicators": {
            "UNRATE": {"range": [4.3, 4.6], "direction": "stable"},
            "VIXCLS": {"range": [20, 45], "direction": "spiking"},
            "FEDFUNDS": {"range": [4.75, 5.50], "direction": "falling"},
        },
        "what_followed": "S&P 500 fell 19%, recovered within 3 months. Fed cut 75bp in emergency moves. No recession. Dot-com bubble continued into 2000.",
        "duration_months": 4,
    },
    "2022_tightening": {
        "name": "2022 Fed Tightening Cycle",
        "period": "2022-01 to 2023-07",
        "peak_date": "2022-06",
        "characteristics": {
            "yield_curve_inverted": True,
            "credit_stress_high": False,
            "vix_elevated": True,
            "unemployment_rising": False,
            "inflation_declining": False,
            "fed_cutting": False,
        },
        "indicators": {
            "UNRATE": {"range": [3.4, 3.7], "direction": "stable"},
            "VIXCLS": {"range": [20, 36], "direction": "elevated"},
            "FEDFUNDS": {"range": [0.25, 5.50], "direction": "rising"},
            "spread_10y2y_bps": {"range": [-110, 40], "direction": "inverting"},
        },
        "what_followed": "S&P 500 fell 25%, then recovered. Deep yield curve inversion. No recession materialized. Inflation peaked at 9.1% and declined. Soft landing narrative.",
        "duration_months": 18,
    },
    "2015_taper_tantrum_aftermath": {
        "name": "2015-2016 Global Slowdown Scare",
        "period": "2015-08 to 2016-02",
        "peak_date": "2016-01",
        "characteristics": {
            "yield_curve_inverted": False,
            "credit_stress_high": True,
            "vix_elevated": True,
            "unemployment_rising": False,
            "inflation_declining": True,
            "fed_cutting": False,
        },
        "indicators": {
            "UNRATE": {"range": [4.9, 5.1], "direction": "stable"},
            "VIXCLS": {"range": [15, 28], "direction": "elevated"},
            "FEDFUNDS": {"range": [0.25, 0.50], "direction": "rising"},
        },
        "what_followed": "S&P 500 fell 13%. China devaluation fears. Oil crashed to $26. Fed paused hikes. Recovery by mid-2016. No recession.",
        "duration_months": 6,
    },
    "2019_inversion": {
        "name": "2019 Yield Curve Inversion & Insurance Cuts",
        "period": "2019-05 to 2019-10",
        "peak_date": "2019-08",
        "characteristics": {
            "yield_curve_inverted": True,
            "credit_stress_high": False,
            "vix_elevated": False,
            "unemployment_rising": False,
            "inflation_declining": True,
            "fed_cutting": True,
        },
        "indicators": {
            "UNRATE": {"range": [3.5, 3.7], "direction": "stable"},
            "VIXCLS": {"range": [12, 24], "direction": "moderate"},
            "FEDFUNDS": {"range": [1.50, 2.50], "direction": "falling"},
            "spread_10y2y_bps": {"range": [-10, 20], "direction": "inverting"},
        },
        "what_followed": "Fed cut 75bp (3 'insurance' cuts). Curve re-steepened. No recession from inversion itself — COVID intervened. Trade war with China dominated.",
        "duration_months": 5,
    },
}


class PlaybookMatch:
    """Represents a match between current conditions and a historical episode."""

    def __init__(
        self,
        episode_id: str,
        episode_name: str,
        similarity_score: float,
        matching_signals: List[str],
        diverging_signals: List[str],
        what_followed: str,
        period: str,
        duration_months: int,
    ):
        self.episode_id = episode_id
        self.episode_name = episode_name
        self.similarity_score = similarity_score
        self.matching_signals = matching_signals
        self.diverging_signals = diverging_signals
        self.what_followed = what_followed
        self.period = period
        self.duration_months = duration_months
        self.ai_analysis: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "episode_name": self.episode_name,
            "similarity_score": self.similarity_score,
            "similarity_pct": round(self.similarity_score * 100, 1),
            "matching_signals": self.matching_signals,
            "diverging_signals": self.diverging_signals,
            "what_followed": self.what_followed,
            "period": self.period,
            "duration_months": self.duration_months,
            "ai_analysis": self.ai_analysis,
        }


class PlaybookMatcher:
    """
    Matches current economic conditions against historical episodes.
    Provides pattern recognition with probabilistic outcomes.
    """

    def __init__(self, db: Session, api_key: Optional[str] = None):
        self.db = db
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        self._client = None

    def _get_client(self):
        if not self._client and ANTHROPIC_AVAILABLE and self.api_key:
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def _get_current_conditions(self) -> Dict[str, Any]:
        """Assess current economic conditions for matching."""
        conditions = {
            "yield_curve_inverted": False,
            "credit_stress_high": False,
            "vix_elevated": False,
            "unemployment_rising": False,
            "inflation_declining": False,
            "fed_cutting": False,
        }

        indicator_values = {}

        try:
            # Yield curve
            from modules.data_storage.schema import YieldCurve
            curve = self.db.query(YieldCurve).order_by(YieldCurve.timestamp.desc()).first()
            if curve and curve.tenor_10y is not None and curve.tenor_2y is not None:
                spread = (curve.tenor_10y - curve.tenor_2y) * 100
                conditions["yield_curve_inverted"] = spread < 0
                indicator_values["spread_10y2y_bps"] = spread

            # Credit spreads
            from modules.data_storage.queries import QueryHelper
            helper = QueryHelper(self.db)
            spreads = helper.get_latest_credit_spreads()
            for s in spreads:
                if 'HY' in (s.index_name or '').upper():
                    conditions["credit_stress_high"] = (s.percentile_90d or 0) > 80
                    indicator_values["hy_spread_bps"] = s.spread_bps

            # Economic indicators
            from modules.economic_indicators import IndicatorStorage
            storage = IndicatorStorage(self.db)

            # VIX
            start = datetime.utcnow().date() - timedelta(days=30)
            vix_df = storage.get_values("VIXCLS", start_date=start)
            if vix_df is not None and not vix_df.empty:
                current_vix = float(vix_df['value'].iloc[-1])
                conditions["vix_elevated"] = current_vix > 20
                indicator_values["VIXCLS"] = current_vix

            # Unemployment
            unrate_df = storage.get_values("UNRATE", start_date=datetime.utcnow().date() - timedelta(days=365))
            if unrate_df is not None and not unrate_df.empty and len(unrate_df) >= 4:
                values = unrate_df['value'].values
                current = float(values[-1])
                three_months_ago = float(values[-4]) if len(values) >= 4 else current
                conditions["unemployment_rising"] = current > three_months_ago + 0.2
                indicator_values["UNRATE"] = current

            # Fed Funds
            ff_df = storage.get_values("FEDFUNDS", start_date=datetime.utcnow().date() - timedelta(days=365))
            if ff_df is not None and not ff_df.empty and len(ff_df) >= 2:
                values = ff_df['value'].values
                current = float(values[-1])
                prior = float(values[-2])
                conditions["fed_cutting"] = current < prior - 0.1
                indicator_values["FEDFUNDS"] = current

            # CPI / Inflation
            cpi_df = storage.get_values("CPIAUCSL", start_date=datetime.utcnow().date() - timedelta(days=730))
            if cpi_df is not None and not cpi_df.empty and len(cpi_df) >= 14:
                values = cpi_df['value'].values
                current_yoy = ((values[-1] - values[-13]) / abs(values[-13])) * 100
                prior_yoy = ((values[-2] - values[-14]) / abs(values[-14])) * 100
                conditions["inflation_declining"] = current_yoy < prior_yoy - 0.1
                indicator_values["CPI_YoY"] = round(current_yoy, 2)

        except Exception as e:
            logger.error(f"Error gathering current conditions: {e}")

        return {
            "conditions": conditions,
            "indicator_values": indicator_values,
            "timestamp": get_current_time().isoformat(),
        }

    def match_episodes(self) -> Dict[str, Any]:
        """
        Match current conditions against all historical episodes.
        Returns ranked matches with similarity scores.
        """
        current = self._get_current_conditions()
        conditions = current["conditions"]
        matches = []

        for ep_id, episode in HISTORICAL_EPISODES.items():
            ep_chars = episode["characteristics"]
            matching = []
            diverging = []

            # Compare each characteristic
            for signal, current_val in conditions.items():
                if signal in ep_chars:
                    if current_val == ep_chars[signal]:
                        matching.append(signal)
                    else:
                        diverging.append(signal)

            total_signals = len(matching) + len(diverging)
            if total_signals > 0:
                score = len(matching) / total_signals
            else:
                score = 0

            match = PlaybookMatch(
                episode_id=ep_id,
                episode_name=episode["name"],
                similarity_score=score,
                matching_signals=matching,
                diverging_signals=diverging,
                what_followed=episode["what_followed"],
                period=episode["period"],
                duration_months=episode["duration_months"],
            )
            matches.append(match)

        # Sort by similarity score descending
        matches.sort(key=lambda m: m.similarity_score, reverse=True)

        return {
            "current_conditions": current,
            "matches": [m.to_dict() for m in matches],
            "best_match": matches[0].to_dict() if matches else None,
            "timestamp": get_current_time().isoformat(),
        }

    async def match_and_analyze(self) -> Dict[str, Any]:
        """Match episodes and generate AI analysis for top matches."""
        result = self.match_episodes()
        top_matches = result["matches"][:3]

        client = self._get_client()
        if client and top_matches:
            try:
                # Build context for AI analysis
                conditions = result["current_conditions"]
                match_summary = "\n".join([
                    f"{i+1}. {m['episode_name']} ({m['similarity_pct']}% match)\n"
                    f"   Matching: {', '.join(m['matching_signals'])}\n"
                    f"   Diverging: {', '.join(m['diverging_signals'])}\n"
                    f"   What followed: {m['what_followed']}"
                    for i, m in enumerate(top_matches)
                ])

                cond_str = "\n".join(f"  {k}: {v}" for k, v in conditions["conditions"].items())
                vals_str = "\n".join(f"  {k}: {v}" for k, v in conditions["indicator_values"].items())

                user_msg = f"""Current economic conditions:
{cond_str}

Key indicator values:
{vals_str}

Top historical matches:
{match_summary}

Write a 200-word analysis comparing current conditions to these historical episodes.
Focus on: (1) Which match is most instructive and why, (2) Key differences that matter,
(3) What the historical patterns suggest for the next 3-6 months, (4) Confidence level in the analogy.
Be specific with numbers and probabilities."""

                message = client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=500,
                    system="You are a senior macro strategist who specializes in historical pattern recognition. Be direct, quantitative, and honest about uncertainty.",
                    messages=[{"role": "user", "content": user_msg}]
                )

                result["ai_analysis"] = message.content[0].text
                result["tokens_used"] = message.usage.input_tokens + message.usage.output_tokens

            except Exception as e:
                logger.error(f"Playbook AI analysis error: {e}")
                result["ai_analysis"] = None

        return result
