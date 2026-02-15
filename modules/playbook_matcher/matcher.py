"""
Historical Playbook Matcher

Compares current economic conditions against major historical episodes
to identify similar patterns and provide "what followed" context.
"""

import os
import time
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


def _get_indicator_values(db: 'Session', series_id: str, limit: int = 20) -> List[float]:
    """Get recent indicator values as a list of floats (most recent first)."""
    try:
        from modules.economic_indicators import IndicatorStorage
        storage = IndicatorStorage(db)
        df = storage.get_values(series_id)
        if df.empty:
            return []
        df = df.sort_values('date', ascending=False).head(limit)
        return [float(v) for v in df['value'].tolist() if v is not None]
    except Exception as e:
        logger.debug(f"Failed to get indicator {series_id}: {e}")
        return []


# Historical episodes with signal fingerprints
HISTORICAL_EPISODES = [
    {
        "id": "gfc_2008",
        "name": "2008 Global Financial Crisis",
        "period": "Sep 2008 - Mar 2009",
        "signals": {
            "yield_curve_inverted": True,
            "vix_above_30": True,
            "credit_spreads_wide": True,
            "unemployment_rising": True,
            "fed_cutting": True,
            "inflation_falling": True,
            "equities_declining": True,
            "dollar_strengthening": True,
        },
        "what_followed": (
            "S&P 500 fell 57% peak-to-trough. Fed cut rates to zero and launched QE1. "
            "Unemployment peaked at 10%. Recovery began Q3 2009. Credit markets froze, "
            "requiring unprecedented government intervention. Markets bottomed March 2009."
        ),
    },
    {
        "id": "covid_2020",
        "name": "2020 COVID Crash",
        "period": "Feb 2020 - Apr 2020",
        "signals": {
            "yield_curve_inverted": False,
            "vix_above_30": True,
            "credit_spreads_wide": True,
            "unemployment_rising": True,
            "fed_cutting": True,
            "inflation_falling": True,
            "equities_declining": True,
            "dollar_strengthening": True,
        },
        "what_followed": (
            "Fastest 30% decline in S&P 500 history. Fed cut to zero in emergency meetings, "
            "launched unlimited QE. Unemployment spiked to 14.7%. V-shaped recovery followed "
            "with massive fiscal stimulus. Markets recovered all losses by August 2020."
        ),
    },
    {
        "id": "ltcm_1998",
        "name": "1998 LTCM / Russia Crisis",
        "period": "Aug 1998 - Oct 1998",
        "signals": {
            "yield_curve_inverted": False,
            "vix_above_30": True,
            "credit_spreads_wide": True,
            "unemployment_rising": False,
            "fed_cutting": True,
            "inflation_falling": True,
            "equities_declining": True,
            "dollar_strengthening": False,
        },
        "what_followed": (
            "LTCM bailout required Fed coordination. 3 inter-meeting rate cuts. "
            "S&P 500 fell ~20% but recovered within months. Contagion from Russia/EM "
            "was contained. Led to dot-com bubble's final leg higher into 2000."
        ),
    },
    {
        "id": "tightening_2022",
        "name": "2022 Aggressive Tightening",
        "period": "Mar 2022 - Dec 2022",
        "signals": {
            "yield_curve_inverted": True,
            "vix_above_30": True,
            "credit_spreads_wide": False,
            "unemployment_rising": False,
            "fed_cutting": False,
            "inflation_falling": False,
            "equities_declining": True,
            "dollar_strengthening": True,
        },
        "what_followed": (
            "Fed raised rates 425bps in 9 months. S&P 500 fell 25%. Bond market worst "
            "year on record. Dollar surged to 20-year highs. Inflation peaked at 9.1% "
            "and began declining. Economy avoided recession despite rate shock."
        ),
    },
    {
        "id": "slowdown_2015",
        "name": "2015-16 Global Slowdown",
        "period": "Aug 2015 - Feb 2016",
        "signals": {
            "yield_curve_inverted": False,
            "vix_above_30": False,
            "credit_spreads_wide": True,
            "unemployment_rising": False,
            "fed_cutting": False,
            "inflation_falling": True,
            "equities_declining": True,
            "dollar_strengthening": True,
        },
        "what_followed": (
            "China devaluation fears and oil crash drove 15% S&P 500 correction. "
            "Fed delayed rate hikes. Energy sector credit stress but no systemic crisis. "
            "Markets recovered by mid-2016. Fed resumed hiking December 2016."
        ),
    },
    {
        "id": "inversion_2019",
        "name": "2019 Yield Curve Inversion",
        "period": "Mar 2019 - Oct 2019",
        "signals": {
            "yield_curve_inverted": True,
            "vix_above_30": False,
            "credit_spreads_wide": False,
            "unemployment_rising": False,
            "fed_cutting": True,
            "inflation_falling": True,
            "equities_declining": False,
            "dollar_strengthening": True,
        },
        "what_followed": (
            "Yield curve inverted briefly, triggering recession fears. Fed pivoted to "
            "3 'insurance' cuts. Trade war uncertainty dominated. Equities rallied into "
            "year-end. COVID hit before recession cycle could play out naturally."
        ),
    },
]


