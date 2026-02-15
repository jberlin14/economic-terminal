"""
Conversational AI Chat Engine

Provides institutional-grade economic analysis through multi-turn conversation.
Every request includes a comprehensive market snapshot so the AI maintains
a full macro worldview, plus deep topic-specific data for the user's question.
"""

import os
import time
import uuid
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


# ──────────────────────────────────────────────
# Topic Detection
# ──────────────────────────────────────────────

TOPIC_KEYWORDS = {
    "yields": ["yield", "treasury", "bond", "curve", "spread", "10y", "2y", "30y", "rates", "duration", "tips", "tenor", "fixed income"],
    "fx": ["fx", "dollar", "euro", "yen", "currency", "eur/usd", "usd", "dxy", "forex", "exchange rate", "peso", "real", "yuan", "sterling", "pound", "franc", "emerging market curr"],
    "credit": ["credit", "oas", "ig", "hy", "high yield", "investment grade", "cds", "default", "corporate bond", "bbb", "ccc", "junk bond"],
    "labor": ["jobs", "employment", "unemployment", "payroll", "nfp", "labor", "claims", "jolts", "hiring", "wages", "hourly earnings", "participation", "workforce", "layoff"],
    "inflation": ["inflation", "cpi", "pce", "prices", "deflation", "core", "transitory", "shelter", "rent", "food price", "energy price", "ppi", "producer price", "disinflation"],
    "fed": ["fed", "fomc", "powell", "rate cut", "rate hike", "monetary", "tightening", "easing", "qe", "qt", "federal funds", "fed funds", "dot plot", "neutral rate"],
    "growth": ["gdp", "growth", "recession", "expansion", "output", "industrial", "manufacturing", "pmi", "retail sales", "consumer spending", "soft landing", "hard landing"],
    "equities": ["stock", "equity", "s&p", "sp500", "nasdaq", "dow", "market", "rally", "correction", "earnings", "pe ratio", "vix", "volatility", "risk appetite"],
    "news": ["news", "headline", "event", "latest", "today", "recent", "breaking", "geopolitical", "what happened", "what's going on", "update"],
    "housing": ["housing", "home", "mortgage", "real estate", "starts", "permits", "construction", "home price"],
    "consumer": ["consumer", "sentiment", "confidence", "spending", "saving", "personal income", "savings rate", "retail"],
    "trade": ["trade", "export", "import", "tariff", "deficit", "surplus", "balance of trade", "trade war", "sanction"],
    "global": ["global", "world", "china", "europe", "japan", "emerging", "boj", "ecb", "boe", "pboc", "geopolitic", "war", "conflict"],
}

# Comprehensive indicator map: topic -> [(series_id, display_label)]
INDICATOR_MAP = {
    "labor": [
        ("UNRATE", "Unemployment Rate (%)"),
        ("PAYEMS", "Total Nonfarm Payrolls (K)"),
        ("ICSA", "Initial Jobless Claims"),
        ("CCSA", "Continuing Claims"),
        ("CIVPART", "Labor Force Participation Rate (%)"),
        ("EMRATIO", "Employment-Population Ratio (%)"),
        ("CES0500000003", "Avg Hourly Earnings ($/hr)"),
        ("AWHAETP", "Avg Weekly Hours"),
    ],
    "inflation": [
        ("CPIAUCSL", "CPI All Items (index)"),
        ("CPILFESL", "Core CPI ex Food & Energy (index)"),
        ("CUSR0000SAH1", "CPI Shelter (index)"),
        ("CPIENGSL", "CPI Energy (index)"),
        ("CPIUFDSL", "CPI Food (index)"),
        ("PCEPI", "PCE Price Index"),
        ("PCEPILFE", "Core PCE ex Food & Energy"),
        ("PPIFES", "PPI Final Demand"),
        ("PPIACO", "PPI All Commodities"),
    ],
    "fed": [
        ("FEDFUNDS", "Federal Funds Rate (%)"),
        ("DGS10", "10-Year Treasury Yield (%)"),
        ("DGS2", "2-Year Treasury Yield (%)"),
        ("T10Y2Y", "10Y-2Y Treasury Spread (%)"),
    ],
    "growth": [
        ("GDP", "Nominal GDP (B)"),
        ("GDPC1", "Real GDP (B)"),
        ("A191RL1Q225SBEA", "Real GDP Growth SAAR (%)"),
        ("INDPRO", "Industrial Production Index"),
        ("RSXFS", "Retail Sales ex Food Svc"),
    ],
    "housing": [
        ("HOUST", "Housing Starts (K)"),
    ],
    "consumer": [
        ("UMCSENT", "U of Mich Consumer Sentiment"),
        ("PCE", "Personal Consumption (B)"),
        ("PI", "Personal Income (B)"),
        ("PSAVERT", "Personal Savings Rate (%)"),
        ("RSXFS", "Retail Sales ex Food Svc"),
    ],
    "trade": [
        ("PPIIDC", "PPI Intermediate Services"),
        ("PPIACO", "PPI All Commodities"),
        ("PPIFES", "PPI Final Demand"),
    ],
}

