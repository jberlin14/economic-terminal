"""
Shared Market Analytics Engine

Provides centralized access to pre-computed market analytics for both
the AIMarketNarrative generator and the ChatEngine. Delegates to
AIMarketNarrative's internal methods to avoid duplicating logic.
"""

import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from loguru import logger

from modules.utils.timezone import get_current_time


# Module-level cache for context + analytics results (Phase 2 §2.7 perf).
# `gather_market_context` is called by every dashboard, scorecard, and
# chat request — at ~3 page loads/min across multiple endpoints + tabs
# that's tens of redundant FRED-touching calls a minute. A 60-second TTL
# brings repeat calls down to ~1/min while staleness stays invisible at
# the dashboard's daily-grained view.
_context_cache: Dict[str, Any] = {"data": None, "timestamp": 0.0}
# Single-slot analytics cache keyed by id(context). We don't allow more
# than one entry — when gather_market_context returns a fresh context
# (TTL expired), the previous analytics entry is replaced. Multi-entry
# caching previously risked Python id() reuse: the GC could reclaim the
# old context's id, a fresh dict could land at the same address, and
# stale analytics would be served. Now: at most one entry, always
# matching the currently-cached context.
#
# Concurrency note: this cache is not lock-protected. Under uvicorn's
# default async worker model (single thread, cooperative scheduling),
# `compute_analytics` runs to completion without interleaving — the
# slot is consistent. Multi-process deployments (`--workers > 1`) get
# per-process caches and no cross-process race exists. Only a threaded
# WSGI deployment (e.g. gunicorn threaded workers) could observe
# overlapping `compute_analytics` calls; in that mode two writers may
# both compute the same context and the later writer's result wins,
# which is harmless (they computed the same input). Add a `threading.
# Lock` if the deployment changes to threaded workers.
_analytics_cache: Dict[str, Any] = {"context_id": None, "data": None}
_CACHE_TTL_SECONDS = 60


def gather_market_context(db: Session) -> Dict[str, Any]:
    """
    Gather all raw market data (indicators, yields, FX, credit, news, calendar).

    Returns a context dict consumable by compute_analytics(). A 60-second
    module-level cache absorbs the multi-endpoint stampede that occurs
    when dashboard / scorecard / chat all fetch within the same poll
    cycle. Delegates to AIMarketNarrative's data-gathering methods on
    cache miss.
    """
    from .ai_narrative import AIMarketNarrative

    now = time.time()
    cached = _context_cache.get("data")
    cached_at = _context_cache.get("timestamp", 0.0)
    if cached is not None and (now - cached_at) < _CACHE_TTL_SECONDS:
        return cached

    narrator = AIMarketNarrative(db)
    context = narrator._gather_context()
    _context_cache["data"] = context
    _context_cache["timestamp"] = now
    # Invalidate the analytics memo whenever the context changes so a
    # stale (id-aliased) entry can never be returned for a fresh context.
    _analytics_cache["context_id"] = None
    _analytics_cache["data"] = None
    return context


