"""
AI Market Journal

Creates and retrieves daily market journal entries that persist the AI's
evolving worldview across sessions. One entry per calendar day.
"""

from datetime import date, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from loguru import logger

from modules.data_storage.schema import AIMarketJournal


class MarketJournal:
    """Manages persistent daily market journal entries."""

    def __init__(self, db: Session):
        self.db = db

    def get_today(self) -> Optional[AIMarketJournal]:
        """Get today's journal entry, if it exists."""
        return self.db.query(AIMarketJournal).filter(
            AIMarketJournal.date == date.today()
        ).first()

    def get_recent(self, days: int = 7) -> List[AIMarketJournal]:
        """Get recent journal entries for context (most recent first)."""
        cutoff = date.today() - timedelta(days=days)
        return self.db.query(AIMarketJournal).filter(
            AIMarketJournal.date >= cutoff
        ).order_by(AIMarketJournal.date.desc()).all()

    def create_or_update_today(self) -> Optional[AIMarketJournal]:
        """Create or update today's journal entry from current market data."""
        try:
            from .analytics_engine import (
                gather_market_context, compute_analytics, build_indicator_snapshot
            )

            context = gather_market_context(self.db)
            analytics = compute_analytics(context, self.db)
            snapshot = build_indicator_snapshot(context, analytics)

            regime_data = analytics.get("regime", {})
            regime = regime_data.get("regime", "UNKNOWN")

            themes = self._extract_themes(analytics, snapshot)

            # News themes digest
            from .analytics_engine import _sanitize_for_json
            news_analytics = analytics.get("news", {})
            news_themes = _sanitize_for_json({
                "top_categories": news_analytics.get("by_category", {}),
                "top_leaders": news_analytics.get("top_leaders", []),
                "severity_counts": news_analytics.get("severity_counts", {}),
                "total": news_analytics.get("total", 0),
            })

            # Build a concise narrative summary from the data
            narrative = self._build_narrative_summary(snapshot, regime, themes)

            existing = self.get_today()
            if existing:
                existing.regime = regime
                existing.key_themes = themes
                existing.indicator_snapshot = snapshot
                existing.news_themes = news_themes
                existing.narrative_summary = narrative
                self.db.commit()
                return existing

            entry = AIMarketJournal(
                date=date.today(),
                regime=regime,
                key_themes=themes,
                indicator_snapshot=snapshot,
                news_themes=news_themes,
                narrative_summary=narrative,
            )
            self.db.add(entry)
            self.db.commit()
            return entry

        except Exception as e:
            logger.error(f"Failed to create journal entry: {e}")
            self.db.rollback()
            return None

    def _extract_themes(self, analytics: Dict[str, Any], snapshot: Dict[str, Any]) -> List[str]:
        """Extract key macro themes from analytics."""
        themes = []
        derived = snapshot.get("derived", {})

        # Inflation theme
        cpi_yoy = derived.get("cpi_yoy")
        if cpi_yoy is not None:
            if cpi_yoy > 4.0:
                themes.append("inflation_hot")
            elif cpi_yoy > 3.0:
                themes.append("inflation_elevated")
            elif cpi_yoy < 2.0:
                themes.append("disinflation_risk")
            else:
                themes.append("disinflation_progress")

        # Labor theme
        sahm = derived.get("sahm_rule")
        if sahm is not None:
            if sahm >= 0.50:
                themes.append("sahm_triggered")
            elif sahm > 0.30:
                themes.append("labor_softening")
            else:
                themes.append("labor_stable")

        # Yield curve theme — use the 10Y-2Y spread directly (not the stored shape
        # string, which may have been computed with older buggy logic)
        spreads = snapshot.get("spreads", {})
        spread_10y2y = spreads.get("10y2y")
        if spread_10y2y is not None:
            spread_bps = spread_10y2y * 100
            if spread_bps < -50:
                themes.append("curve_deeply_inverted")
            elif spread_bps < -10:
                themes.append("curve_inverted")
            elif spread_bps < 25:
                themes.append("curve_flat")
            else:
                steep = snapshot.get("steepening_trend", "")
                if steep == "STEEPENING":
                    themes.append("curve_steepening")
                elif steep == "FLATTENING":
                    themes.append("curve_flattening")
                else:
                    themes.append("curve_normal")

        # Credit theme
        stress = snapshot.get("credit_stress", "NORMAL")
        if stress and stress != "NORMAL":
            themes.append(f"credit_{stress.lower()}")

        # Fed stance
        real_ff = derived.get("real_fed_funds")
        if real_ff is not None:
            if real_ff > 2.0:
                themes.append("policy_tight")
            elif real_ff > 0.5:
                themes.append("policy_mildly_restrictive")
            elif real_ff < -1.0:
                themes.append("policy_accommodative")

        # Regime
        regime = snapshot.get("regime", "")
        if regime in ("CRISIS", "RISK_OFF"):
            themes.append(f"regime_{regime.lower()}")

        return themes

    def _build_narrative_summary(self, snapshot: Dict[str, Any], regime: str, themes: List[str]) -> str:
        """Build a concise data-driven narrative summary from the snapshot.

        This is a rule-based summary (no AI call) so it's fast and always available.
        """
        parts = []
        derived = snapshot.get("derived", {})
        spreads = snapshot.get("spreads", {})

        # Regime
        regime_desc = {
            "RISK_ON": "Risk-on conditions prevail with no major stress signals.",
            "CAUTIOUS": "Conditions warrant caution as multiple indicators show emerging stress.",
            "RISK_OFF": "Risk-off environment with significant stress across several pillars.",
            "CRISIS": "Crisis-level stress detected across multiple market pillars.",
        }
        parts.append(regime_desc.get(regime, f"Regime: {regime}."))

        # Inflation
        cpi_yoy = derived.get("cpi_yoy")
        if cpi_yoy is not None:
            if cpi_yoy < 2.5:
                parts.append(f"Inflation is contained at {cpi_yoy:.1f}% YoY, within the Fed's comfort zone.")
            elif cpi_yoy < 3.5:
                parts.append(f"Inflation remains moderately elevated at {cpi_yoy:.1f}% YoY, above the 2% target but trending toward normalization.")
            else:
                parts.append(f"Inflation is running hot at {cpi_yoy:.1f}% YoY, well above the Fed's 2% target.")

        # Labor
        sahm = derived.get("sahm_rule")
        if sahm is not None:
            if sahm >= 0.50:
                parts.append(f"The Sahm Rule has triggered at {sahm:.2f}, signaling recession-level labor market deterioration.")
            elif sahm > 0.30:
                parts.append(f"The Sahm Rule reads {sahm:.2f}, approaching the 0.50 recession threshold but not yet triggered.")
            else:
                parts.append(f"The labor market remains stable with the Sahm Rule at {sahm:.2f}, well below recession thresholds.")

        # Yield curve
        spread_10y2y = spreads.get("10y2y")
        if spread_10y2y is not None:
            bps = spread_10y2y * 100
            if bps > 50:
                parts.append(f"The yield curve is normally sloped with the 10Y-2Y spread at +{bps:.0f}bps.")
            elif bps > 0:
                parts.append(f"The yield curve is relatively flat with the 10Y-2Y spread at +{bps:.0f}bps.")
            elif bps > -50:
                parts.append(f"The yield curve is partially inverted with the 10Y-2Y spread at {bps:.0f}bps.")
            else:
                parts.append(f"The yield curve is deeply inverted at {bps:.0f}bps, a historically reliable recession signal.")

        # Credit
        credit = snapshot.get("credit_stress", "NORMAL")
        if credit == "NORMAL":
            parts.append("Credit markets are calm with spreads at normal levels.")
        elif credit == "ELEVATED":
            parts.append("Credit spreads are widening, signaling some corporate stress.")
        else:
            parts.append("Credit markets are under significant stress with wide spreads.")

        # Policy
        real_ff = derived.get("real_fed_funds")
        if real_ff is not None:
            if real_ff > 2.0:
                parts.append(f"Monetary policy is restrictive with real Fed Funds at {real_ff:.1f}%.")
            elif real_ff > 0.5:
                parts.append(f"Policy is mildly restrictive with real Fed Funds at {real_ff:.1f}%.")
            elif real_ff > -0.5:
                parts.append(f"Policy is approximately neutral with real Fed Funds at {real_ff:.1f}%.")
            else:
                parts.append(f"Policy is accommodative with real Fed Funds at {real_ff:.1f}%.")

        return " ".join(parts)
