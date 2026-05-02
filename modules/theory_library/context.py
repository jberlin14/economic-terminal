"""
Theory Context Loader

Selectively loads theory documents based on current market conditions,
detected topics, and regime classification. Supports three analytical depth tiers:

- "executive": Executive Brief — C-suite-ready conclusions. Key takeaways,
  directional calls, no formulas. Think: what does the CEO need to know?
- "analyst": Analyst Depth — Working-level analysis with frameworks applied.
  Cites theories by name, identifies signal confirmations/contradictions,
  actionable for portfolio/risk decisions. Think: sell-side research note.
- "research": Research Depth — Full academic treatment. Complete theoretical
  mechanisms, incentive deep-dives, cross-framework tensions, novel condition
  flagging. Think: Brookings/NBER working paper quality.

Theory documents use ## HIGH-LEVEL and ## RIGOROUS section markers internally.
The loader maps these to the three tiers:
  - executive  → HIGH-LEVEL section only (condensed)
  - analyst    → HIGH-LEVEL + key RIGOROUS subsections
  - research   → Full document (both sections)
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger

# Root directory for theory documents
THEORY_ROOT = Path(__file__).parent

# ──────────────────────────────────────────────
# Theory Document Registry
# ──────────────────────────────────────────────

THEORY_FILES = {
    # Economics (heavy coverage)
    "monetary_policy": "economics/monetary_policy.md",
    "yield_curve": "economics/yield_curve.md",
    "inflation": "economics/inflation.md",
    "business_cycles": "economics/business_cycles.md",
    "labor_markets": "economics/labor_markets.md",
    "fx_and_trade": "economics/fx_and_trade.md",

    # Political Economy
    "fiscal_policy": "political_economy/fiscal_policy.md",
    "central_bank_independence": "political_economy/central_bank_independence.md",
    "trade_policy": "political_economy/trade_policy.md",
    "sanctions": "political_economy/sanctions.md",

    # Geopolitics
    "great_power_competition": "geopolitics/great_power_competition.md",
    "energy_security": "geopolitics/energy_security.md",
    "supply_chain_risk": "geopolitics/supply_chain_risk.md",

    # Frameworks (interpretation guides)
    "signal_interpretation": "frameworks/signal_interpretation.md",
    "regime_mapping": "frameworks/regime_mapping.md",
}


# ──────────────────────────────────────────────
# Condition-Based Theory Selection Rules
# ──────────────────────────────────────────────

# Map: topic keyword → theory documents to load
TOPIC_THEORY_MAP = {
    "yields": ["yield_curve", "monetary_policy", "business_cycles"],
    "fx": ["fx_and_trade", "monetary_policy"],
    "credit": ["business_cycles", "yield_curve", "monetary_policy"],
    "labor": ["labor_markets", "business_cycles", "monetary_policy"],
    "inflation": ["inflation", "monetary_policy", "central_bank_independence"],
    "fed": ["monetary_policy", "central_bank_independence", "inflation"],
    "growth": ["business_cycles", "labor_markets", "fiscal_policy"],
    "equities": ["business_cycles", "monetary_policy"],
    "housing": ["monetary_policy", "business_cycles"],
    "consumer": ["business_cycles", "labor_markets", "inflation"],
    "trade": ["trade_policy", "fx_and_trade", "great_power_competition"],
    "global": ["great_power_competition", "fx_and_trade", "energy_security"],
    "news": [],  # News is too broad — theory selected by sub-topics
}

# Map: news event types → theory documents
EVENT_THEORY_MAP = {
    "RATE_DECISION": ["monetary_policy", "central_bank_independence", "yield_curve"],
    "TRADE_POLICY": ["trade_policy", "fx_and_trade", "great_power_competition"],
    "SANCTIONS": ["sanctions", "energy_security", "great_power_competition"],
    "MILITARY": ["great_power_competition", "energy_security", "supply_chain_risk"],
    "ELECTION": ["central_bank_independence", "fiscal_policy"],
    "ECONOMIC_DATA": ["business_cycles", "inflation", "labor_markets"],
    "MARKET_MOVE": ["business_cycles", "yield_curve"],
    "CURRENCY": ["fx_and_trade", "monetary_policy"],
    "DEBT_CREDIT": ["fiscal_policy", "business_cycles", "yield_curve"],
    "DISASTER": ["supply_chain_risk", "energy_security"],
}

# Map: regime → theory documents always loaded
REGIME_THEORY_MAP = {
    "RISK_ON": ["business_cycles", "monetary_policy"],
    "CAUTIOUS": ["yield_curve", "business_cycles", "labor_markets", "monetary_policy"],
    "RISK_OFF": ["business_cycles", "monetary_policy", "fiscal_policy", "inflation"],
    "CRISIS": ["business_cycles", "monetary_policy", "fiscal_policy", "sanctions"],
}

# Maximum theories to load per request (excludes signal_interpretation)
MAX_THEORIES_DEFAULT = 4
MAX_THEORIES_CHAT = 5
MAX_THEORIES_NARRATIVE = 3

# Depth tier definitions
VALID_DEPTHS = {"executive", "analyst", "research"}

# Backward compatibility mapping from old names
DEPTH_ALIASES = {
    "high-level": "executive",
    "rigorous": "research",
}

# Tier metadata for API consumers and frontend display
DEPTH_TIERS = {
    "executive": {
        "name": "Executive Brief",
        "description": "C-suite-ready conclusions and directional calls",
        "persona": "You are briefing the CEO and CIO. Be decisive. Lead with conclusions, not process. Every sentence must earn its place.",
        "max_theories": 3,
    },
    "analyst": {
        "name": "Analyst",
        "description": "Working-level analysis with frameworks applied",
        "persona": "You are a senior sell-side strategist writing morning research. Cite frameworks by name. Identify where data confirms or contradicts theory. Be specific and actionable.",
        "max_theories": 4,
    },
    "research": {
        "name": "Research",
        "description": "Full academic depth with incentive analysis",
        "persona": "You are writing institutional research at Brookings/NBER depth. Apply complete theoretical mechanisms. Analyze incentive structures exhaustively — who benefits, who loses, who is forced to act. Flag novel conditions and cross-framework tensions.",
        "max_theories": 5,
    },
}


# ──────────────────────────────────────────────
# Section Extraction
# ──────────────────────────────────────────────

def _resolve_depth(depth: str) -> str:
    """Resolve depth aliases and validate."""
    resolved = DEPTH_ALIASES.get(depth, depth)
    if resolved not in VALID_DEPTHS:
        logger.warning(f"Invalid depth '{depth}', defaulting to 'analyst'")
        return "analyst"
    return resolved


def _extract_section(content: str, depth: str) -> str:
    """
    Extract the appropriate depth section from a theory document.

    Documents use ## HIGH-LEVEL and ## RIGOROUS as section markers.
    Tier mapping:
    - "executive"  → HIGH-LEVEL section only
    - "analyst"    → HIGH-LEVEL + RIGOROUS (but trimmed — skip Incentive Structure)
    - "research"   → Full document (both sections including Incentive Structure)
    """
    depth = _resolve_depth(depth)

    # Find section boundaries
    hl_match = re.search(r'^## HIGH-LEVEL\s*$', content, re.MULTILINE)
    rig_match = re.search(r'^## RIGOROUS\s*$', content, re.MULTILINE)

    if not hl_match:
        # No section markers — return full content for research, truncate for others
        if depth == "executive":
            # Take first ~500 chars as summary
            lines = content.strip().split('\n')
            result = []
            char_count = 0
            for line in lines:
                result.append(line)
                char_count += len(line)
                if char_count > 500:
                    break
            return '\n'.join(result)
        return content.strip()

    if depth == "executive":
        # Executive: HIGH-LEVEL section only
        if rig_match:
            return content[hl_match.start():rig_match.start()].strip()
        else:
            return content[hl_match.start():].strip()

    elif depth == "analyst":
        # Analyst: Both sections, but trim the Incentive Structure subsection
        # to keep context budget manageable
        full = content.strip()
        # Remove the detailed Incentive Structure section (keep it for research only)
        # Match "### Incentive Structure" through the next ## or end of file
        trimmed = re.sub(
            r'### Incentive Structure\s*\n.*?(?=\n##|\Z)',
            '### Incentive Structure\n[See Research tier for full incentive analysis]\n',
            full,
            flags=re.DOTALL,
        )
        return trimmed

    else:
        # Research: return the full document (both sections)
        return content.strip()


def _load_theory_file(theory_key: str, depth: str) -> Optional[str]:
    """Load and extract the appropriate section from a theory file."""
    if theory_key not in THEORY_FILES:
        logger.warning(f"Unknown theory key: {theory_key}")
        return None

    filepath = THEORY_ROOT / THEORY_FILES[theory_key]
    if not filepath.exists():
        logger.warning(f"Theory file not found: {filepath}")
        return None

    try:
        content = filepath.read_text(encoding="utf-8")
        return _extract_section(content, depth)
    except Exception as e:
        logger.error(f"Error loading theory {theory_key}: {e}")
        return None


# ──────────────────────────────────────────────
# Theory Context Builder
# ──────────────────────────────────────────────

class TheoryContext:
    """
    Builds a theory context block for injection into AI prompts.

    Selects relevant theory documents based on:
    - Detected chat topics
    - Current market regime
    - Active news event types
    - Explicit theory requests

    Supports three depth tiers: "executive", "analyst", "research".
    """

    def __init__(self, depth: str = "analyst"):
        self.depth = _resolve_depth(depth)
        self._theories_applied: List[str] = []  # Track which theories were loaded

    def select_theories(
        self,
        topics: Optional[List[str]] = None,
        regime: Optional[str] = None,
        news_events: Optional[List[str]] = None,
        explicit_theories: Optional[List[str]] = None,
        max_theories: int = MAX_THEORIES_DEFAULT,
    ) -> List[str]:
        """
        Determine which theory documents to load based on conditions.

        Uses a scoring system to prioritize the most relevant theories
        and caps the total to avoid context window bloat.

        Priority order:
        1. Explicit requests (always included, don't count toward cap)
        2. Topic-matched theories (scored by frequency across detected topics)
        3. News event-matched theories
        4. Regime-based theories (lowest priority — broad background)

        signal_interpretation is always included and doesn't count toward cap.

        Returns deduplicated, ordered list of theory keys.
        """
        # Score each theory by how many sources reference it
        scores: Dict[str, int] = {}

        # Topic matches get highest weight (3 points per topic match)
        if topics:
            for topic in topics:
                for key in TOPIC_THEORY_MAP.get(topic, []):
                    scores[key] = scores.get(key, 0) + 3

        # News event matches get medium weight (2 points per event match)
        if news_events:
            for event in news_events:
                for key in EVENT_THEORY_MAP.get(event, []):
                    scores[key] = scores.get(key, 0) + 2

        # Regime matches get lowest weight (1 point)
        if regime and regime in REGIME_THEORY_MAP:
            for key in REGIME_THEORY_MAP[regime]:
                scores[key] = scores.get(key, 0) + 1

        # Sort by score descending, then by canonical order for ties
        order = list(THEORY_FILES.keys())
        ranked = sorted(
            scores.keys(),
            key=lambda x: (-scores[x], order.index(x) if x in order else 999),
        )

        # Start with explicit theories (bypass cap)
        selected: List[str] = []
        if explicit_theories:
            for key in explicit_theories:
                if key in THEORY_FILES and key not in selected:
                    selected.append(key)

        # Fill up to max_theories from ranked list
        for key in ranked:
            if key not in selected:
                selected.append(key)
            if len(selected) >= max_theories:
                break

        # Always include signal interpretation (doesn't count toward cap)
        if "signal_interpretation" not in selected:
            selected.append("signal_interpretation")

        # Re-sort by canonical order for consistent output
        return sorted(selected, key=lambda x: order.index(x) if x in order else 999)

    def build_context(
        self,
        topics: Optional[List[str]] = None,
        regime: Optional[str] = None,
        news_events: Optional[List[str]] = None,
        explicit_theories: Optional[List[str]] = None,
        max_theories: Optional[int] = None,
    ) -> str:
        """
        Build the complete theory context block for prompt injection.

        Returns formatted string ready to insert into AI prompts.
        """
        tier_config = DEPTH_TIERS[self.depth]
        effective_max = max_theories or tier_config["max_theories"]

        theory_keys = self.select_theories(
            topics=topics,
            regime=regime,
            news_events=news_events,
            explicit_theories=explicit_theories,
            max_theories=effective_max,
        )

        if not theory_keys:
            return ""

        sections = []
        self._theories_applied = []

        for key in theory_keys:
            content = _load_theory_file(key, self.depth)
            if content:
                sections.append(content)
                self._theories_applied.append(key)

        if not sections:
            return ""

        tier_name = tier_config["name"].upper()
        persona = tier_config["persona"]

        # Tier-specific instructions
        if self.depth == "executive":
            instructions = (
                f"Apply these frameworks to support your conclusions. "
                f"Reference theory only when it sharpens the call. "
                f"Keep it decisive — the reader has 2 minutes."
            )
        elif self.depth == "analyst":
            instructions = (
                f"Apply these frameworks when interpreting the market data above. "
                f"Cite specific theories by name (Taylor Rule, Phillips Curve, Minsky, etc.). "
                f"Identify where data confirms or contradicts theoretical predictions. "
                f"Flag when conditions are novel or when multiple theories conflict."
            )
        else:  # research
            instructions = (
                f"Apply these frameworks exhaustively. Cite theories by name. "
                f"Identify where data confirms or contradicts theoretical predictions. "
                f"When conditions are novel or multiple theories conflict, explain the tension. "
                f"Analyze INCENTIVE STRUCTURES in depth — who benefits, who loses, "
                f"who is forced to act, and how those incentives drive behavior and policy."
            )

        header = (
            f"[THEORETICAL FRAMEWORK — {tier_name}]\n"
            f"Analytical Persona: {persona}\n\n"
            f"{instructions}\n"
        )

        return header + "\n\n---\n\n".join(sections)

    def get_theories_applied(self) -> List[str]:
        """Return list of theory keys that were loaded in the last build_context call."""
        return list(self._theories_applied)

    def get_analytical_lens(self) -> Dict[str, Any]:
        """
        Return metadata about the analytical configuration for API responses.

        This powers the "Analytical Lens" display in the frontend.
        """
        tier_config = DEPTH_TIERS[self.depth]
        # Map theory keys to human-readable names
        theory_names = {
            "monetary_policy": "Monetary Policy & Fed Reaction Function",
            "yield_curve": "Yield Curve Theory & Term Structure",
            "inflation": "Inflation Dynamics & Phillips Curve",
            "business_cycles": "Business Cycle Theory & Minsky",
            "labor_markets": "Labor Market Theory & Beveridge Curve",
            "fx_and_trade": "FX Theory & Mundell-Fleming",
            "fiscal_policy": "Fiscal Policy & Debt Sustainability",
            "central_bank_independence": "Central Bank Independence & Credibility",
            "trade_policy": "Trade Policy & Tariff Theory",
            "sanctions": "Sanctions & Economic Statecraft",
            "great_power_competition": "Great Power Competition & Geopolitics",
            "energy_security": "Energy Security & Commodity Geopolitics",
            "supply_chain_risk": "Supply Chain & Industrial Strategy",
            "signal_interpretation": "Signal Interpretation Guide",
            "regime_mapping": "Regime Mapping Framework",
        }

        return {
            "depth_tier": self.depth,
            "tier_name": tier_config["name"],
            "tier_description": tier_config["description"],
            "theories_applied": [
                {
                    "key": key,
                    "name": theory_names.get(key, key.replace("_", " ").title()),
                }
                for key in self._theories_applied
            ],
            "theory_count": len(self._theories_applied),
        }

    def build_narrative_context(
        self,
        regime: Optional[str] = None,
        news_events: Optional[List[str]] = None,
        narrative_mode: Optional[str] = None,
    ) -> str:
        """
        Build theory context optimized for narrative generation.

        Uses the narrative mode to select relevant topics.
        Depth tier is set at construction time.
        """
        # Map narrative modes to topic sets
        mode_topics = {
            "comprehensive": ["yields", "inflation", "labor", "growth"],
            "fed_watcher": ["fed", "inflation", "labor"],
            "rates_trader": ["yields", "credit", "fx"],
            "equity_strategist": ["equities", "growth", "fed"],
            "macro_bear": ["credit", "labor", "growth", "yields"],
            "geopolitical_analyst": ["global", "trade"],
            "contrarian": ["yields", "inflation", "growth", "credit"],
            "quick_brief": [],  # No theory for quick briefs
        }

        topics = mode_topics.get(narrative_mode, ["yields", "inflation", "labor"])

        if narrative_mode == "quick_brief":
            return ""  # Quick briefs don't need theory injection

        return self.build_context(
            topics=topics,
            regime=regime,
            news_events=news_events,
        )


# ──────────────────────────────────────────────
# Convenience Functions
# ──────────────────────────────────────────────

def get_theory_context(
    depth: str = "analyst",
    topics: Optional[List[str]] = None,
    regime: Optional[str] = None,
    news_events: Optional[List[str]] = None,
    explicit_theories: Optional[List[str]] = None,
    max_theories: Optional[int] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    One-shot convenience function to get theory context and metadata.

    Args:
        depth: "executive", "analyst", or "research" (also accepts legacy "high-level"/"rigorous")
        topics: Detected chat topics (e.g., ["yields", "fed", "inflation"])
        regime: Current market regime ("RISK_ON", "CAUTIOUS", "RISK_OFF", "CRISIS")
        news_events: Active news event types (e.g., ["RATE_DECISION", "TRADE_POLICY"])
        explicit_theories: Specific theory keys to always include
        max_theories: Override max theories (default: determined by tier)

    Returns:
        Tuple of (formatted theory context string, analytical lens metadata dict).
        Empty string and empty dict if no theories selected.
    """
    ctx = TheoryContext(depth=depth)
    context_str = ctx.build_context(
        topics=topics,
        regime=regime,
        news_events=news_events,
        explicit_theories=explicit_theories,
        max_theories=max_theories,
    )
    lens = ctx.get_analytical_lens() if context_str else {}
    return context_str, lens


def get_available_tiers() -> Dict[str, Dict[str, str]]:
    """Return available depth tiers for API/frontend consumption."""
    return {
        key: {
            "name": config["name"],
            "description": config["description"],
        }
        for key, config in DEPTH_TIERS.items()
    }