# Key indicators for the always-on market snapshot
SNAPSHOT_INDICATORS = [
    ("UNRATE", "Unemployment"),
    ("FEDFUNDS", "Fed Funds Rate"),
    ("CPIAUCSL", "CPI Index"),
    ("CPILFESL", "Core CPI Index"),
    ("PCEPI", "PCE Price Index"),
    ("PCEPILFE", "Core PCE Index"),
    ("A191RL1Q225SBEA", "Real GDP Growth (%)"),
    ("ICSA", "Initial Claims"),
    ("PAYEMS", "Nonfarm Payrolls (K)"),
    ("DGS10", "10Y Yield (%)"),
    ("DGS2", "2Y Yield (%)"),
    ("T10Y2Y", "10Y-2Y Spread (%)"),
    ("PSAVERT", "Savings Rate (%)"),
    ("UMCSENT", "Consumer Sentiment"),
    ("INDPRO", "Industrial Production"),
]

SYSTEM_PROMPT = """You are an elite macro strategist and economic analyst embedded in a professional institutional-grade market monitoring terminal. You synthesize data across all asset classes and economic indicators to provide comprehensive, nuanced analysis.

## Your Analytical Framework

**Cross-Asset Synthesis**: You always connect dots across rates, FX, credit, equities, and economic data. A move in treasuries implies something about Fed expectations, which connects to dollar strength, which affects EM currencies and commodities.

**Regime Awareness**: You maintain a running assessment of the macro regime — are we in expansion, late cycle, slowdown, recession, or recovery? Every data point gets interpreted through this lens.

**Policy Transmission**: You understand how monetary policy flows through the economy — from Fed funds rate → short-term rates → yield curve → credit conditions → real economy → employment → inflation → back to Fed. You track where we are in this cycle.

**Global Interconnections**: US macro doesn't exist in isolation. You consider: ECB/BOJ/BOE policy divergence, China's growth trajectory, EM stress signals, energy markets, geopolitical risk premia, and global trade flows.

**Historical Pattern Recognition**: You naturally reference historical parallels when relevant — prior tightening cycles, recession indicators (Sahm rule, yield curve inversion lead times), policy pivots, and market regime transitions.

**Forward-Looking Orientation**: While grounding analysis in current data, you always push toward what the data implies for the next 3-12 months. What are the base case, upside risk, and downside risk scenarios?

**Theoretical Grounding**: When a THEORETICAL FRAMEWORK section is provided, follow its Analytical Persona instructions precisely — the depth tier (Executive Brief / Analyst / Research) determines your voice and analytical depth. At Executive level, be decisive and cite theory only to sharpen calls. At Analyst level, cite frameworks by name and connect data to predictions. At Research level, apply complete theoretical mechanisms and analyze incentive structures exhaustively.

## Response Guidelines

- **Depth**: Provide substantive analysis, not surface-level summaries. The user is a professional who wants institutional-quality insight.
- **Data-Grounded**: Reference specific numbers from the data provided. "Unemployment at 4.3% vs 3.4% a year ago suggests..."
- **Theory-Informed**: Ground your interpretation in the theoretical frameworks provided. Don't just describe what happened — explain WHY it matters through the lens of economic theory, political economy, and incentive analysis.
- **Nuanced**: Avoid one-dimensional takes. Good analysis explores tensions and contradictions in the data.
- **Actionable**: Connect macro observations to market/portfolio implications where relevant.
- **Honest Uncertainty**: When the data is ambiguous or conflicting, say so. Flag what would resolve the uncertainty.
- **Length**: Aim for 3-5 substantive paragraphs. Go longer if the question demands it. Never be superficial to be brief.
- For index-level data (CPI, PCE), compute and discuss year-over-year or month-over-month changes rather than quoting raw index values.
- When multiple signals conflict, explicitly discuss the tension rather than picking a side.

## Writing Style (MANDATORY)

- Write in clear, flowing prose. Each paragraph develops one complete idea.
- Use direct, declarative sentences. State your conclusion first, then support it.
- NEVER use dashes or em-dashes to join clauses mid-sentence. Write separate sentences.
- NEVER use triple-clause constructions ("not X, but Y, and Z"). Use simple subject-verb-object structures.
- NEVER front-load with hedging phrases ("it is worth noting," "one might argue," "it bears mentioning," "perhaps most notably").
- Avoid AI-isms: no "it's important to note," "one cannot overstate," "the key takeaway here is."
- Do not start consecutive sentences with the same word or structure.
- Write like a Goldman Sachs or JPMorgan morning note: confident, precise, economical with words."""