def compute_analytics(context: Dict[str, Any], db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Compute all pre-digested analytics from raw context.

    Returns analytics dict with: indicators (trends, derived metrics),
    yields (shape, WoW/MoM changes, breakevens), fx (DM/EM classification,
    USD direction), credit (stress levels), news (severity aggregation,
    priority headlines), regime (composite assessment).

    Memoized per-context-object: if the caller is reusing the cached
    context returned from `gather_market_context`, the analytics result
    is reused too — saving the per-request derivation cost.
    """
    from .ai_narrative import AIMarketNarrative

    cache_key = id(context)
    if (
        _analytics_cache["context_id"] == cache_key
        and _analytics_cache["data"] is not None
    ):
        return _analytics_cache["data"]

    # Create a narrator just to access its analytics methods
    # We pass db=None since analytics methods don't use self.db
    narrator = AIMarketNarrative.__new__(AIMarketNarrative)
    narrator.db = db
    narrator.api_key = None
    narrator._client = None
    narrator._last_narrative = None

    result = narrator._compute_analytics(context)
    _analytics_cache["context_id"] = cache_key
    _analytics_cache["data"] = result
    return result


def _sanitize_for_json(obj):
    """Convert numpy types to native Python types for JSON serialization."""
    import json

    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    else:
        try:
            import numpy as np
            if isinstance(obj, (np.integer,)):
                return int(obj)
            elif isinstance(obj, (np.floating,)):
                return float(obj)
            elif isinstance(obj, (np.bool_,)):
                return bool(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            pass
        return obj


def build_indicator_snapshot(context: Dict[str, Any], analytics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a compact JSON-serializable snapshot of current market state.

    This is what gets stored in AIMarketJournal.indicator_snapshot for
    cross-day comparison and change detection.
    """
    snapshot = {}

    # Indicator values with trends
    indicators = context.get("indicators", {})
    ind_analytics = analytics.get("indicators", {})

    for series_id, data in indicators.items():
        entry = {"value": data.get("value")}

        # Add trend from analytics
        trend_data = ind_analytics.get(series_id, {})
        if trend_data.get("trend"):
            entry["trend"] = trend_data["trend"]

        # Add change data
        if data.get("prior_level_change") is not None:
            entry["mom_change"] = round(data["prior_level_change"], 3)
        if data.get("prior_change_pct") is not None:
            entry["mom_pct"] = round(data["prior_change_pct"], 2)
        if data.get("yoy_change_pct") is not None:
            entry["yoy_pct"] = round(data["yoy_change_pct"], 2)
        if data.get("jobs_change_thousands") is not None:
            entry["jobs_mom_k"] = round(data["jobs_change_thousands"], 1)
        if data.get("date"):
            entry["date"] = str(data["date"])

        snapshot[series_id] = entry

    # Derived metrics
    derived = ind_analytics.get("_derived", {})
    snapshot["derived"] = {
        "real_fed_funds": derived.get("real_fed_funds"),
        "cpi_yoy": derived.get("cpi_yoy"),
        "sahm_rule": derived.get("sahm_rule"),
        "sahm_triggered": derived.get("sahm_triggered"),
    }

    # Yield curve shape
    yield_analytics = analytics.get("yields", {})
    snapshot["curve_shape"] = yield_analytics.get("shape")
    snapshot["steepening_trend"] = yield_analytics.get("steepening_trend")
    snapshot["breakevens"] = yield_analytics.get("breakevens", {})

    # Spreads
    yields = context.get("yields", {})
    snapshot["spreads"] = yields.get("spreads", {})

    # Credit stress
    credit_analytics = analytics.get("credit", {})
    snapshot["credit_stress"] = credit_analytics.get("stress_level", "NORMAL")

    # FX direction
    fx_analytics = analytics.get("fx", {})
    snapshot["usd_direction"] = fx_analytics.get("usd_direction")

    # Regime
    regime_data = analytics.get("regime", {})
    snapshot["regime"] = regime_data.get("regime")
    snapshot["regime_signals"] = regime_data.get("signals", {})

    return _sanitize_for_json(snapshot)


def format_compact_briefing(
    context: Dict[str, Any],
    analytics: Dict[str, Any],
    journal_entries: Optional[List] = None,
    changes: Optional[Dict] = None,
) -> str:
    """
    Format a compact pre-digested briefing for the chat engine.

    Unlike AIMarketNarrative's full prompt format, this is optimized for
    the chat context: shorter, all arithmetic pre-computed, includes
    change detection and journal history.
    """
    sections = []

    # ── Regime ──
    regime_data = analytics.get("regime", {})
    regime = regime_data.get("regime", "UNKNOWN")
    regime_labels = {
        "CRISIS": "Multiple critical stress signals. Crisis-level conditions.",
        "RISK_OFF": "Significant stress indicators. Defensive positioning warranted.",
        "CAUTIOUS": "Elevated risk signals. Increased monitoring recommended.",
        "RISK_ON": "No significant stress signals. Normal conditions.",
    }
    sections.append(f"REGIME: {regime} — {regime_labels.get(regime, '')}")

    # ── What Changed ──
    if changes and changes.get("has_prior"):
        from .change_detector import format_changes_section
        changes_text = format_changes_section(changes)
        if changes_text:
            sections.append(changes_text)

    # ── Key Indicators (pre-computed) ──
    indicators = context.get("indicators", {})
    ind_analytics = analytics.get("indicators", {})
    derived = ind_analytics.get("_derived", {})

    ind_lines = ["KEY INDICATORS (pre-computed):"]

    # Unemployment
    unrate = indicators.get("UNRATE", {})
    if unrate.get("value") is not None:
        trend = ind_analytics.get("UNRATE", {}).get("trend", "")
        mom = unrate.get("prior_level_change")
        sahm = derived.get("sahm_rule")
        parts = [f"{unrate['value']}%"]
        if mom is not None:
            parts.append(f"MoM: {mom:+.1f}pp")
        if trend:
            parts.append(f"Trend: {trend}")
        if sahm is not None:
            parts.append(f"Sahm: {sahm:.2f}")
        ind_lines.append(f"  Unemployment: {' | '.join(parts)}")

    # CPI YoY
    cpi_yoy = derived.get("cpi_yoy")
    if cpi_yoy is not None:
        cpi_trend = ind_analytics.get("CPIAUCSL", {}).get("trend", "")
        parts = [f"{cpi_yoy:.1f}%"]
        if cpi_trend:
            parts.append(f"Trend: {cpi_trend}")
        ind_lines.append(f"  CPI YoY: {' | '.join(parts)}")

    # Fed Funds + Real Rate
    ff = indicators.get("FEDFUNDS", {})
    if ff.get("value") is not None:
        real_rate = derived.get("real_fed_funds")
        parts = [f"{ff['value']}%"]
        if real_rate is not None:
            stance = "restrictive" if real_rate > 1 else "neutral" if real_rate > -0.5 else "accommodative"
            parts.append(f"Real Rate: {real_rate:+.2f}% ({stance})")
        ind_lines.append(f"  Fed Funds: {' | '.join(parts)}")

    # Nonfarm Payrolls (level is in thousands; MoM change = headline jobs number)
    payems = indicators.get("PAYEMS", {})
    if payems.get("value") is not None:
        jobs_chg = payems.get("jobs_change_thousands")
        trend = ind_analytics.get("PAYEMS", {}).get("trend", "")
        parts = [f"Total: {payems['value']/1000:.1f}M"]
        if jobs_chg is not None:
            parts.append(f"MoM change: {jobs_chg:+.0f}K")
        if trend:
            parts.append(f"Trend: {trend}")
        ind_lines.append(f"  Nonfarm Payrolls: {' | '.join(parts)}")

    # Initial Claims
    icsa = indicators.get("ICSA", {})
    if icsa.get("value") is not None:
        trend = ind_analytics.get("ICSA", {}).get("trend", "")
        parts = [f"{icsa['value']/1000:.0f}K"]
        if trend:
            parts.append(f"Trend: {trend}")
        ind_lines.append(f"  Initial Claims: {' | '.join(parts)}")

    # GDP
    gdp = indicators.get("GDP", {})
    if gdp.get("value") is not None:
        yoy = gdp.get("yoy_change_pct")
        parts = [f"{gdp['value']}"]
        if yoy is not None:
            parts.append(f"YoY: {yoy:+.1f}%")
        ind_lines.append(f"  GDP: {' | '.join(parts)}")

    # Consumer Sentiment
    umcsent = indicators.get("UMCSENT", {})
    if umcsent.get("value") is not None:
        trend = ind_analytics.get("UMCSENT", {}).get("trend", "")
        parts = [f"{umcsent['value']}"]
        if trend:
            parts.append(f"Trend: {trend}")
        ind_lines.append(f"  Consumer Sentiment: {' | '.join(parts)}")

    # Industrial Production
    indpro = indicators.get("INDPRO", {})
    if indpro.get("value") is not None:
        trend = ind_analytics.get("INDPRO", {}).get("trend", "")
        mom = indpro.get("prior_change_pct")
        parts = [f"{indpro['value']}"]
        if mom is not None:
            parts.append(f"MoM: {mom:+.1f}%")
        if trend:
            parts.append(f"Trend: {trend}")
        ind_lines.append(f"  Industrial Production: {' | '.join(parts)}")

    if len(ind_lines) > 1:
        sections.append("\n".join(ind_lines))

    # ── Yield Curve ──
    yield_analytics = analytics.get("yields", {})
    yields = context.get("yields", {})
    curve = yields.get("curve", {})
    spreads = yields.get("spreads", {})
    if curve:
        shape = yield_analytics.get("shape", "UNKNOWN")
        steep_trend = yield_analytics.get("steepening_trend", "")
        spread_chg = yield_analytics.get("spread_wow_change_bps")

        shape_parts = [shape]
        if steep_trend:
            shape_parts.append(steep_trend.lower())
        if spread_chg is not None:
            shape_parts.append(f"{spread_chg:+.0f}bps WoW")

        line = f"YIELD CURVE: {' | '.join(shape_parts)}"
        tenors = []
        for t in ['2Y', '5Y', '10Y', '30Y']:
            if t in curve:
                tenors.append(f"{t}: {curve[t]}%")
        if tenors:
            line += f"\n  {' | '.join(tenors)}"
        if spreads.get("10y2y") is not None:
            line += f"\n  10Y-2Y: {spreads['10y2y']}%"
        breakevens = yield_analytics.get("breakevens", {})
        if breakevens.get("10y") is not None:
            line += f" | Breakeven 10Y: {breakevens['10y']}%"
        sections.append(line)

    # ── Credit ──
    credit_analytics = analytics.get("credit", {})
    credit = context.get("credit", {})
    if credit:
        stress = credit_analytics.get("stress_level", "NORMAL")
        credit_parts = [f"CREDIT: {stress} stress"]
        for idx in ["US_IG", "US_HY"]:
            data = credit.get(idx, {})
            if data.get("spread_bps") is not None:
                avg = data.get("avg_90d")
                p = f"{idx}: {data['spread_bps']:.0f}bps"
                if avg:
                    p += f" (vs 90d avg {avg:.0f})"
                credit_parts.append(p)
        sections.append(" | ".join(credit_parts[:1]) + "\n  " + " | ".join(credit_parts[1:]) if len(credit_parts) > 1 else credit_parts[0])

    # ── FX ──
    fx_analytics = analytics.get("fx", {})
    fx = context.get("fx", {})
    if fx:
        usd_dir = fx_analytics.get("usd_direction", "STABLE")
        dm_avg = fx_analytics.get("dm_avg_24h")
        line = f"FX: USD {usd_dir}"
        if dm_avg is not None:
            line += f" (DM avg 24h: {dm_avg:+.2f}%)"
        # Add top 3 pairs
        top_pairs = []
        for pair in ["USD/EUR", "USD/JPY", "USD/GBP"]:
            data = fx.get(pair, {})
            if data.get("rate") is not None:
                chg = data.get("change_24h")
                p = f"{pair}: {data['rate']}"
                if chg is not None:
                    p += f" ({chg:+.2f}%)"
                top_pairs.append(p)
        if top_pairs:
            line += "\n  " + " | ".join(top_pairs)
        sections.append(line)

    # ── Equities + VIX (live) ──
    try:
        import yfinance as yf
        import pandas as pd
        eq_lines = ["EQUITIES & VOL:"]
        for ticker, label in [("^GSPC", "S&P 500"), ("^IXIC", "NASDAQ"), ("^DJI", "Dow"), ("^VIX", "VIX")]:
            try:
                data = yf.download(ticker, period="5d", progress=False, auto_adjust=True)
                if len(data) > 0:
                    close = data["Close"]
                    if isinstance(close, pd.DataFrame):
                        close = close.iloc[:, 0]
                    val = float(close.iloc[-1])
                    prev = float(close.iloc[-2]) if len(close) > 1 else val
                    chg = ((val - prev) / prev) * 100
                    fmt = f"{val:.1f}" if "VIX" in label else f"{val:,.0f}"
                    eq_lines.append(f"  {label}: {fmt} ({chg:+.2f}%)")
            except Exception:
                pass
        if len(eq_lines) > 1:
            sections.append("\n".join(eq_lines))
    except Exception:
        pass

    # ── Priority News ──
    news_analytics = analytics.get("news", {})
    priority = news_analytics.get("priority_headlines", [])
    if priority:
        lines = [f"MARKET-MOVING NEWS ({len(priority)} priority):"]
        for article in priority[:10]:
            cat = article.get("category", "")
            sev = article.get("severity", "")
            title = article.get("title", "")
            source = article.get("source", "")
            published = article.get("published", "")
            lines.append(f"  [{cat}/{sev}] {title} — {source} [{published}]")
        sections.append("\n".join(lines))

    # ── Prior Journal Assessments ──
    if journal_entries:
        lines = ["PRIOR ASSESSMENTS (journal):"]
        for entry in journal_entries[:3]:
            date_str = entry.date.strftime("%m/%d") if hasattr(entry, 'date') else "?"
            regime = getattr(entry, 'regime', '?')
            themes = getattr(entry, 'key_themes', []) or []
            theme_str = ", ".join(themes) if themes else "none"
            lines.append(f"  {date_str}: {regime} | {theme_str}")
        sections.append("\n".join(lines))

    return "\n\n".join(sections)
