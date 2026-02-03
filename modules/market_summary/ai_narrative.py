"""
AI-Powered Market Narrative Generator

Uses Claude API to generate institutional-grade market analysis narratives.
Pre-computes analytics (trends, percentiles, regime classification) so the AI
focuses on interpretation rather than arithmetic.
"""

import os
import math
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import Counter, defaultdict
from sqlalchemy.orm import Session
from loguru import logger

# Ensure .env is loaded from project root
from pathlib import Path
from dotenv import load_dotenv
project_root = Path(__file__).parent.parent.parent
env_path = project_root / '.env'
load_dotenv(env_path)

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("Anthropic SDK not installed. AI narrative generation unavailable.")

from modules.utils.timezone import get_current_time


# DM vs EM currency classification
DM_CURRENCIES = {'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'NZD', 'CHF'}
EM_CURRENCIES = {'MXN', 'BRL', 'ARS', 'TWD', 'ZAR', 'TRY', 'INR', 'CNY'}


SYSTEM_PROMPT = """You are an expert economic analyst writing a pre-digested market briefing for institutional decision-makers.

**Critical Rules:**
- You are receiving a PRE-DIGESTED briefing where all arithmetic is already computed. TRUST the pre-computed numbers (trends, changes). Do NOT recalculate.
- Items flagged as SUSPECT in Data Quality Alerts are data errors. IGNORE them entirely — do not mention them.
- The ANALYST NOTES section contains rule-based observations. You may agree, disagree, or extend them.
- Many indicators have publication lags. Reference the CURRENT date shown, not the data's reference period.

**Tone & Voice:**
- Professional yet accessible, maintaining technical accuracy
- Measured and analytical, never alarmist or sensational
- Direct and substantive, with interpretive insight beyond reporting numbers
- Use phrases that crystallize patterns into memorable frameworks

**Analytical Approach:**
- Ground observations in the trend data and changes provided
- Move beyond headline figures to underlying dynamics
- Apply constraint-based reasoning about institutional and political limits
- Identify what the data obscures as much as what it reveals
- Connect macro trends to real-world business implications

**Structure:**
- Write in flowing prose paragraphs, NOT bullet points or sections
- Lead with the most significant developments
- Layer analysis from immediate data to forward-looking implications

**Coverage Areas:**
1. Labor market conditions and employment dynamics
2. Inflation trends and Fed policy implications
3. Growth indicators and economic momentum
4. Market conditions (yields, credit, FX)
5. Forward-looking assessment

Write a single cohesive narrative of 400-600 words. No headers, bullet points, or section breaks."""


class AIMarketNarrative:
    """
    Generates sophisticated market narratives using Claude API.
    Pre-computes analytics layer between data gathering and prompt formatting.
    """

    def __init__(self, db: Session, api_key: Optional[str] = None):
        self.db = db
        load_dotenv(env_path, override=True)
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        self._client = None
        self._last_narrative: Optional[Dict[str, Any]] = None

    def is_available(self) -> bool:
        return ANTHROPIC_AVAILABLE and bool(self.api_key)

    def _get_client(self):
        if not self._client and self.is_available():
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    # ──────────────────────────────────────────────
    # PHASE 1: Data Gathering (enriched raw data)
    # ──────────────────────────────────────────────

    def _gather_context(self) -> Dict[str, Any]:
        """Gather all relevant data for narrative generation."""
        return {
            "timestamp": get_current_time().isoformat(),
            "indicators": self._get_economic_indicators(),
            "yields": self._get_yield_data(),
            "fx": self._get_fx_data(),
            "credit": self._get_credit_data(),
            "news": self._get_recent_news(),
            "calendar": self._get_upcoming_releases()
        }

    def _get_economic_indicators(self) -> Dict[str, Any]:
        """Get key economic indicators using DataTransformer for proper calculations."""
        try:
            from modules.economic_indicators import IndicatorStorage
            from modules.economic_indicators.transformer import DataTransformer

            storage = IndicatorStorage(self.db)
            transformer = DataTransformer()

            key_series = {
                "CPIAUCSL": "CPI (Consumer Price Index)",
                "PAYEMS": "Nonfarm Payrolls",
                "UNRATE": "Unemployment Rate",
                "FEDFUNDS": "Fed Funds Rate",
                "GDP": "Real GDP",
                "RSXFS": "Retail Sales (ex Food Services)",
                "INDPRO": "Industrial Production",
                "UMCSENT": "Consumer Sentiment (U of M)",
                "HOUST": "Housing Starts",
                "ICSA": "Initial Jobless Claims"
            }

            # Series where absolute level change is more meaningful
            level_change_series = {'FEDFUNDS', 'UNRATE', 'UMCSENT', 'PAYEMS'}

            indicators = {}
            for series_id, name in key_series.items():
                try:
                    indicator = storage.get_indicator(series_id)
                    if not indicator:
                        continue

                    freq = (indicator.frequency or 'monthly').lower()
                    # 5-year lookback for percentile calculations
                    start = datetime.utcnow().date() - timedelta(days=1825)
                    df = storage.get_values(series_id, start_date=start)

                    if df is None or df.empty:
                        continue

                    # Use DataTransformer for standardized calculations
                    latest_data = transformer.get_latest_with_changes(df, freq)
                    if not latest_data:
                        continue

                    use_level = series_id in level_change_series

                    # Determine change label
                    if freq == 'weekly':
                        change_period = 'WoW'
                    elif freq == 'quarterly':
                        change_period = 'QoQ'
                    else:
                        change_period = 'MoM'

                    entry = {
                        "name": name,
                        "value": latest_data['value'],
                        "date": latest_data['date'],
                        "units": indicator.units,
                        "frequency": freq,
                        "change_period": change_period,
                        # Store raw df for analytics phase (stripped before formatting)
                        "_df": df,
                    }

                    if use_level:
                        entry["prior_level_change"] = latest_data.get('mom_change')
                        if series_id == 'PAYEMS':
                            entry["jobs_change_thousands"] = latest_data.get('mom_change')
                    else:
                        entry["prior_change_pct"] = latest_data.get('mom_percent')
                        entry["yoy_change_pct"] = latest_data.get('yoy_percent')

                    indicators[series_id] = entry

                except Exception as e:
                    logger.debug(f"Could not get {series_id}: {e}")

            return indicators
        except Exception as e:
            logger.error(f"Error gathering indicators: {e}")
            return {}

    def _get_yield_data(self) -> Dict[str, Any]:
        """Get full yield curve with all tenors, spreads, TIPS, and history."""
        try:
            from modules.data_storage.schema import YieldCurve
            from modules.data_storage.queries import QueryHelper

            helper = QueryHelper(self.db)
            curve = self.db.query(YieldCurve).order_by(YieldCurve.timestamp.desc()).first()

            if not curve:
                return {}

            # Full curve - all 9 tenors
            curve_data = {}
            for tenor in ['1M', '3M', '6M', '1Y', '2Y', '5Y', '10Y', '20Y', '30Y']:
                attr = f'tenor_{tenor.lower()}'
                val = getattr(curve, attr, None)
                if val is not None:
                    curve_data[tenor] = val

            # Pre-computed spreads from schema
            spreads = {}
            if curve.spread_10y2y is not None:
                spreads['10y2y'] = curve.spread_10y2y
            if curve.spread_10y3m is not None:
                spreads['10y3m'] = curve.spread_10y3m
            if curve.spread_30y10y is not None:
                spreads['30y10y'] = curve.spread_30y10y

            # TIPS real yields
            tips = {}
            if curve.tips_5y is not None:
                tips['5y'] = curve.tips_5y
            if curve.tips_10y is not None:
                tips['10y'] = curve.tips_10y

            # Fetch history for WoW/MoM change computation
            history = []
            try:
                history = helper.get_yield_curve_history(days=30)
            except Exception:
                pass

            return {
                "curve": curve_data,
                "spreads": spreads,
                "tips": tips,
                "timestamp": curve.timestamp.isoformat() if curve.timestamp else None,
                "_history": history,  # consumed by analytics, stripped before formatting
            }
        except Exception as e:
            logger.error(f"Error getting yields: {e}")
            return {}

    def _get_fx_data(self) -> Dict[str, Any]:
        """Get FX rates with all change columns."""
        try:
            from modules.data_storage.queries import QueryHelper
            helper = QueryHelper(self.db)
            rates = helper.get_latest_fx_rates()

            fx_data = {}
            for rate in rates:
                fx_data[rate.pair] = {
                    "rate": rate.rate,
                    "change_1h": rate.change_1h,
                    "change_24h": rate.change_24h,
                    "change_1w": rate.change_1w,
                    "change_ytd": rate.change_ytd,
                }
            return fx_data
        except Exception as e:
            logger.error(f"Error getting FX: {e}")
            return {}

    def _get_credit_data(self) -> Dict[str, Any]:
        """Get credit spreads with all pre-computed analytics from schema."""
        try:
            from modules.data_storage.queries import QueryHelper
            helper = QueryHelper(self.db)
            spreads = helper.get_latest_credit_spreads()

            credit_data = {}
            for spread in spreads:
                credit_data[spread.index_name] = {
                    "spread_bps": spread.spread_bps,
                    "change_1d": spread.change_1d,
                    "change_1w": spread.change_1w,
                    "avg_30d": spread.avg_30d,
                    "avg_90d": spread.avg_90d,
                }
            return credit_data
        except Exception as e:
            logger.error(f"Error getting credit: {e}")
            return {}

    def _get_recent_news(self) -> List[Dict[str, Any]]:
        """Get recent news with category and entity data.

        Uses two queries to ensure important news isn't crowded out:
        1. Latest 30 articles by recency
        2. Recent CENTRAL_BANK / HIGH+ severity articles from past 3 days
        """
        try:
            from modules.data_storage.schema import NewsArticle
            from sqlalchemy import or_

            # Query 1: Most recent articles
            recent = self.db.query(NewsArticle).order_by(
                NewsArticle.published_at.desc()
            ).limit(30).all()

            # Query 2: Central bank / rate decision articles from past 3 days
            three_days_ago = datetime.utcnow() - timedelta(days=3)
            central_bank = self.db.query(NewsArticle).filter(
                NewsArticle.published_at >= three_days_ago,
                or_(
                    NewsArticle.category.in_(['CENTRAL_BANK', 'RATE_DECISION']),
                    NewsArticle.headline.ilike('%fomc%'),
                    NewsArticle.headline.ilike('%rate decision%'),
                    NewsArticle.headline.ilike('%rate cut%'),
                    NewsArticle.headline.ilike('%rate hike%'),
                    NewsArticle.headline.ilike('%holds rates%'),
                    NewsArticle.headline.ilike('%fed holds%'),
                    NewsArticle.headline.ilike('%interest rate announcement%'),
                )
            ).order_by(NewsArticle.published_at.desc()).limit(10).all()

            # Query 3: HIGH/CRITICAL severity articles from past 3 days
            high_sev = self.db.query(NewsArticle).filter(
                NewsArticle.published_at >= three_days_ago,
                NewsArticle.severity.in_(['CRITICAL', 'HIGH']),
            ).order_by(NewsArticle.published_at.desc()).limit(10).all()

            priority = central_bank + high_sev

            # Merge and deduplicate by id
            seen_ids = set()
            all_articles = []
            for a in priority + recent:  # priority first so they're included
                if a.id not in seen_ids:
                    seen_ids.add(a.id)
                    all_articles.append(a)

            def _article_to_dict(a):
                return {
                    "title": a.headline,
                    "source": a.source,
                    "published": a.published_at.strftime('%Y-%m-%d %H:%M') if a.published_at else None,
                    "severity": a.severity,
                    "category": getattr(a, 'category', None),
                    "summary": getattr(a, 'summary', None),
                    "leader_mentions": getattr(a, 'leader_mentions', None) or [],
                    "institutions": getattr(a, 'institutions', None) or [],
                    "relevance_score": getattr(a, 'relevance_score', None),
                }

            return [_article_to_dict(a) for a in all_articles]
        except Exception as e:
            logger.error(f"Error getting news: {e}")
            return []

    def _get_upcoming_releases(self) -> List[Dict[str, Any]]:
        """Get upcoming economic releases."""
        try:
            from modules.economic_calendar import EconomicCalendar
            calendar = EconomicCalendar()
            releases = calendar.get_upcoming_releases(days_ahead=7)

            return [
                {
                    "name": r.name,
                    "date": r.release_date.strftime('%Y-%m-%d') if r.release_date else None,
                    "importance": r.importance.value
                }
                for r in releases[:5]
            ]
        except Exception as e:
            logger.error(f"Error getting calendar: {e}")
            return []

    # ──────────────────────────────────────────────
    # PHASE 2: Analytics Computation
    # ──────────────────────────────────────────────

    def _compute_analytics(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Pre-compute all analytics so the AI focuses on interpretation."""
        analytics = {}

        analytics["indicators"] = self._compute_indicator_analytics(context.get("indicators", {}))
        analytics["yields"] = self._compute_yield_analytics(context.get("yields", {}))
        analytics["fx"] = self._compute_fx_analytics(context.get("fx", {}))
        analytics["credit"] = self._compute_credit_analytics(context.get("credit", {}))
        analytics["news"] = self._compute_news_analytics(context.get("news", []))
        analytics["regime"] = self._compute_market_regime(context, analytics)

        # Strip private data before formatting
        self._strip_private_data(context)

        return analytics

    def _compute_indicator_analytics(self, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """Compute trend and quality for each indicator."""
        import numpy as np

        result = {}
        for series_id, data in indicators.items():
            entry = {"trend": None, "quality": "OK"}

            df = data.get("_df")
            if df is None or df.empty or len(df) < 3:
                result[series_id] = entry
                continue

            values = df['value'].dropna().values
            current = values[-1]

            # 3-period trend direction (MA slope)
            try:
                if len(values) >= 6:
                    ma3 = np.convolve(values, np.ones(3)/3, mode='valid')
                    if len(ma3) >= 3:
                        slope = ma3[-1] - ma3[-3]
                        magnitude = abs(current) if current != 0 else 1
                        pct_slope = (slope / magnitude) * 100
                        if pct_slope > 0.5:
                            entry["trend"] = "ACCELERATING"
                        elif pct_slope < -0.5:
                            entry["trend"] = "DECELERATING"
                        else:
                            entry["trend"] = "STABLE"
            except Exception:
                pass

            # Data quality check (z-score)
            try:
                mean = float(np.mean(values))
                std = float(np.std(values))
                if std > 0:
                    z = abs(current - mean) / std
                    if z > 4:
                        entry["quality"] = "SUSPECT"
            except Exception:
                pass

            result[series_id] = entry

        # Derived metrics
        derived = {}

        # Real Fed Funds Rate
        try:
            ff = indicators.get("FEDFUNDS", {})
            cpi = indicators.get("CPIAUCSL", {})
            if ff.get("value") is not None and cpi.get("_df") is not None:
                cpi_yoy = result.get("CPIAUCSL", {}).get("_cpi_yoy")
                # Calculate CPI YoY from the data
                cpi_df = cpi.get("_df")
                if cpi_df is not None and len(cpi_df) >= 13:
                    cpi_vals = cpi_df['value'].values
                    cpi_yoy_val = ((cpi_vals[-1] - cpi_vals[-13]) / abs(cpi_vals[-13])) * 100
                    derived["real_fed_funds"] = round(ff["value"] - cpi_yoy_val, 2)
                    derived["cpi_yoy"] = round(cpi_yoy_val, 2)
        except Exception:
            pass

        # Sahm Rule
        try:
            unrate = indicators.get("UNRATE", {})
            unrate_df = unrate.get("_df")
            if unrate_df is not None and len(unrate_df) >= 15:
                ur_vals = unrate_df['value'].values
                # 3-month moving average
                ma3 = np.convolve(ur_vals, np.ones(3)/3, mode='valid')
                if len(ma3) >= 13:
                    current_ma3 = ma3[-1]
                    min_ma3_prior_12 = float(np.min(ma3[-13:-1]))
                    sahm = round(float(current_ma3 - min_ma3_prior_12), 2)
                    derived["sahm_rule"] = sahm
                    derived["sahm_triggered"] = sahm >= 0.50
        except Exception:
            pass

        result["_derived"] = derived
        return result

    def _compute_yield_analytics(self, yields_data: Dict[str, Any]) -> Dict[str, Any]:
        """Compute yield curve shape, changes, and breakevens."""
        result = {
            "shape": None,
            "wow_changes": {},
            "mom_changes": {},
            "steepening_trend": None,
            "breakevens": {},
        }

        curve = yields_data.get("curve", {})
        if not curve:
            return result

        # Curve shape classification
        try:
            from modules.risk_detector.yield_rules import analyze_curve_shape
            shape_data = analyze_curve_shape(curve)
            result["shape"] = shape_data.get("classification", "UNKNOWN")
            result["inversions"] = shape_data.get("inversions", [])
        except Exception as e:
            logger.debug(f"Could not analyze curve shape: {e}")

        # WoW and MoM changes from history
        history = yields_data.get("_history", [])
        if history:
            try:
                # Find curve from ~7 days ago and ~30 days ago
                now = datetime.utcnow()
                week_ago_target = now - timedelta(days=7)
                month_ago_target = now - timedelta(days=30)

                week_ago_curve = None
                month_ago_curve = None
                for h in history:
                    ts = h.timestamp if hasattr(h, 'timestamp') else None
                    if ts is None:
                        continue
                    diff_days = (now - ts).total_seconds() / 86400
                    if 5 <= diff_days <= 10 and week_ago_curve is None:
                        week_ago_curve = h
                    if 25 <= diff_days <= 35 and month_ago_curve is None:
                        month_ago_curve = h

                for tenor in ['1M', '3M', '6M', '1Y', '2Y', '5Y', '10Y', '20Y', '30Y']:
                    attr = f'tenor_{tenor.lower()}'
                    current_val = curve.get(tenor)
                    if current_val is None:
                        continue

                    if week_ago_curve:
                        prev = getattr(week_ago_curve, attr, None)
                        if prev is not None:
                            result["wow_changes"][tenor] = round((current_val - prev) * 100, 1)  # bps

                    if month_ago_curve:
                        prev = getattr(month_ago_curve, attr, None)
                        if prev is not None:
                            result["mom_changes"][tenor] = round((current_val - prev) * 100, 1)  # bps

                # Steepening/flattening trend
                spreads = yields_data.get("spreads", {})
                current_10y2y = spreads.get("10y2y")
                if current_10y2y is not None and week_ago_curve:
                    prev_10y = getattr(week_ago_curve, 'tenor_10y', None)
                    prev_2y = getattr(week_ago_curve, 'tenor_2y', None)
                    if prev_10y is not None and prev_2y is not None:
                        prev_spread = prev_10y - prev_2y
                        spread_change = current_10y2y - prev_spread
                        if spread_change > 0.05:
                            result["steepening_trend"] = "STEEPENING"
                        elif spread_change < -0.05:
                            result["steepening_trend"] = "FLATTENING"
                        else:
                            result["steepening_trend"] = "STABLE"
                        result["spread_wow_change_bps"] = round(spread_change * 100, 1)

            except Exception as e:
                logger.debug(f"Could not compute yield changes: {e}")

        # Breakeven inflation
        tips = yields_data.get("tips", {})
        try:
            if tips.get("10y") is not None and curve.get("10Y") is not None:
                result["breakevens"]["10y"] = round(curve["10Y"] - tips["10y"], 2)
            if tips.get("5y") is not None and curve.get("5Y") is not None:
                result["breakevens"]["5y"] = round(curve["5Y"] - tips["5y"], 2)
        except Exception:
            pass

        return result

    def _compute_fx_analytics(self, fx_data: Dict[str, Any]) -> Dict[str, Any]:
        """Classify FX pairs, flag bad data, compute DM/EM averages."""
        result = {
            "dm_pairs": {},
            "em_pairs": {},
            "other_pairs": {},
            "quality_flags": {},
            "dm_avg_24h": None,
            "em_avg_24h": None,
            "usd_direction": None,
        }

        dm_changes = []
        em_changes = []

        for pair, data in fx_data.items():
            # Extract the foreign currency from pair (e.g., "USD/JPY" → "JPY")
            parts = pair.split('/')
            foreign = parts[1] if len(parts) == 2 else pair

            # Data quality check
            change_24h = data.get("change_24h")
            if change_24h is not None and abs(change_24h) > 5.0:
                result["quality_flags"][pair] = "SUSPECT"
            else:
                result["quality_flags"][pair] = "OK"

            # Classify
            if foreign in DM_CURRENCIES:
                result["dm_pairs"][pair] = data
                if change_24h is not None and result["quality_flags"][pair] == "OK":
                    dm_changes.append(change_24h)
            elif foreign in EM_CURRENCIES:
                result["em_pairs"][pair] = data
                if change_24h is not None and result["quality_flags"][pair] == "OK":
                    em_changes.append(change_24h)
            else:
                result["other_pairs"][pair] = data

        # Average moves
        if dm_changes:
            avg = sum(dm_changes) / len(dm_changes)
            result["dm_avg_24h"] = round(avg, 2)
            # Positive change_24h in USD/XXX = USD weakened
            if avg > 0.1:
                result["usd_direction"] = "WEAKENING"
            elif avg < -0.1:
                result["usd_direction"] = "STRENGTHENING"
            else:
                result["usd_direction"] = "STABLE"

        if em_changes:
            result["em_avg_24h"] = round(sum(em_changes) / len(em_changes), 2)

        return result

    def _compute_credit_analytics(self, credit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Compute credit stress assessment and spread context."""
        result = {
            "stress_level": "NORMAL",
            "quality_flags": {},
            "vs_avg": {},
        }

        # Stress assessment via risk detector
        try:
            from modules.risk_detector.credit_rules import assess_credit_conditions
            assessment = assess_credit_conditions(credit_data)
            result["stress_level"] = assessment.get("stress_level", "NORMAL")
            result["ig_status"] = assessment.get("ig_status", "NORMAL")
            result["hy_status"] = assessment.get("hy_status", "NORMAL")
        except Exception:
            pass

        # Spread vs average + data quality
        for index_name, data in credit_data.items():
            spread = data.get("spread_bps")
            avg_90d = data.get("avg_90d")

            # Validate ranges
            is_hy = 'HY' in index_name.upper() or 'HIGH' in index_name.upper()
            if spread is not None:
                if is_hy and spread < 200:
                    result["quality_flags"][index_name] = "SUSPECT_LOW"
                elif not is_hy and spread < 30:
                    result["quality_flags"][index_name] = "SUSPECT_LOW"
                else:
                    result["quality_flags"][index_name] = "OK"

            # Vs 90-day average
            if spread is not None and avg_90d is not None and avg_90d > 0:
                result["vs_avg"][index_name] = round(spread - avg_90d, 1)

        return result

    def _compute_news_analytics(self, news_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate news by category, severity, and entities. Extract priority headlines."""
        result = {
            "severity_counts": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
            "by_category": defaultdict(int),
            "top_leaders": [],
            "top_institutions": [],
            "priority_headlines": [],
            "total": len(news_list),
        }

        all_leaders = []
        all_institutions = []

        # Categories that indicate market-moving events
        priority_categories = {
            'RATE_DECISION', 'CENTRAL_BANK', 'SANCTIONS', 'TRADE_POLICY',
            'MARKET_MOVE', 'DEBT_CREDIT',
        }

        for article in news_list:
            sev = article.get("severity") or "LOW"
            if sev in result["severity_counts"]:
                result["severity_counts"][sev] += 1

            cat = article.get("category") or "OTHER"
            result["by_category"][cat] += 1

            leaders = article.get("leader_mentions")
            if leaders and isinstance(leaders, list):
                all_leaders.extend(leaders)

            institutions = article.get("institutions")
            if institutions and isinstance(institutions, list):
                all_institutions.extend(institutions)

            # Extract priority headlines: CRITICAL/HIGH severity, or key categories,
            # or headlines containing rate-decision language
            is_priority = False
            if sev in ('CRITICAL', 'HIGH'):
                is_priority = True
            elif cat in priority_categories:
                is_priority = True
            else:
                # Check headline text for rate decision / central bank keywords
                title_lower = (article.get("title") or "").lower()
                summary_lower = (article.get("summary") or "").lower()
                combined = title_lower + " " + summary_lower
                rate_keywords = [
                    'rate cut', 'rate hike', 'cuts rates', 'raises rates',
                    'holds rates', 'fed holds', 'basis points', 'bps',
                    'fomc', 'rate decision', 'monetary policy',
                    'fed ', 'federal reserve', 'fomc statement',
                    'interest rate announcement', 'policy rate',
                    'dovish', 'hawkish', 'taper', 'quantitative',
                ]
                if any(kw in combined for kw in rate_keywords):
                    is_priority = True

            if is_priority:
                result["priority_headlines"].append(article)

        result["top_leaders"] = Counter(all_leaders).most_common(5)
        result["top_institutions"] = Counter(all_institutions).most_common(5)
        result["by_category"] = dict(result["by_category"])

        # Sort priority headlines: FOMC/rate decisions first, then economic, then other
        def _priority_sort_key(article):
            cat = (article.get("category") or "").upper()
            title = (article.get("title") or "").lower()
            summary = (article.get("summary") or "").lower()
            combined = title + " " + summary

            # Tier 0: FOMC / rate decisions (always first)
            fomc_keywords = ['fomc', 'rate decision', 'rate cut', 'rate hike',
                             'fed holds', 'fed cuts', 'fed raises', 'holds rates',
                             'interest rate announcement']
            if any(kw in combined for kw in fomc_keywords):
                tier = 0
            # Tier 1: Central bank / economic
            elif cat in ('CENTRAL_BANK', 'RATE_DECISION', 'ECONOMIC_DATA', 'ECON',
                         'MARKET_MOVE', 'CREDIT', 'DEBT_CREDIT', 'FX', 'CURRENCY'):
                tier = 1
            # Tier 1 also: headlines with economic keywords regardless of category
            elif any(kw in combined for kw in ['federal reserve', 'fed ', 'treasury',
                                                'inflation', 'gdp', 'payroll', 'jobs report',
                                                'trade balance', 'oil price', 'gold ']):
                tier = 1
            # Tier 2: Everything else
            else:
                tier = 2

            relevance = article.get("relevance_score") or 0
            return (tier, -relevance)

        result["priority_headlines"].sort(key=_priority_sort_key)

        return result

    def _compute_market_regime(self, context: Dict[str, Any], analytics: Dict[str, Any]) -> Dict[str, Any]:
        """Composite market regime assessment from all signals."""
        signals = {}

        # Yield curve inverted?
        yield_analytics = analytics.get("yields", {})
        shape = yield_analytics.get("shape", "")
        signals["curve_inverted"] = "INVERTED" in str(shape).upper()

        # Credit stressed?
        credit_analytics = analytics.get("credit", {})
        signals["credit_stressed"] = credit_analytics.get("stress_level") in ("ELEVATED", "HIGH")

        # Unemployment rising? (Sahm Rule)
        ind_analytics = analytics.get("indicators", {})
        derived = ind_analytics.get("_derived", {})
        sahm = derived.get("sahm_rule")
        signals["unemployment_rising"] = sahm is not None and sahm > 0.30

        # Inflation above target?
        cpi_yoy = derived.get("cpi_yoy")
        signals["inflation_above_target"] = cpi_yoy is not None and cpi_yoy > 3.0

        # Composite
        negative_count = sum(1 for v in signals.values() if v)
        if negative_count >= 3:
            regime = "CRISIS"
        elif negative_count >= 2:
            regime = "RISK_OFF"
        elif negative_count >= 1:
            regime = "CAUTIOUS"
        else:
            regime = "RISK_ON"

        return {
            "regime": regime,
            "signals": signals,
            "sahm_rule": sahm,
            "cpi_yoy": cpi_yoy,
            "real_fed_funds": derived.get("real_fed_funds"),
        }

    def _strip_private_data(self, context: Dict[str, Any]):
        """Remove internal DataFrames and history objects before formatting."""
        for series_id, data in context.get("indicators", {}).items():
            data.pop("_df", None)
        yields = context.get("yields", {})
        yields.pop("_history", None)

    # ──────────────────────────────────────────────
    # PHASE 3: Prompt Formatting (pre-digested briefing)
    # ──────────────────────────────────────────────

    def _format_context_for_prompt(self, context: Dict[str, Any], analytics: Dict[str, Any]) -> str:
        """Format gathered data + analytics into a pre-digested briefing."""
        lines = []
        regime = analytics.get("regime", {})

        lines.append("=== PRE-DIGESTED MARKET BRIEFING ===")
        lines.append(f"Generated: {context['timestamp']}")
        lines.append(f"Market Regime: {regime.get('regime', 'UNKNOWN')}")
        lines.append("")

        # ── Data Quality Alerts ──
        quality_issues = []
        fx_analytics = analytics.get("fx", {})
        for pair, flag in fx_analytics.get("quality_flags", {}).items():
            if flag == "SUSPECT":
                fx = context.get("fx", {}).get(pair, {})
                quality_issues.append(f"- {pair}: 24h change of {fx.get('change_24h', '?')}% flagged as SUSPECT (likely data error)")

        credit_analytics = analytics.get("credit", {})
        for idx, flag in credit_analytics.get("quality_flags", {}).items():
            if "SUSPECT" in str(flag):
                quality_issues.append(f"- {idx}: spread flagged as {flag} (outside normal range)")

        ind_analytics = analytics.get("indicators", {})
        for sid, ind_a in ind_analytics.items():
            if sid.startswith("_"):
                continue
            if isinstance(ind_a, dict) and ind_a.get("quality") == "SUSPECT":
                quality_issues.append(f"- {context['indicators'].get(sid, {}).get('name', sid)}: value flagged as SUSPECT (>4 std devs from 5Y mean)")

        lines.append("=== DATA QUALITY ALERTS ===")
        if quality_issues:
            lines.extend(quality_issues)
        else:
            lines.append("No data quality issues detected.")
        lines.append("")

        # ── Economic Indicators ──
        lines.append("=== ECONOMIC INDICATORS ===")
        for series_id, data in context.get("indicators", {}).items():
            ind_a = ind_analytics.get(series_id, {})
            if not isinstance(ind_a, dict):
                continue

            change_period = data.get("change_period", "MoM")
            val = data.get("value")
            if val is None:
                continue

            # Build value string
            val_str = f"{val:.2f}"
            units = data.get("units") or ""
            freq = data.get("frequency", "")

            label_line = f"{data['name']}: {val_str} ({units}, {freq}) as of {data.get('date', '?')}"
            # Add data lag caveat for FEDFUNDS
            if series_id == 'FEDFUNDS':
                label_line += "  [NOTE: monthly average — check news for recent rate decisions]"
            lines.append(label_line)

            # Change info
            parts = []
            if data.get("jobs_change_thousands") is not None:
                parts.append(f"{change_period} change: {data['jobs_change_thousands']:+.0f}K jobs")
            elif data.get("prior_level_change") is not None:
                parts.append(f"Change from prior: {data['prior_level_change']:+.2f}")
            elif data.get("prior_change_pct") is not None:
                parts.append(f"{change_period}: {data['prior_change_pct']:+.2f}%")

            if data.get("yoy_change_pct") is not None:
                parts.append(f"YoY: {data['yoy_change_pct']:+.2f}%")

            trend = ind_a.get("trend")
            quality = ind_a.get("quality", "OK")

            if trend:
                parts.append(f"3M Trend: {trend}")
            if quality != "OK":
                parts.append(f"Quality: {quality}")

            if parts:
                lines.append(f"  {' | '.join(parts)}")
            lines.append("")

        # Derived metrics
        derived = ind_analytics.get("_derived", {})
        if derived:
            lines.append("Derived Metrics:")
            if derived.get("real_fed_funds") is not None:
                ff_val = context.get("indicators", {}).get("FEDFUNDS", {}).get("value", "?")
                lines.append(f"  Real Fed Funds Rate: {derived['real_fed_funds']:+.2f}% (FEDFUNDS {ff_val}% - CPI YoY {derived.get('cpi_yoy', '?')}%)")
            if derived.get("sahm_rule") is not None:
                status = "TRIGGERED" if derived.get("sahm_triggered") else "below 0.50 trigger"
                lines.append(f"  Sahm Rule: {derived['sahm_rule']:.2f} ({status})")
            lines.append("")

        # ── Treasury Yields ──
        yields = context.get("yields", {})
        yield_a = analytics.get("yields", {})
        curve = yields.get("curve", {})
        if curve:
            lines.append("=== TREASURY YIELDS ===")
            lines.append("Current Curve:")
            short = " | ".join(f"{t}: {curve[t]:.2f}%" for t in ['1M', '3M', '6M', '1Y'] if t in curve)
            long = " | ".join(f"{t}: {curve[t]:.2f}%" for t in ['2Y', '5Y', '10Y', '20Y', '30Y'] if t in curve)
            if short:
                lines.append(f"  {short}")
            if long:
                lines.append(f"  {long}")

            # Spreads
            spreads = yields.get("spreads", {})
            if spreads:
                spread_parts = []
                for key, val in spreads.items():
                    bps = val * 100
                    label = key.upper().replace('Y', 'Y-').rstrip('-')
                    spread_parts.append(f"{label}: {bps:+.0f} bps")
                lines.append(f"Key Spreads: {', '.join(spread_parts)}")

            # Curve shape
            shape = yield_a.get("shape")
            if shape:
                lines.append(f"Curve Shape: {shape}")

            # Steepening trend
            trend = yield_a.get("steepening_trend")
            wow_spread = yield_a.get("spread_wow_change_bps")
            if trend and wow_spread is not None:
                lines.append(f"10Y-2Y Trend: {trend} ({wow_spread:+.1f} bps WoW)")

            # WoW changes
            wow = yield_a.get("wow_changes", {})
            if wow:
                wow_str = ", ".join(f"{t}: {v:+.0f}" for t, v in wow.items())
                lines.append(f"WoW Changes (bps): {wow_str}")

            # Breakevens
            be = yield_a.get("breakevens", {})
            if be:
                be_str = ", ".join(f"{t}: {v:.2f}%" for t, v in be.items())
                lines.append(f"Breakeven Inflation: {be_str}")

            lines.append("")

        # ── FX Rates ──
        fx = context.get("fx", {})
        if fx:
            lines.append("=== FX RATES ===")

            usd_dir = fx_analytics.get("usd_direction")
            dm_avg = fx_analytics.get("dm_avg_24h")
            em_avg = fx_analytics.get("em_avg_24h")

            if usd_dir:
                lines.append(f"USD Direction (vs DM): {usd_dir}")

            # DM pairs
            dm_pairs = fx_analytics.get("dm_pairs", {})
            if dm_pairs:
                lines.append(f"DM Currencies (avg 24h: {dm_avg:+.2f}%):" if dm_avg is not None else "DM Currencies:")
                for pair, data in dm_pairs.items():
                    flag = fx_analytics.get("quality_flags", {}).get(pair, "OK")
                    changes = []
                    for period in ['change_1h', 'change_24h', 'change_1w', 'change_ytd']:
                        v = data.get(period)
                        label = period.replace('change_', '')
                        if v is not None:
                            changes.append(f"{label}: {v:+.2f}%")
                    flag_str = f" [{flag}]" if flag != "OK" else ""
                    lines.append(f"  {pair}: {data['rate']:.4f} ({', '.join(changes)}){flag_str}")

            # EM pairs
            em_pairs = fx_analytics.get("em_pairs", {})
            if em_pairs:
                lines.append(f"EM Currencies (avg 24h: {em_avg:+.2f}%):" if em_avg is not None else "EM Currencies:")
                for pair, data in em_pairs.items():
                    flag = fx_analytics.get("quality_flags", {}).get(pair, "OK")
                    changes = []
                    for period in ['change_1h', 'change_24h', 'change_1w', 'change_ytd']:
                        v = data.get(period)
                        label = period.replace('change_', '')
                        if v is not None:
                            changes.append(f"{label}: {v:+.2f}%")
                    flag_str = f" [SUSPECT - IGNORE]" if flag != "OK" else ""
                    lines.append(f"  {pair}: {data['rate']:.4f} ({', '.join(changes)}){flag_str}")

            # Other pairs (USDX, etc.)
            other = fx_analytics.get("other_pairs", {})
            for pair, data in other.items():
                flag = fx_analytics.get("quality_flags", {}).get(pair, "OK")
                changes = []
                for period in ['change_1h', 'change_24h', 'change_1w', 'change_ytd']:
                    v = data.get(period)
                    label = period.replace('change_', '')
                    if v is not None:
                        changes.append(f"{label}: {v:+.2f}%")
                flag_str = f" [{flag}]" if flag != "OK" else ""
                lines.append(f"  {pair}: {data['rate']:.4f} ({', '.join(changes)}){flag_str}")

            lines.append("")

        # ── Credit Spreads ──
        credit = context.get("credit", {})
        if credit:
            lines.append("=== CREDIT SPREADS ===")
            stress = credit_analytics.get("stress_level", "NORMAL")
            lines.append(f"Credit Stress Assessment: {stress}")

            for name, data in credit.items():
                spread = data.get("spread_bps")
                if spread is None:
                    continue

                parts = [f"{spread:.0f} bps"]
                if data.get("change_1d") is not None:
                    parts.append(f"1d: {data['change_1d']:+.1f}")
                if data.get("change_1w") is not None:
                    parts.append(f"1w: {data['change_1w']:+.1f}")

                vs_avg = credit_analytics.get("vs_avg", {}).get(name)
                if vs_avg is not None:
                    parts.append(f"vs 90d avg: {vs_avg:+.1f} bps")

                quality = credit_analytics.get("quality_flags", {}).get(name, "OK")
                if "SUSPECT" in str(quality):
                    parts.append(f"Quality: {quality}")

                lines.append(f"  {name}: {' | '.join(parts)}")
            lines.append("")

        # ── Critical/High Priority News (elevated to top-level importance) ──
        news = context.get("news", [])
        news_a = analytics.get("news", {})
        priority_news = news_a.get("priority_headlines", [])
        if priority_news:
            # Split into economic/market vs political/other
            econ_categories = {'CENTRAL_BANK', 'RATE_DECISION', 'ECONOMIC_DATA', 'ECON',
                               'MARKET_MOVE', 'CREDIT', 'DEBT_CREDIT', 'FX', 'CURRENCY'}
            econ_keywords = [
                'fomc', 'fed ', 'federal reserve', 'rate cut', 'rate hike',
                'rate decision', 'fed holds', 'fed cuts', 'fed raises',
                'basis point', 'monetary policy', 'gdp', 'inflation',
                'jobs report', 'payroll', 'unemployment', 'treasury',
                'yield', 'bond', 'credit spread', 'trade balance',
                'tariff', 'trade war', 'oil price', 'gold ',
            ]
            econ_news = []
            other_news = []
            for article in priority_news:
                cat = (article.get('category') or '').upper()
                title_lower = (article.get('title') or '').lower()
                is_econ = (cat in econ_categories or
                           any(kw in title_lower for kw in econ_keywords))
                if is_econ:
                    econ_news.append(article)
                else:
                    other_news.append(article)

            if econ_news:
                lines.append("=== MARKET-MOVING NEWS (incorporate these into your analysis) ===")
                for article in econ_news[:8]:
                    lines.append(f"  ** [{article.get('category', '?')}/{article.get('severity', '?')}] {article['title']} ({article['source']}, {article.get('published', '?')})")
                    if article.get('summary'):
                        lines.append(f"     {article['summary'][:200]}")
                lines.append("")

            if other_news:
                lines.append("=== OTHER HIGH-PRIORITY NEWS (political/geopolitical context) ===")
                for article in other_news[:5]:  # Limit political noise
                    lines.append(f"  [{article.get('category', '?')}/{article.get('severity', '?')}] {article['title']} ({article['source']}, {article.get('published', '?')})")
                lines.append("")

        # ── News Digest ──
        if news:
            lines.append("=== NEWS DIGEST ===")
            sev = news_a.get("severity_counts", {})
            lines.append(f"Severity: CRITICAL: {sev.get('CRITICAL', 0)}, HIGH: {sev.get('HIGH', 0)}, MEDIUM: {sev.get('MEDIUM', 0)}, LOW: {sev.get('LOW', 0)}")

            cats = news_a.get("by_category", {})
            if cats:
                cat_str = ", ".join(f"{k}: {v}" for k, v in cats.items())
                lines.append(f"Categories: {cat_str}")

            top_inst = news_a.get("top_institutions", [])
            if top_inst:
                inst_str = ", ".join(f"{name} ({count})" for name, count in top_inst[:5])
                lines.append(f"Top Institutions: {inst_str}")

            top_leaders = news_a.get("top_leaders", [])
            if top_leaders:
                leader_str = ", ".join(f"{name} ({count})" for name, count in top_leaders[:5])
                lines.append(f"Top Leaders: {leader_str}")

            lines.append("")
            lines.append("All Headlines:")
            for article in news[:15]:
                cat = article.get("category") or "?"
                sev_label = article.get("severity") or "?"
                lines.append(f"  [{cat}/{sev_label}] {article['title']} ({article['source']}, {article.get('published', '?')})")
            lines.append("")

        # ── Upcoming Releases ──
        calendar = context.get("calendar", [])
        if calendar:
            lines.append("=== UPCOMING RELEASES ===")
            for release in calendar:
                lines.append(f"  {release['name']} ({release['date']}) - {release['importance']} importance")
            lines.append("")

        # ── Pre-computed Analyst Notes ──
        lines.append("=== ANALYST NOTES (Pre-computed) ===")
        notes = self._generate_analyst_notes(context, analytics)
        for i, note in enumerate(notes, 1):
            lines.append(f"{i}. {note}")

        return "\n".join(lines)

    def _generate_analyst_notes(self, context: Dict[str, Any], analytics: Dict[str, Any]) -> List[str]:
        """Generate 3-5 rule-based analyst observations."""
        notes = []
        regime = analytics.get("regime", {})
        yield_a = analytics.get("yields", {})
        credit_a = analytics.get("credit", {})
        ind_a = analytics.get("indicators", {})
        derived = ind_a.get("_derived", {})

        # Yield curve note
        shape = yield_a.get("shape")
        trend = yield_a.get("steepening_trend")
        wow_spread = yield_a.get("spread_wow_change_bps")
        if shape:
            note = f"Yield curve classified as {shape}."
            if trend and wow_spread is not None:
                note += f" 10Y-2Y spread {trend.lower()} ({wow_spread:+.1f} bps WoW)."
            notes.append(note)

        # Credit note
        stress = credit_a.get("stress_level", "NORMAL")
        if stress != "NORMAL":
            notes.append(f"Credit markets showing {stress} stress levels.")
        else:
            notes.append("Credit spreads within normal historical range.")

        # Real rates note
        real_ff = derived.get("real_fed_funds")
        if real_ff is not None:
            stance = "restrictive" if real_ff > 1.0 else "accommodative" if real_ff < 0 else "neutral"
            notes.append(f"Real fed funds rate at {real_ff:+.2f}% — monetary policy remains {stance}.")

        # Sahm Rule note
        sahm = derived.get("sahm_rule")
        if sahm is not None:
            if derived.get("sahm_triggered"):
                notes.append(f"Sahm Rule TRIGGERED at {sahm:.2f} (>=0.50). Historically indicates recession onset.")
            elif sahm > 0.30:
                notes.append(f"Sahm Rule at {sahm:.2f} — approaching but below 0.50 trigger. Labor market softening bears watching.")
            else:
                notes.append(f"Sahm Rule at {sahm:.2f} — well below recession trigger. Labor market stable.")

        # FX note
        fx_a = analytics.get("fx", {})
        usd_dir = fx_a.get("usd_direction")
        suspect_pairs = [p for p, f in fx_a.get("quality_flags", {}).items() if f != "OK"]
        if suspect_pairs:
            notes.append(f"FX data quality issues: {', '.join(suspect_pairs)} flagged as suspect — ignore these in analysis.")
        elif usd_dir:
            notes.append(f"USD {usd_dir.lower()} vs DM currencies on balance.")

        return notes[:5]

    # ──────────────────────────────────────────────
    # PHASE 4: Narrative Generation
    # ──────────────────────────────────────────────

    async def generate_narrative(self) -> Dict[str, Any]:
        """Generate a market narrative using Claude API with pre-computed analytics."""
        if not self.is_available():
            return {
                "error": "AI generation not available. Please set ANTHROPIC_API_KEY.",
                "generated_at": get_current_time().isoformat()
            }

        try:
            # Phase 1: Gather raw data
            context = self._gather_context()

            # Phase 2: Compute analytics
            analytics = self._compute_analytics(context)

            # Phase 3: Format pre-digested briefing
            context_text = self._format_context_for_prompt(context, analytics)

            regime = analytics.get("regime", {}).get("regime", "UNKNOWN")
            current_date = context.get("timestamp", "")

            # Build user message
            user_message = f"""You are receiving a pre-digested market briefing with all arithmetic already computed. Your job is INTERPRETATION and NARRATIVE, not calculation.

{context_text}

INSTRUCTIONS:
- All changes, trends, and derived metrics are pre-computed. Trust them — do NOT recalculate.
- Items flagged as SUSPECT are data errors. Ignore them entirely.
- The ANALYST NOTES are rule-based observations. Agree, disagree, or extend them with deeper context.
- The Market Regime assessment ({regime}) is a starting point. Challenge it if the data tells a different story.
- The current date is {current_date}. Many indicators have publication lags — frame analysis around today, not the data's reference period.
- For PAYEMS, the MoM change in thousands IS the headline jobs number.
- For FEDFUNDS, the level change is in percentage points (e.g., -0.25 = 25bp cut). NOTE: FEDFUNDS is a monthly average from FRED — it may not reflect very recent rate decisions. CHECK THE BREAKING/HIGH-PRIORITY NEWS SECTION for any rate cuts or hikes that happened in the last few days, and incorporate them prominently.
- The BREAKING/HIGH-PRIORITY NEWS section contains market-moving headlines. These should inform your narrative prominently — especially rate decisions, trade policy changes, and geopolitical events. If the Fed cut or raised rates recently, LEAD with that.
- Write 400-600 words of flowing prose. No bullet points, no headers.
- Do NOT use percentiles or percentile rankings in your narrative. Focus on actual values, changes, and trends.
- Address: labor, inflation, growth, rates/markets, forward outlook."""

            # Call Claude API
            client = self._get_client()

            message = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1500,
                messages=[
                    {"role": "user", "content": user_message}
                ],
                system=SYSTEM_PROMPT
            )

            narrative = message.content[0].text

            result = {
                "narrative": narrative,
                "generated_at": get_current_time().isoformat(),
                "model": "claude-sonnet-4-5-20250929",
                "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
                "indicators_count": len(context.get('indicators', {})),
                "news_count": len(context.get('news', [])),
                "market_regime": regime,
            }

            self._last_narrative = result
            logger.success(f"Generated narrative using {result['tokens_used']} tokens (regime: {regime})")
            return result

        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            return {
                "error": f"API error: {str(e)}",
                "generated_at": get_current_time().isoformat()
            }
        except Exception as e:
            logger.error(f"Narrative generation error: {e}")
            return {
                "error": f"Generation failed: {str(e)}",
                "generated_at": get_current_time().isoformat()
            }

    def get_last_narrative(self) -> Optional[Dict[str, Any]]:
        """Get the most recently generated narrative."""
        return self._last_narrative
