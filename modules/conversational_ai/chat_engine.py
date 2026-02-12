"""
Chat Engine for Conversational AI Layer

Handles multi-turn conversations about economic data with full context awareness.
Uses the same data gathering infrastructure as the narrative generator but adds
conversational memory and question-specific data retrieval.
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


CHAT_SYSTEM_PROMPT = """You are an expert economic analyst embedded in a real-time market monitoring terminal.
You have access to live economic data, yield curves, FX rates, credit spreads, news feeds, and historical indicators.

**Your role:**
- Answer questions about current market conditions using the data provided
- Explain economic relationships and implications
- Compare current conditions to historical periods
- Provide actionable insights grounded in data
- Be direct and quantitative — cite specific numbers, dates, and changes

**Rules:**
- Always ground your answers in the data context provided
- If data is insufficient to answer a question, say so explicitly
- Use precise numbers — don't round unless the precision is spurious
- When comparing periods, specify exact dates and values
- For forward-looking statements, clearly label them as analysis/opinion
- Keep responses concise (150-300 words) unless the user asks for detail
- Never fabricate data points — only reference what's in the context

**Tone:** Professional, direct, quantitative. Like a senior desk analyst answering a PM's question."""


class ConversationSession:
    """Manages a single conversation session with message history."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages: List[Dict[str, str]] = []
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()

    def add_user_message(self, content: str):
        self.messages.append({"role": "user", "content": content})
        self.last_activity = datetime.utcnow()

    def add_assistant_message(self, content: str):
        self.messages.append({"role": "assistant", "content": content})
        self.last_activity = datetime.utcnow()

    def get_messages(self, max_turns: int = 10) -> List[Dict[str, str]]:
        """Get recent message history, trimmed to max_turns pairs."""
        # Keep the last N message pairs (user+assistant)
        if len(self.messages) > max_turns * 2:
            return self.messages[-(max_turns * 2):]
        return self.messages

    def is_expired(self, ttl_minutes: int = 60) -> bool:
        age = (datetime.utcnow() - self.last_activity).total_seconds() / 60
        return age > ttl_minutes


class ChatEngine:
    """
    Conversational AI engine for interrogating economic data.

    Maintains conversation sessions and provides context-aware responses
    using the same data infrastructure as the narrative generator.
    """

    _sessions: Dict[str, ConversationSession] = {}
    _max_sessions = 100
    _session_ttl_minutes = 60

    def __init__(self, db: Session, api_key: Optional[str] = None):
        self.db = db
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        self._client = None

    def is_available(self) -> bool:
        return ANTHROPIC_AVAILABLE and bool(self.api_key)

    def _get_client(self):
        if not self._client and self.is_available():
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def _get_or_create_session(self, session_id: Optional[str] = None) -> ConversationSession:
        """Get existing session or create a new one."""
        self._cleanup_expired_sessions()

        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            if not session.is_expired(self._session_ttl_minutes):
                return session

        # Create new session
        new_id = session_id or str(uuid.uuid4())[:8]
        session = ConversationSession(new_id)
        self._sessions[new_id] = session
        return session

    def _cleanup_expired_sessions(self):
        """Remove expired sessions."""
        expired = [
            sid for sid, s in self._sessions.items()
            if s.is_expired(self._session_ttl_minutes)
        ]
        for sid in expired:
            del self._sessions[sid]

        # Evict oldest if over limit
        if len(self._sessions) > self._max_sessions:
            sorted_sessions = sorted(
                self._sessions.items(),
                key=lambda x: x[1].last_activity
            )
            for sid, _ in sorted_sessions[:len(self._sessions) - self._max_sessions]:
                del self._sessions[sid]

    def _gather_data_context(self, question: str) -> str:
        """
        Gather relevant data context based on the user's question.
        Uses keyword matching to pull in the right data sections.
        """
        from modules.market_summary.ai_narrative import AIMarketNarrative

        narrative_gen = AIMarketNarrative(self.db, self.api_key)
        context = narrative_gen._gather_context()
        analytics = narrative_gen._compute_analytics(context)

        lines = []
        lines.append(f"=== CURRENT MARKET DATA (as of {context['timestamp']}) ===")
        lines.append("")

        q_lower = question.lower()

        # Always include regime
        regime = analytics.get("regime", {})
        lines.append(f"Market Regime: {regime.get('regime', 'UNKNOWN')}")
        signals = regime.get("signals", {})
        signal_str = ", ".join(f"{k}: {v}" for k, v in signals.items())
        lines.append(f"Regime Signals: {signal_str}")
        lines.append("")

        # Include indicators based on question relevance
        indicators = context.get("indicators", {})
        yield_keywords = ['yield', 'curve', 'spread', 'treasury', 'bond', '10y', '2y', '2s10s',
                          'steepen', 'flatten', 'invert', 'term premium', 'tips', 'breakeven']
        fx_keywords = ['fx', 'currency', 'dollar', 'usd', 'eur', 'jpy', 'gbp', 'peso', 'real',
                       'dxy', 'exchange rate', 'forex']
        credit_keywords = ['credit', 'spread', 'ig', 'hy', 'high yield', 'investment grade',
                           'oas', 'corporate bond', 'default']
        labor_keywords = ['job', 'employ', 'labor', 'nfp', 'payroll', 'unemployment', 'claims',
                          'sahm', 'jolts', 'openings', 'hiring', 'wage']
        inflation_keywords = ['inflation', 'cpi', 'pce', 'price', 'deflation', 'disinflation',
                              'core inflation', 'shelter', 'rent']
        fed_keywords = ['fed', 'fomc', 'rate cut', 'rate hike', 'powell', 'monetary policy',
                        'taper', 'dovish', 'hawkish', 'fed funds', 'interest rate']
        growth_keywords = ['gdp', 'growth', 'recession', 'expansion', 'slowdown', 'output',
                           'industrial', 'retail', 'consumer', 'sentiment', 'housing']
        equity_keywords = ['equit', 'stock', 's&p', 'nasdaq', 'dow', 'vix', 'volatil',
                           'risk', 'rally', 'correction', 'bear', 'bull']
        news_keywords = ['news', 'headline', 'article', 'today', 'happen', 'event',
                         'announce', 'break', 'develop']

        include_all = any(kw in q_lower for kw in ['overview', 'summary', 'everything',
                                                      'market', 'what\'s going on', 'brief'])

        # Economic indicators
        if include_all or any(kw in q_lower for kw in labor_keywords + inflation_keywords +
                               fed_keywords + growth_keywords + equity_keywords):
            lines.append("=== KEY ECONOMIC INDICATORS ===")
            for series_id, data in indicators.items():
                val = data.get("value")
                if val is None:
                    continue
                name = data.get("name", series_id)
                units = data.get("units", "")
                date = data.get("date", "?")

                parts = [f"{name}: {val:.2f} ({units}) as of {date}"]
                if data.get("jobs_change_thousands") is not None:
                    parts.append(f"MoM: {data['jobs_change_thousands']:+.0f}K")
                elif data.get("prior_change_pct") is not None:
                    parts.append(f"MoM: {data['prior_change_pct']:+.2f}%")
                if data.get("yoy_change_pct") is not None:
                    parts.append(f"YoY: {data['yoy_change_pct']:+.2f}%")

                ind_a = analytics.get("indicators", {}).get(series_id, {})
                if isinstance(ind_a, dict) and ind_a.get("trend"):
                    parts.append(f"Trend: {ind_a['trend']}")

                lines.append("  " + " | ".join(parts))

            # Derived metrics
            derived = analytics.get("indicators", {}).get("_derived", {})
            if derived:
                if derived.get("real_fed_funds") is not None:
                    lines.append(f"  Real Fed Funds: {derived['real_fed_funds']:+.2f}%")
                if derived.get("sahm_rule") is not None:
                    triggered = "TRIGGERED" if derived.get("sahm_triggered") else "below trigger"
                    lines.append(f"  Sahm Rule: {derived['sahm_rule']:.2f} ({triggered})")
                if derived.get("cpi_yoy") is not None:
                    lines.append(f"  CPI YoY: {derived['cpi_yoy']:.2f}%")
            lines.append("")

        # Yields
        if include_all or any(kw in q_lower for kw in yield_keywords + fed_keywords):
            yields = context.get("yields", {})
            curve = yields.get("curve", {})
            if curve:
                lines.append("=== TREASURY YIELDS ===")
                curve_str = " | ".join(f"{t}: {curve[t]:.2f}%" for t in
                                        ['1M', '3M', '6M', '1Y', '2Y', '5Y', '10Y', '20Y', '30Y']
                                        if t in curve)
                lines.append(f"  {curve_str}")

                spreads = yields.get("spreads", {})
                if spreads:
                    spread_str = ", ".join(f"{k}: {v*100:+.0f}bps" for k, v in spreads.items())
                    lines.append(f"  Spreads: {spread_str}")

                yield_a = analytics.get("yields", {})
                if yield_a.get("shape"):
                    lines.append(f"  Shape: {yield_a['shape']}")
                if yield_a.get("steepening_trend"):
                    lines.append(f"  Trend: {yield_a['steepening_trend']}")

                wow = yield_a.get("wow_changes", {})
                if wow:
                    wow_str = ", ".join(f"{t}: {v:+.0f}" for t, v in wow.items())
                    lines.append(f"  WoW (bps): {wow_str}")

                be = yield_a.get("breakevens", {})
                if be:
                    be_str = ", ".join(f"{t}: {v:.2f}%" for t, v in be.items())
                    lines.append(f"  Breakevens: {be_str}")
                lines.append("")

        # FX
        if include_all or any(kw in q_lower for kw in fx_keywords):
            fx = context.get("fx", {})
            if fx:
                lines.append("=== FX RATES ===")
                fx_a = analytics.get("fx", {})
                if fx_a.get("usd_direction"):
                    lines.append(f"  USD: {fx_a['usd_direction']}")
                for pair, data in fx.items():
                    changes = []
                    for period in ['change_1h', 'change_24h', 'change_1w']:
                        v = data.get(period)
                        if v is not None:
                            label = period.replace('change_', '')
                            changes.append(f"{label}: {v:+.2f}%")
                    lines.append(f"  {pair}: {data['rate']:.4f} ({', '.join(changes)})")
                lines.append("")

        # Credit
        if include_all or any(kw in q_lower for kw in credit_keywords):
            credit = context.get("credit", {})
            if credit:
                lines.append("=== CREDIT SPREADS ===")
                credit_a = analytics.get("credit", {})
                lines.append(f"  Stress: {credit_a.get('stress_level', 'NORMAL')}")
                for name, data in credit.items():
                    spread = data.get("spread_bps")
                    if spread is not None:
                        parts = [f"{spread:.0f} bps"]
                        if data.get("change_1d") is not None:
                            parts.append(f"1d: {data['change_1d']:+.1f}")
                        if data.get("change_1w") is not None:
                            parts.append(f"1w: {data['change_1w']:+.1f}")
                        lines.append(f"  {name}: {' | '.join(parts)}")
                lines.append("")

        # News
        if include_all or any(kw in q_lower for kw in news_keywords + fed_keywords):
            news = context.get("news", [])
            news_a = analytics.get("news", {})
            priority = news_a.get("priority_headlines", [])
            if priority:
                lines.append("=== PRIORITY NEWS ===")
                for article in priority[:10]:
                    lines.append(f"  [{article.get('severity', '?')}] {article['title']} "
                                 f"({article.get('source', '?')}, {article.get('published', '?')})")
                lines.append("")
            elif news:
                lines.append("=== RECENT NEWS ===")
                for article in news[:8]:
                    lines.append(f"  [{article.get('severity', '?')}] {article['title']} "
                                 f"({article.get('source', '?')})")
                lines.append("")

        # Calendar
        calendar = context.get("calendar", [])
        if calendar and (include_all or any(kw in q_lower for kw in ['calendar', 'upcoming', 'release', 'schedule'])):
            lines.append("=== UPCOMING RELEASES ===")
            for r in calendar:
                lines.append(f"  {r['name']} ({r['date']}) - {r['importance']}")
            lines.append("")

        return "\n".join(lines)

    async def chat(
        self,
        question: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a user question and return a response with full context.

        Args:
            question: The user's question
            session_id: Optional session ID for conversation continuity

        Returns:
            Dict with response, session_id, metadata
        """
        start_time = time.time()

        if not self.is_available():
            return {
                "response": "AI chat is unavailable. Please configure ANTHROPIC_API_KEY.",
                "session_id": session_id or "none",
                "error": "api_key_missing"
            }

        session = self._get_or_create_session(session_id)

        try:
            # Gather relevant data context
            data_context = self._gather_data_context(question)

            # Build the contextual user message
            if len(session.messages) == 0:
                # First message — include full data context
                user_content = f"""Here is the current market data context:

{data_context}

User question: {question}"""
            else:
                # Follow-up — include refreshed data but reference prior conversation
                user_content = f"""Updated market data:

{data_context}

Follow-up question: {question}"""

            session.add_user_message(user_content)

            # Build messages for API call
            api_messages = session.get_messages(max_turns=8)

            client = self._get_client()
            message = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=800,
                system=CHAT_SYSTEM_PROMPT,
                messages=api_messages
            )

            response_text = message.content[0].text
            session.add_assistant_message(response_text)

            elapsed_ms = round((time.time() - start_time) * 1000, 2)

            return {
                "response": response_text,
                "session_id": session.session_id,
                "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
                "model": "claude-sonnet-4-5-20250929",
                "elapsed_ms": elapsed_ms,
                "conversation_turns": len(session.messages) // 2,
                "timestamp": get_current_time().isoformat()
            }

        except Exception as e:
            logger.error(f"Chat error: {e}", exc_info=True)
            return {
                "response": f"I encountered an error processing your question: {str(e)}",
                "session_id": session.session_id,
                "error": str(e),
                "timestamp": get_current_time().isoformat()
            }

    @classmethod
    def get_active_sessions(cls) -> Dict[str, Any]:
        """Get info about active chat sessions."""
        return {
            "active_sessions": len(cls._sessions),
            "sessions": [
                {
                    "session_id": s.session_id,
                    "turns": len(s.messages) // 2,
                    "created_at": s.created_at.isoformat(),
                    "last_activity": s.last_activity.isoformat(),
                }
                for s in cls._sessions.values()
                if not s.is_expired(cls._session_ttl_minutes)
            ]
        }