SESSION_TTL_MINUTES = 30
MAX_HISTORY_TURNS = 20


class ChatEngine:
    """Multi-turn conversational AI for economic analysis."""

    _sessions: Dict[str, Dict[str, Any]] = {}

    def __init__(self, db: Session, api_key: Optional[str] = None):
        self.db = db
        self.helper = QueryHelper(db)
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        self._client = None

    def is_available(self) -> bool:
        return ANTHROPIC_AVAILABLE and bool(self.api_key)

    def _get_client(self):
        if not self._client and self.is_available():
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    async def chat(self, message: str, session_id: Optional[str] = None, theory_depth: str = "analyst") -> Dict[str, Any]:
        """Process a chat message and return AI response with analytical lens metadata."""
        start = time.time()

        if not self.is_available():
            return {
                "response": "AI chat is unavailable. Please configure the ANTHROPIC_API_KEY environment variable.",
                "session_id": session_id or "none",
                "error": "api_key_missing",
            }

        self._cleanup_sessions()

        if not session_id or session_id not in self._sessions:
            session_id = str(uuid.uuid4())
            self._sessions[session_id] = {
                "history": [],
                "last_active": get_current_time(),
                "created_at": get_current_time().isoformat(),
            }

        session = self._sessions[session_id]
        session["last_active"] = get_current_time()

        # Always build comprehensive context
        topics = self._detect_topics(message)
        market_snapshot = self._build_market_snapshot()
        topic_deep_dive = self._gather_topic_data(topics)

        context_parts = [market_snapshot]
        if topic_deep_dive:
            context_parts.append(topic_deep_dive)

        context_data = "\n\n".join(p for p in context_parts if p)

        # Build theory context based on conditions (returns tuple now)
        theory_block, analytical_lens = self._build_theory_context(topics, depth=theory_depth)

        messages = list(session["history"])

        user_content = message
        if context_data:
            parts = [
                f"[COMPREHENSIVE MARKET BRIEFING — {get_current_time().strftime('%Y-%m-%d %H:%M ET')}]",
                context_data,
            ]
            if theory_block:
                parts.append(theory_block)
            parts.append(f"[USER QUESTION]\n{message}")
            user_content = "\n\n".join(parts)

        messages.append({"role": "user", "content": user_content})

        try:
            client = self._get_client()
            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2000,
                messages=messages,
                system=SYSTEM_PROMPT,
            )

            assistant_text = response.content[0].text
            tokens_used = response.usage.input_tokens + response.usage.output_tokens

            session["history"].append({"role": "user", "content": message})
            session["history"].append({"role": "assistant", "content": assistant_text})

            if len(session["history"]) > MAX_HISTORY_TURNS * 2:
                session["history"] = session["history"][-(MAX_HISTORY_TURNS * 2):]

            elapsed_ms = round((time.time() - start) * 1000)

            result = {
                "response": assistant_text,
                "session_id": session_id,
                "tokens_used": tokens_used,
                "elapsed_ms": elapsed_ms,
                "topics_detected": topics,
                "turn_count": len(session["history"]) // 2,
            }

            # Include analytical lens metadata if theories were applied
            if analytical_lens:
                result["analytical_lens"] = analytical_lens

            return result

        except Exception as e:
            logger.error(f"Chat generation error: {e}")
            return {
                "response": "I encountered an error processing your request. Please try again.",
                "session_id": session_id,
                "error": str(e),
            }

    def get_sessions(self) -> List[Dict[str, Any]]:
        self._cleanup_sessions()
        return [
            {
                "session_id": sid,
                "turn_count": len(session["history"]) // 2,
                "created_at": session.get("created_at"),
                "last_active": session["last_active"].isoformat(),
            }
            for sid, session in self._sessions.items()
        ]

    # ──────────────────────────────────────────────
    # Always-On Market Snapshot (sent with every request)
    # ──────────────────────────────────────────────

    def _build_market_snapshot(self) -> str:
        """Build comprehensive analytics-powered market snapshot.

        Uses the shared analytics engine for pre-computed metrics (trends,
        derived indicators, regime), the market journal for cross-day memory,
        and the change detector for "what moved" context.
        """
        try:
            from modules.market_summary.analytics_engine import (
                gather_market_context, compute_analytics,
                build_indicator_snapshot, format_compact_briefing
            )
            from modules.market_summary.journal import MarketJournal
            from modules.market_summary.change_detector import detect_changes

            # Phase 1: Gather raw data and compute analytics
            context = gather_market_context(self.db)
            analytics = compute_analytics(context, self.db)

            # Phase 2: Build structured snapshot
            snapshot = build_indicator_snapshot(context, analytics)

            # Phase 3: Journal — ensure today's entry exists, get prior for diff
            journal = MarketJournal(self.db)
            today_entry = journal.get_today()
            if not today_entry:
                today_entry = journal.create_or_update_today()

            recent_entries = journal.get_recent(days=5)
            # Prior entry is the most recent one that isn't today
            prior_entry = None
            for entry in recent_entries:
                if entry.date != today_entry.date if today_entry else True:
                    prior_entry = entry
                    break

            # Phase 4: Change detection
            changes = detect_changes(snapshot, prior_entry)

            # Phase 5: Format compact briefing
            briefing = format_compact_briefing(
                context, analytics,
                journal_entries=recent_entries[:5],
                changes=changes,
            )

            return briefing

        except Exception as e:
            logger.warning(f"Analytics-powered snapshot failed, falling back to basic: {e}")
            import traceback
            traceback.print_exc()
            return self._build_basic_snapshot()

    def _build_basic_snapshot(self) -> str:
        """Fallback snapshot using raw data (no analytics engine)."""
        sections = []

        # Regime
        try:
            from modules.regime_detector import RegimeDetector
            detector = RegimeDetector(self.db)
            regime = detector.assess_regime()
            sections.append(f"REGIME: {regime['regime']} — {regime['regime_description']}")
        except Exception:
            pass

        # Key indicators (raw values)
        try:
            from modules.economic_indicators import IndicatorStorage
            storage = IndicatorStorage(self.db)
            lines = ["KEY INDICATORS:"]
            for series_id, label in SNAPSHOT_INDICATORS:
                latest = storage.get_latest_value(series_id)
                if latest and latest.get("value") is not None:
                    lines.append(f"  {label}: {latest['value']} [{latest.get('date', '?')}]")
            if len(lines) > 1:
                sections.append("\n".join(lines))
        except Exception:
            pass

        # Yields
        try:
            yc = self.helper.get_latest_yield_curve()
            if yc:
                sections.append(
                    f"YIELDS: 2Y: {yc.tenor_2y}% | 10Y: {yc.tenor_10y}% | "
                    f"30Y: {yc.tenor_30y}% | 10Y-2Y: {yc.spread_10y2y}%"
                )
        except Exception:
            pass

        # Equities
        try:
            import yfinance as yf
            import pandas as pd
            eq_parts = []
            for ticker, label in [("^GSPC", "S&P"), ("^VIX", "VIX")]:
                data = yf.download(ticker, period="5d", progress=False, auto_adjust=True)
                if len(data) > 0:
                    close = data["Close"]
                    if isinstance(close, pd.DataFrame):
                        close = close.iloc[:, 0]
                    eq_parts.append(f"{label}: {float(close.iloc[-1]):,.0f}")
            if eq_parts:
                sections.append("EQUITIES: " + " | ".join(eq_parts))
        except Exception:
            pass

        return "\n\n".join(sections) if sections else ""

    # ──────────────────────────────────────────────
    # Theory Context (academic framework injection)
    # ──────────────────────────────────────────────

    def _build_theory_context(self, topics: List[str], depth: str = "analyst") -> tuple:
        """Build theory context based on current conditions and detected topics.

        Loads relevant economic/political economy/geopolitical theory documents
        and injects them into the prompt so the AI applies formal frameworks.

        Returns:
            Tuple of (theory_block_str, analytical_lens_dict)
        """
        try:
            from modules.theory_library import get_theory_context

            # Get current regime
            regime = None
            try:
                from modules.regime_detector import RegimeDetector
                detector = RegimeDetector(self.db)
                regime_data = detector.assess_regime()
                regime = regime_data.get("regime")
            except Exception:
                pass

            # Get recent news event types for theory selection
            news_events = []
            try:
                from modules.data_storage.schema import NewsArticle as NewsArticleDB
                from datetime import timedelta
                cutoff = get_current_time() - timedelta(hours=24)
                recent_articles = (
                    self.db.query(NewsArticleDB)
                    .filter(
                        NewsArticleDB.published_at >= cutoff,
                        NewsArticleDB.severity.in_(["CRITICAL", "HIGH"]),
                    )
                    .all()
                )
                for article in recent_articles:
                    if article.event_types:
                        news_events.extend(article.event_types)
                news_events = list(set(news_events))
            except Exception:
                pass

            theory_block, lens = get_theory_context(
                depth=depth,
                topics=topics,
                regime=regime,
                news_events=news_events,
            )
            return theory_block, lens

        except Exception as e:
            logger.debug(f"Theory context failed: {e}")
            return "", {}

    # ──────────────────────────────────────────────
    # Topic-Specific Deep Dive (additional detail for detected topics)
    # ──────────────────────────────────────────────

    def _detect_topics(self, message: str) -> List[str]:
        message_lower = message.lower()
        detected = []
        for topic, keywords in TOPIC_KEYWORDS.items():
            for keyword in keywords:
                if keyword in message_lower:
                    detected.append(topic)
                    break
        return detected

    def _gather_topic_data(self, topics: List[str]) -> str:
        """Gather deep-dive data for specifically detected topics."""
        if not topics:
            return ""

        sections = []

        # Full yield curve detail
        if "yields" in topics:
            try:
                yc = self.helper.get_latest_yield_curve()
                if yc:
                    sections.append(
                        f"DETAILED YIELD CURVE:\n"
                        f"  1M: {yc.tenor_1m}%  |  3M: {yc.tenor_3m}%  |  6M: {yc.tenor_6m}%  |  1Y: {yc.tenor_1y}%\n"
                        f"  2Y: {yc.tenor_2y}%  |  5Y: {yc.tenor_5y}%  |  10Y: {yc.tenor_10y}%  |  "
                        f"20Y: {yc.tenor_20y}%  |  30Y: {yc.tenor_30y}%\n"
                        f"  Spreads: 10Y-2Y: {yc.spread_10y2y}%  |  10Y-3M: {yc.spread_10y3m}%  |  "
                        f"30Y-10Y: {yc.spread_30y10y}%\n"
                        f"  TIPS: 5Y Real: {yc.tips_5y}%  |  10Y Real: {yc.tips_10y}%"
                    )
            except Exception as e:
                logger.debug(f"Topic yields error: {e}")

        # Full FX detail
        if "fx" in topics:
            try:
                fx_rates = self.helper.get_latest_fx_rates()
                if fx_rates:
                    lines = ["DETAILED FX RATES:"]
                    for r in fx_rates:
                        chg_parts = []
                        if r.change_1h is not None:
                            chg_parts.append(f"1h: {r.change_1h:+.2f}%")
                        if r.change_24h is not None:
                            chg_parts.append(f"24h: {r.change_24h:+.2f}%")
                        if r.change_1w is not None:
                            chg_parts.append(f"1w: {r.change_1w:+.2f}%")
                        if r.change_ytd is not None:
                            chg_parts.append(f"YTD: {r.change_ytd:+.2f}%")
                        chg_str = " | ".join(chg_parts) if chg_parts else ""
                        lines.append(f"  {r.pair}: {r.rate} ({chg_str})")
                    sections.append("\n".join(lines))
            except Exception as e:
                logger.debug(f"Topic FX error: {e}")

        # Full credit detail
        if "credit" in topics:
            try:
                spreads = self.helper.get_latest_credit_spreads()
                if spreads:
                    lines = ["DETAILED CREDIT SPREADS:"]
                    for s in spreads:
                        parts = [f"{s.spread_bps:.0f}bps"]
                        if s.avg_30d:
                            parts.append(f"30d avg: {s.avg_30d:.0f}")
                        if s.avg_90d:
                            parts.append(f"90d avg: {s.avg_90d:.0f}")
                        if s.change_1d is not None:
                            parts.append(f"1d: {s.change_1d:+.1f}")
                        if s.change_1w is not None:
                            parts.append(f"1w: {s.change_1w:+.1f}")
                        if s.percentile_90d is not None:
                            parts.append(f"90d pctile: {s.percentile_90d:.0f}th")
                        if s.percentile_1y is not None:
                            parts.append(f"1Y pctile: {s.percentile_1y:.0f}th")
                        lines.append(f"  {s.index_name}: {' | '.join(parts)}")
                    sections.append("\n".join(lines))
            except Exception as e:
                logger.debug(f"Topic credit error: {e}")

        # Deep indicator data for economic topics
        indicator_topics = [t for t in topics if t in INDICATOR_MAP]
        if indicator_topics:
            try:
                from modules.economic_indicators import IndicatorStorage
                storage = IndicatorStorage(self.db)

                lines = ["DETAILED ECONOMIC DATA:"]
                seen = set()
                for topic in indicator_topics:
                    for series_id, label in INDICATOR_MAP.get(topic, []):
                        if series_id in seen:
                            continue
                        seen.add(series_id)
                        latest = storage.get_latest_value(series_id)
                        if latest and latest.get("value") is not None:
                            lines.append(f"  {label} ({series_id}): {latest['value']} [as of {latest.get('date', '?')}]")

                if len(lines) > 1:
                    sections.append("\n".join(lines))
            except Exception as e:
                logger.debug(f"Topic indicators error: {e}")

        # Playbook matches (for macro/regime questions)
        if any(t in topics for t in ["growth", "fed", "global"]):
            try:
                from modules.playbook_matcher import PlaybookMatcher
                matcher = PlaybookMatcher(self.db)
                result = matcher.match()
                if result.get("matches"):
                    lines = ["HISTORICAL PLAYBOOK MATCHES:"]
                    for m in result["matches"][:3]:
                        lines.append(
                            f"  {m['episode_name']} ({m['period']}): {m['similarity_pct']}% match — "
                            f"{m['matching_count']}/{m['total_signals']} signals"
                        )
                    details = result.get("current_conditions", {}).get("details", {})
                    if details:
                        lines.append(f"  Current: {details}")
                    sections.append("\n".join(lines))
            except Exception as e:
                logger.debug(f"Topic playbook error: {e}")

        # Category-filtered news for specific topics
        if "news" in topics or "global" in topics:
            try:
                from modules.data_storage.schema import NewsArticle
                # Get more news with category filtering
                articles = (
                    self.db.query(NewsArticle)
                    .order_by(NewsArticle.published_at.desc())
                    .limit(25)
                    .all()
                )
                if articles:
                    lines = [f"EXPANDED NEWS ({len(articles)} recent):"]
                    for a in articles:
                        cat = f" [{a.category}]" if a.category else ""
                        ts = a.published_at.strftime("%m/%d %H:%M") if a.published_at else ""
                        src = f" — {a.source}" if a.source else ""
                        leaders = ""
                        if a.leader_mentions:
                            leaders = f" (mentions: {', '.join(a.leader_mentions[:3])})"
                        institutions = ""
                        if a.institutions:
                            institutions = f" [inst: {', '.join(a.institutions[:3])}]"
                        lines.append(f"  {a.severity}{cat}: {a.headline}{leaders}{institutions}{src} [{ts}]")
                    sections.append("\n".join(lines))
            except Exception as e:
                logger.debug(f"Topic news error: {e}")

        return "\n\n".join(sections) if sections else ""

    def _cleanup_sessions(self):
        now = get_current_time()
        expired = [
            sid for sid, session in self._sessions.items()
            if (now - session["last_active"]) > timedelta(minutes=SESSION_TTL_MINUTES)
        ]
        for sid in expired:
            del self._sessions[sid]