class PlaybookMatcher:
    """Matches current conditions against historical economic episodes."""

    def __init__(self, db: Session, api_key: Optional[str] = None):
        self.db = db
        self.helper = QueryHelper(db)
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        self._client = None

    def _get_client(self):
        if not self._client and ANTHROPIC_AVAILABLE and self.api_key:
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def match(self, include_ai: bool = False) -> Dict[str, Any]:
        """Compare current conditions against all historical episodes."""
        start = time.time()

        current = self._gather_current_conditions()
        matches = []

        for episode in HISTORICAL_EPISODES:
            result = self._compute_similarity(current, episode)
            matches.append(result)

        # Sort by similarity descending
        matches.sort(key=lambda x: x["similarity_pct"], reverse=True)

        # Optional AI analysis of top matches
        ai_analysis = None
        if include_ai and matches:
            ai_analysis = self._generate_analysis(current, matches[:3])

        return {
            "current_conditions": current,
            "matches": matches,
            "top_match": matches[0] if matches else None,
            "ai_analysis": ai_analysis,
            "assessed_at": get_current_time().isoformat(),
            "elapsed_ms": round((time.time() - start) * 1000),
        }

    def _gather_current_conditions(self) -> Dict[str, Any]:
        """Gather current economic signals for comparison."""
        conditions = {
            "yield_curve_inverted": False,
            "vix_above_30": False,
            "credit_spreads_wide": False,
            "unemployment_rising": False,
            "fed_cutting": False,
            "inflation_falling": False,
            "equities_declining": False,
            "dollar_strengthening": False,
        }
        details = {}

        # Yield curve
        try:
            yc = self.helper.get_latest_yield_curve()
            if yc and yc.spread_10y2y is not None:
                conditions["yield_curve_inverted"] = yc.spread_10y2y < 0
                details["spread_10y2y"] = round(yc.spread_10y2y, 3)
        except Exception as e:
            logger.debug(f"Playbook yield check error: {e}")

        # VIX (try FRED, fall back to yfinance)
        vix_vals = _get_indicator_values(self.db, "VIXCLS", limit=3)
        if not vix_vals:
            try:
                import yfinance as yf
                import pandas as pd
                data = yf.download("^VIX", period="5d", progress=False, auto_adjust=True)
                if len(data) > 0:
                    close = data["Close"]
                    if isinstance(close, pd.DataFrame):
                        close = close.iloc[:, 0]
                    vix_vals = [float(close.iloc[-1])]
            except Exception:
                pass
        if vix_vals:
            conditions["vix_above_30"] = vix_vals[0] >= 30
            details["vix"] = round(vix_vals[0], 1)

        # Credit spreads
        try:
            spreads = self.helper.get_latest_credit_spreads()
            if spreads:
                for s in spreads:
                    current = s.spread_bps
                    avg = s.avg_90d
                    if current and avg and avg > 0:
                        if current / avg >= 1.5:
                            conditions["credit_spreads_wide"] = True
                            details["credit_ratio"] = round(current / avg, 2)
                            break
        except Exception as e:
            logger.debug(f"Playbook credit check error: {e}")

        # Unemployment trend
        unrate_vals = _get_indicator_values(self.db, "UNRATE", limit=5)
        if len(unrate_vals) >= 3:
            conditions["unemployment_rising"] = unrate_vals[0] > unrate_vals[2]
            details["unemployment"] = round(unrate_vals[0], 1)

        # Fed funds direction
        ff_vals = _get_indicator_values(self.db, "FEDFUNDS", limit=3)
        if len(ff_vals) >= 2:
            conditions["fed_cutting"] = ff_vals[0] < ff_vals[1]
            details["fed_funds"] = round(ff_vals[0], 2)

        # Inflation trend
        cpi_vals = _get_indicator_values(self.db, "CPIAUCSL", limit=20)
        if len(cpi_vals) >= 13:
            yoy_current = ((cpi_vals[0] - cpi_vals[12]) / cpi_vals[12]) * 100
            details["cpi_yoy"] = round(yoy_current, 1)
            if len(cpi_vals) >= 16:
                yoy_3m_ago = ((cpi_vals[3] - cpi_vals[15]) / cpi_vals[15]) * 100
                conditions["inflation_falling"] = yoy_current < yoy_3m_ago

        # Equities trend (S&P 500 via yfinance)
        try:
            import yfinance as yf
            import pandas as pd
            sp_data = yf.download("^GSPC", period="3mo", progress=False, auto_adjust=True)
            if len(sp_data) >= 2:
                close = sp_data["Close"]
                if isinstance(close, pd.DataFrame):
                    close = close.iloc[:, 0]
                latest = float(close.iloc[-1])
                start = float(close.iloc[0])
                pct_change = ((latest - start) / start) * 100
                conditions["equities_declining"] = pct_change < -5
                details["sp500_3mo_change"] = round(pct_change, 1)
        except Exception as e:
            logger.debug(f"Playbook equities check error: {e}")

        # Dollar strength (via EUR/USD from FX data)
        try:
            fx_rates = self.helper.get_latest_fx_rates()
            if fx_rates:
                for rate in fx_rates:
                    if rate.pair == "EUR/USD":
                        change_1w = rate.change_1w
                        if change_1w is not None:
                            conditions["dollar_strengthening"] = change_1w < -0.5
                            details["eurusd_1w_change"] = round(change_1w, 2)
                        break
        except Exception as e:
            logger.debug(f"Playbook dollar check error: {e}")

        return {"signals": conditions, "details": details}

    def _compute_similarity(self, current: Dict, episode: Dict) -> Dict[str, Any]:
        """Compute similarity score between current conditions and a historical episode."""
        current_signals = current["signals"]
        episode_signals = episode["signals"]

        matching = []
        diverging = []

        for signal, historical_value in episode_signals.items():
            current_value = current_signals.get(signal)
            if current_value == historical_value:
                matching.append(signal)
            else:
                diverging.append(signal)

        total = len(episode_signals)
        similarity = (len(matching) / total * 100) if total > 0 else 0

        return {
            "episode_id": episode["id"],
            "episode_name": episode["name"],
            "period": episode["period"],
            "similarity_pct": round(similarity, 1),
            "matching_signals": matching,
            "diverging_signals": diverging,
            "matching_count": len(matching),
            "total_signals": total,
            "what_followed": episode["what_followed"],
        }

    def _generate_analysis(self, current: Dict, top_matches: List[Dict]) -> Optional[str]:
        """Generate AI analysis of top historical matches."""
        client = self._get_client()
        if not client:
            return None

        try:
            matches_text = "\n".join(
                f"- {m['episode_name']} ({m['period']}): {m['similarity_pct']}% match. "
                f"Matching: {', '.join(m['matching_signals'])}. "
                f"Diverging: {', '.join(m['diverging_signals'])}."
                for m in top_matches
            )

            prompt = (
                f"Current economic conditions:\n{current['details']}\n\n"
                f"Top historical matches:\n{matches_text}\n\n"
                f"In 3-4 sentences, analyze what these historical parallels suggest for "
                f"the current environment. Note important differences from the closest match. "
                f"Be specific about actionable implications."
            )

            message = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
                system="You are a senior macro strategist. Provide concise, actionable analysis.",
            )
            return message.content[0].text
        except Exception as e:
            logger.warning(f"Playbook AI analysis failed: {e}")
            return None
