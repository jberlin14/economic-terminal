"""
Market Summary Generator

Analyzes economic data and generates intelligent narrative summaries.
"""

from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.orm import Session
from loguru import logger

from modules.utils.timezone import get_current_time


class SentimentLevel(str, Enum):
    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"


class TrendDirection(str, Enum):
    IMPROVING = "improving"
    STABLE = "stable"
    DETERIORATING = "deteriorating"


@dataclass
class MarketSummary:
    """Complete market summary with all components."""
    timestamp: datetime
    headline: str
    overview: str
    sections: Dict[str, str]
    key_metrics: List[Dict[str, Any]]
    sentiment: SentimentLevel
    alerts: List[str]
    trends: Dict[str, TrendDirection]


class MarketSummaryGenerator:
    """
    Generates comprehensive market summaries from economic data.

    Uses rule-based analysis to create human-readable narratives.
    """

    def __init__(self, db: Session):
        self.db = db
        self._cache: Optional[MarketSummary] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=5)

    def generate_summary(self, force_refresh: bool = False) -> MarketSummary:
        """
        Generate a comprehensive market summary.

        Args:
            force_refresh: Bypass cache and regenerate

        Returns:
            MarketSummary object with all components
        """
        # Check cache
        now = get_current_time()
        if not force_refresh and self._cache and self._cache_time:
            if now - self._cache_time < self._cache_ttl:
                return self._cache

        # Gather all data
        data = self._gather_data()

        # Generate components
        headline = self._generate_headline(data)
        overview = self._generate_overview(data)
        sections = self._generate_sections(data)
        key_metrics = self._extract_key_metrics(data)
        sentiment = self._assess_sentiment(data)
        alerts = self._generate_alerts(data)
        trends = self._assess_trends(data)

        summary = MarketSummary(
            timestamp=now,
            headline=headline,
            overview=overview,
            sections=sections,
            key_metrics=key_metrics,
            sentiment=sentiment,
            alerts=alerts,
            trends=trends
        )

        # Cache result
        self._cache = summary
        self._cache_time = now

        return summary

    def _gather_data(self) -> Dict[str, Any]:
        """Gather all relevant data for analysis."""
        data = {
            "fx_rates": self._get_fx_data(),
            "yields": self._get_yield_data(),
            "credit": self._get_credit_data(),
            "indicators": self._get_indicator_data(),
            "news": self._get_news_data()
        }
        return data

    def _get_fx_data(self) -> Dict[str, Any]:
        """Get latest FX data."""
        try:
            from modules.data_storage.schema import FXRate
            rates = self.db.query(FXRate).order_by(FXRate.timestamp.desc()).limit(10).all()

            fx_data = {}
            for rate in rates:
                if rate.pair not in fx_data:
                    fx_data[rate.pair] = {
                        "rate": rate.rate,
                        "change_24h": rate.change_24h,
                        "timestamp": rate.timestamp
                    }
            return fx_data
        except Exception as e:
            logger.error(f"Error fetching FX data: {e}")
            return {}

    def _get_yield_data(self) -> Dict[str, Any]:
        """Get latest yield curve data."""
        try:
            from modules.data_storage.schema import YieldCurve
            curve = self.db.query(YieldCurve).order_by(YieldCurve.timestamp.desc()).first()

            if curve:
                return {
                    "2y": curve.yield_2y,
                    "5y": curve.yield_5y,
                    "10y": curve.yield_10y,
                    "30y": curve.yield_30y,
                    "spread_10y2y": curve.yield_10y - curve.yield_2y if curve.yield_10y and curve.yield_2y else None,
                    "timestamp": curve.timestamp
                }
            return {}
        except Exception as e:
            logger.error(f"Error fetching yield data: {e}")
            return {}

    def _get_credit_data(self) -> Dict[str, Any]:
        """Get latest credit spread data."""
        try:
            from modules.data_storage.schema import CreditSpread
            spreads = self.db.query(CreditSpread).order_by(CreditSpread.timestamp.desc()).limit(5).all()

            credit_data = {}
            for spread in spreads:
                if spread.index_name not in credit_data:
                    credit_data[spread.index_name] = {
                        "spread": spread.spread,
                        "change_1d": spread.change_1d,
                        "timestamp": spread.timestamp
                    }
            return credit_data
        except Exception as e:
            logger.error(f"Error fetching credit data: {e}")
            return {}

    def _get_indicator_data(self) -> Dict[str, Any]:
        """Get key economic indicator data."""
        try:
            from modules.economic_indicators import IndicatorStorage

            storage = IndicatorStorage(self.db)

            # Key indicators to analyze
            key_series = {
                "CPIAUCSL": "CPI",
                "PAYEMS": "Nonfarm Payrolls",
                "UNRATE": "Unemployment Rate",
                "FEDFUNDS": "Fed Funds Rate",
                "GDP": "GDP",
                "RSXFS": "Retail Sales",
                "INDPRO": "Industrial Production",
                "UMCSENT": "Consumer Sentiment"
            }

            indicator_data = {}
            for series_id, name in key_series.items():
                try:
                    indicator = storage.get_indicator(series_id)
                    if indicator:
                        # Get latest values
                        df = storage.get_values(series_id, limit=13)  # 13 months for YoY
                        if df is not None and not df.empty:
                            latest = df.iloc[0]
                            yoy_change = None
                            mom_change = None

                            if len(df) >= 2:
                                mom_change = ((latest['value'] - df.iloc[1]['value']) / abs(df.iloc[1]['value'])) * 100

                            if len(df) >= 13:
                                yoy_change = ((latest['value'] - df.iloc[12]['value']) / abs(df.iloc[12]['value'])) * 100

                            indicator_data[series_id] = {
                                "name": name,
                                "value": latest['value'],
                                "date": latest['date'],
                                "yoy_change": yoy_change,
                                "mom_change": mom_change,
                                "units": indicator.units
                            }
                except Exception as e:
                    logger.debug(f"Could not get data for {series_id}: {e}")

            return indicator_data
        except Exception as e:
            logger.error(f"Error fetching indicator data: {e}")
            return {}

    def _get_news_data(self) -> List[Dict[str, Any]]:
        """Get recent news headlines."""
        try:
            from modules.data_storage.schema import NewsArticle
            articles = self.db.query(NewsArticle).order_by(
                NewsArticle.published_at.desc()
            ).limit(10).all()

            return [
                {
                    "title": a.title,
                    "source": a.source,
                    "severity": a.severity,
                    "published_at": a.published_at
                }
                for a in articles
            ]
        except Exception as e:
            logger.error(f"Error fetching news data: {e}")
            return []

    def _generate_headline(self, data: Dict[str, Any]) -> str:
        """Generate a punchy headline summarizing current conditions."""
        indicators = data.get("indicators", {})
        yields_data = data.get("yields", {})

        # Check for notable conditions
        headlines = []

        # Inflation check
        cpi = indicators.get("CPIAUCSL", {})
        if cpi.get("yoy_change"):
            yoy = cpi["yoy_change"]
            if yoy > 5:
                headlines.append(f"Inflation Remains Elevated at {yoy:.1f}% YoY")
            elif yoy > 3:
                headlines.append(f"Inflation Above Target at {yoy:.1f}% YoY")
            elif yoy < 2:
                headlines.append(f"Inflation Cools to {yoy:.1f}% YoY")

        # Labor market
        unrate = indicators.get("UNRATE", {})
        payems = indicators.get("PAYEMS", {})
        if unrate.get("value"):
            if unrate["value"] < 4:
                headlines.append("Labor Market Remains Tight")
            elif unrate["value"] > 5:
                headlines.append("Unemployment Rising")

        # Yield curve
        spread = yields_data.get("spread_10y2y")
        if spread is not None:
            if spread < 0:
                headlines.append("Yield Curve Inverted - Recession Signal")
            elif spread < 0.25:
                headlines.append("Yield Curve Flattening")

        if headlines:
            return headlines[0]

        return "Markets Steady as Economic Data Mixed"

    def _generate_overview(self, data: Dict[str, Any]) -> str:
        """Generate a 2-3 sentence overview of market conditions."""
        indicators = data.get("indicators", {})
        yields_data = data.get("yields", {})
        fx = data.get("fx_rates", {})

        parts = []

        # Economic growth assessment
        gdp = indicators.get("GDP", {})
        indpro = indicators.get("INDPRO", {})

        if gdp.get("yoy_change"):
            if gdp["yoy_change"] > 2:
                parts.append("The economy continues to expand at a healthy pace")
            elif gdp["yoy_change"] > 0:
                parts.append("Economic growth remains modest")
            else:
                parts.append("The economy shows signs of contraction")

        # Inflation and Fed
        cpi = indicators.get("CPIAUCSL", {})
        fed_funds = indicators.get("FEDFUNDS", {})

        if cpi.get("yoy_change") and fed_funds.get("value"):
            if cpi["yoy_change"] > 3:
                parts.append(f"with inflation at {cpi['yoy_change']:.1f}% keeping pressure on the Fed")
            else:
                parts.append(f"as inflation moderates to {cpi['yoy_change']:.1f}%")

        # Labor market
        unrate = indicators.get("UNRATE", {})
        if unrate.get("value"):
            parts.append(f"Unemployment stands at {unrate['value']:.1f}%")

        # Yields
        if yields_data.get("10y"):
            parts.append(f"with the 10-year Treasury yielding {yields_data['10y']:.2f}%")

        if parts:
            overview = ". ".join(parts[:2]) + "."
            if len(parts) > 2:
                overview += " " + ". ".join(parts[2:]) + "."
            return overview

        return "Economic conditions remain mixed with markets awaiting key data releases."

    def _generate_sections(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Generate detailed sections for each area."""
        sections = {}

        # Inflation Section
        sections["inflation"] = self._generate_inflation_section(data)

        # Labor Market Section
        sections["labor"] = self._generate_labor_section(data)

        # Growth Section
        sections["growth"] = self._generate_growth_section(data)

        # Rates Section
        sections["rates"] = self._generate_rates_section(data)

        return sections

    def _generate_inflation_section(self, data: Dict[str, Any]) -> str:
        """Generate inflation analysis section."""
        indicators = data.get("indicators", {})
        cpi = indicators.get("CPIAUCSL", {})

        if not cpi.get("value"):
            return "Inflation data not available."

        yoy = cpi.get("yoy_change", 0)
        mom = cpi.get("mom_change", 0)

        text = f"Consumer prices "
        if mom > 0.3:
            text += f"rose {mom:.1f}% month-over-month, "
        elif mom < -0.1:
            text += f"fell {abs(mom):.1f}% month-over-month, "
        else:
            text += f"were relatively flat month-over-month, "

        if yoy > 4:
            text += f"with annual inflation running hot at {yoy:.1f}%. "
            text += "This remains well above the Fed's 2% target and suggests continued monetary policy pressure."
        elif yoy > 2.5:
            text += f"bringing annual inflation to {yoy:.1f}%. "
            text += "Inflation remains above the Fed's target but shows signs of moderating."
        else:
            text += f"with annual inflation at {yoy:.1f}%. "
            text += "Price pressures appear to be normalizing toward the Fed's target."

        return text

    def _generate_labor_section(self, data: Dict[str, Any]) -> str:
        """Generate labor market analysis section."""
        indicators = data.get("indicators", {})
        unrate = indicators.get("UNRATE", {})
        payems = indicators.get("PAYEMS", {})

        parts = []

        if unrate.get("value"):
            rate = unrate["value"]
            if rate < 4:
                parts.append(f"The labor market remains exceptionally tight with unemployment at {rate:.1f}%")
            elif rate < 5:
                parts.append(f"The labor market is healthy with unemployment at {rate:.1f}%")
            else:
                parts.append(f"The labor market shows signs of softening with unemployment at {rate:.1f}%")

        if payems.get("mom_change"):
            change = payems["mom_change"]
            if change > 0.2:
                parts.append("Job growth continues to be robust")
            elif change > 0:
                parts.append("Employment gains remain positive")
            else:
                parts.append("Employment growth has stalled")

        if parts:
            return ". ".join(parts) + "."
        return "Labor market data not available."

    def _generate_growth_section(self, data: Dict[str, Any]) -> str:
        """Generate economic growth analysis section."""
        indicators = data.get("indicators", {})
        gdp = indicators.get("GDP", {})
        indpro = indicators.get("INDPRO", {})
        retail = indicators.get("RSXFS", {})

        parts = []

        if gdp.get("yoy_change"):
            yoy = gdp["yoy_change"]
            if yoy > 3:
                parts.append(f"GDP growth is strong at {yoy:.1f}% year-over-year")
            elif yoy > 1:
                parts.append(f"Economic growth is moderate at {yoy:.1f}% year-over-year")
            elif yoy > 0:
                parts.append(f"Growth has slowed to {yoy:.1f}% year-over-year")
            else:
                parts.append(f"The economy is contracting at {yoy:.1f}% year-over-year")

        if indpro.get("mom_change"):
            if indpro["mom_change"] > 0:
                parts.append("Industrial production is expanding")
            else:
                parts.append("Industrial output has declined")

        if retail.get("mom_change"):
            if retail["mom_change"] > 0.5:
                parts.append("Consumer spending remains strong")
            elif retail["mom_change"] < -0.5:
                parts.append("Consumer spending has weakened")

        if parts:
            return ". ".join(parts) + "."
        return "Growth indicators are mixed."

    def _generate_rates_section(self, data: Dict[str, Any]) -> str:
        """Generate interest rates analysis section."""
        yields_data = data.get("yields", {})
        indicators = data.get("indicators", {})
        fed_funds = indicators.get("FEDFUNDS", {})

        parts = []

        if fed_funds.get("value"):
            parts.append(f"The Fed Funds rate stands at {fed_funds['value']:.2f}%")

        if yields_data.get("10y"):
            parts.append(f"The 10-year Treasury is yielding {yields_data['10y']:.2f}%")

        spread = yields_data.get("spread_10y2y")
        if spread is not None:
            if spread < 0:
                parts.append(f"The yield curve remains inverted ({spread:.0f} bps), historically a recession indicator")
            elif spread < 0.5:
                parts.append(f"The yield curve is flat at {spread*100:.0f} bps")
            else:
                parts.append(f"The yield curve shows a normal slope of {spread*100:.0f} bps")

        if parts:
            return ". ".join(parts) + "."
        return "Rate data not available."

    def _extract_key_metrics(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract key metrics for display."""
        metrics = []
        indicators = data.get("indicators", {})
        yields_data = data.get("yields", {})

        # CPI
        if "CPIAUCSL" in indicators:
            cpi = indicators["CPIAUCSL"]
            metrics.append({
                "name": "CPI YoY",
                "value": f"{cpi.get('yoy_change', 0):.1f}%",
                "trend": "up" if cpi.get('mom_change', 0) > 0 else "down",
                "importance": "high"
            })

        # Unemployment
        if "UNRATE" in indicators:
            unrate = indicators["UNRATE"]
            metrics.append({
                "name": "Unemployment",
                "value": f"{unrate.get('value', 0):.1f}%",
                "trend": "up" if unrate.get('mom_change', 0) > 0 else "down",
                "importance": "high"
            })

        # 10Y Yield
        if yields_data.get("10y"):
            metrics.append({
                "name": "10Y Treasury",
                "value": f"{yields_data['10y']:.2f}%",
                "trend": "neutral",
                "importance": "high"
            })

        # Yield Curve
        spread = yields_data.get("spread_10y2y")
        if spread is not None:
            metrics.append({
                "name": "10Y-2Y Spread",
                "value": f"{spread*100:.0f} bps",
                "trend": "warning" if spread < 0 else "neutral",
                "importance": "high" if spread < 0 else "medium"
            })

        # GDP
        if "GDP" in indicators:
            gdp = indicators["GDP"]
            metrics.append({
                "name": "GDP YoY",
                "value": f"{gdp.get('yoy_change', 0):.1f}%",
                "trend": "up" if gdp.get('yoy_change', 0) > 0 else "down",
                "importance": "high"
            })

        return metrics

    def _assess_sentiment(self, data: Dict[str, Any]) -> SentimentLevel:
        """Assess overall market sentiment."""
        indicators = data.get("indicators", {})
        yields_data = data.get("yields", {})

        score = 0  # Start neutral

        # GDP growth
        gdp = indicators.get("GDP", {})
        if gdp.get("yoy_change"):
            if gdp["yoy_change"] > 2.5:
                score += 2
            elif gdp["yoy_change"] > 1:
                score += 1
            elif gdp["yoy_change"] < 0:
                score -= 2

        # Unemployment
        unrate = indicators.get("UNRATE", {})
        if unrate.get("value"):
            if unrate["value"] < 4:
                score += 1
            elif unrate["value"] > 6:
                score -= 2

        # Inflation (moderate is good)
        cpi = indicators.get("CPIAUCSL", {})
        if cpi.get("yoy_change"):
            if 1.5 < cpi["yoy_change"] < 3:
                score += 1
            elif cpi["yoy_change"] > 5:
                score -= 1

        # Yield curve
        spread = yields_data.get("spread_10y2y")
        if spread is not None and spread < 0:
            score -= 2

        # Convert score to sentiment
        if score >= 3:
            return SentimentLevel.VERY_BULLISH
        elif score >= 1:
            return SentimentLevel.BULLISH
        elif score <= -3:
            return SentimentLevel.VERY_BEARISH
        elif score <= -1:
            return SentimentLevel.BEARISH
        else:
            return SentimentLevel.NEUTRAL

    def _generate_alerts(self, data: Dict[str, Any]) -> List[str]:
        """Generate alert messages for notable conditions."""
        alerts = []
        indicators = data.get("indicators", {})
        yields_data = data.get("yields", {})

        # Yield curve inversion
        spread = yields_data.get("spread_10y2y")
        if spread is not None and spread < 0:
            alerts.append("Yield curve inverted - historically precedes recessions by 12-18 months")

        # High inflation
        cpi = indicators.get("CPIAUCSL", {})
        if cpi.get("yoy_change") and cpi["yoy_change"] > 4:
            alerts.append(f"Inflation running hot at {cpi['yoy_change']:.1f}% - above Fed target")

        # Rising unemployment
        unrate = indicators.get("UNRATE", {})
        if unrate.get("mom_change") and unrate["mom_change"] > 0.3:
            alerts.append("Unemployment rising - labor market may be cooling")

        return alerts

    def _assess_trends(self, data: Dict[str, Any]) -> Dict[str, TrendDirection]:
        """Assess trends for key areas."""
        trends = {}
        indicators = data.get("indicators", {})

        # Inflation trend
        cpi = indicators.get("CPIAUCSL", {})
        if cpi.get("mom_change"):
            if cpi["mom_change"] > 0.3:
                trends["inflation"] = TrendDirection.DETERIORATING
            elif cpi["mom_change"] < 0:
                trends["inflation"] = TrendDirection.IMPROVING
            else:
                trends["inflation"] = TrendDirection.STABLE

        # Employment trend
        unrate = indicators.get("UNRATE", {})
        if unrate.get("mom_change"):
            if unrate["mom_change"] < -0.1:
                trends["employment"] = TrendDirection.IMPROVING
            elif unrate["mom_change"] > 0.2:
                trends["employment"] = TrendDirection.DETERIORATING
            else:
                trends["employment"] = TrendDirection.STABLE

        # Growth trend
        gdp = indicators.get("GDP", {})
        if gdp.get("yoy_change"):
            if gdp["yoy_change"] > 2:
                trends["growth"] = TrendDirection.IMPROVING
            elif gdp["yoy_change"] < 0:
                trends["growth"] = TrendDirection.DETERIORATING
            else:
                trends["growth"] = TrendDirection.STABLE

        return trends

    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to dictionary for API response."""
        summary = self.generate_summary()

        return {
            "timestamp": summary.timestamp.isoformat(),
            "headline": summary.headline,
            "overview": summary.overview,
            "sections": summary.sections,
            "key_metrics": summary.key_metrics,
            "sentiment": summary.sentiment.value,
            "alerts": summary.alerts,
            "trends": {k: v.value for k, v in summary.trends.items()}
        }
