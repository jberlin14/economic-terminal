"""
Scenario Simulator

Simulates cascading market impact of hypothetical economic/geopolitical scenarios
using Claude AI grounded in the theory library and current market state.

"What if CPI comes in at 3.5%?" → traces impact through yields, FX, credit, equities.
"""

import os
import json
import time
from typing import Dict, Any, Optional, Tuple, List
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


# ──────────────────────────────────────────────
# Preset Scenarios
# ──────────────────────────────────────────────

PRESET_SCENARIOS = [
    {"id": "cpi_hot", "label": "CPI comes in at 3.5% YoY", "category": "inflation"},
    {"id": "fed_cut_50", "label": "Fed cuts 50bps at next meeting", "category": "fed"},
    {"id": "fed_hike_surprise", "label": "Fed surprises with 25bps hike", "category": "fed"},
    {"id": "china_devaluation", "label": "China devalues yuan by 5%", "category": "fx"},
    {"id": "credit_event", "label": "Major IG issuer defaults", "category": "credit"},
    {"id": "oil_shock", "label": "Oil spikes to $120/barrel on Middle East escalation", "category": "geopolitical"},
    {"id": "nfp_negative", "label": "NFP prints -150K jobs", "category": "labor"},
    {"id": "soft_landing", "label": "CPI falls to 2.1% while unemployment stays at 4.0%", "category": "growth"},
]

# Map scenario categories to theory library topics
CATEGORY_TOPICS = {
    "inflation": ["inflation", "fed", "yields"],
    "fed": ["fed", "yields", "fx"],
    "fx": ["fx", "trade", "global"],
    "credit": ["credit", "yields", "equities"],
    "geopolitical": ["global", "fx", "trade"],
    "labor": ["labor", "fed", "growth"],
    "growth": ["growth", "fed", "equities"],
}


class ScenarioSimulator:
    """Simulates cascading market impact of hypothetical scenarios."""

    def __init__(self, db: Session):
        self.db = db
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self._client = None

    def is_available(self) -> bool:
        return ANTHROPIC_AVAILABLE and bool(self.api_key)

    def _get_client(self):
        if self._client is None and self.api_key:
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def simulate(self, scenario_text: str, theory_depth: str = "analyst") -> Dict[str, Any]:
        """
        Simulate cascading market impact of a scenario.

        Returns structured result with impacts per asset class,
        cascade chain, regime shift probability, and narrative.
        """
        start = time.time()

        if not self.is_available():
            return {"error": "AI unavailable. ANTHROPIC_API_KEY not configured."}

        # Gather current market state
        from modules.market_summary.analytics_engine import (
            gather_market_context,
            compute_analytics,
            format_compact_briefing,
        )

        context = gather_market_context(self.db)
        analytics = compute_analytics(context, self.db)
        briefing = format_compact_briefing(context, analytics)

        # Get regime info
        regime_data = analytics.get("regime", {})
        current_regime = regime_data.get("regime", "UNKNOWN")

        # Get theory context
        theory_block, analytical_lens = self._build_theory_context(
            scenario_text, theory_depth
        )

        # Build and send prompt
        prompt = self._build_prompt(scenario_text, briefing, current_regime, theory_block)

        try:
            client = self._get_client()
            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=3000,
                system=self._system_prompt(),
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = response.content[0].text
            tokens = response.usage.input_tokens + response.usage.output_tokens

            # Parse structured response
            result = self._parse_response(response_text)
            result["current_regime"] = current_regime
            result["analytical_lens"] = analytical_lens
            result["tokens_used"] = tokens
            result["elapsed_ms"] = int((time.time() - start) * 1000)
            result["scenario_input"] = scenario_text

            return result

        except Exception as e:
            logger.error(f"Scenario simulation failed: {e}", exc_info=True)
            return {
                "error": str(e),
                "elapsed_ms": int((time.time() - start) * 1000),
            }

    def _build_theory_context(self, scenario_text: str, depth: str) -> Tuple[str, Dict]:
        """Get relevant theory context based on scenario topic."""
        try:
            from modules.theory_library import get_theory_context

            # Detect topics from scenario text
            scenario_lower = scenario_text.lower()
            topics = set()
            for cat, cat_topics in CATEGORY_TOPICS.items():
                # Check if any category keywords appear in the scenario
                keywords = {
                    "inflation": ["cpi", "inflation", "pce", "prices"],
                    "fed": ["fed", "fomc", "rate", "monetary", "powell"],
                    "fx": ["dollar", "yuan", "yen", "currency", "fx", "devalue"],
                    "credit": ["credit", "default", "spread", "bond", "debt"],
                    "geopolitical": ["war", "sanctions", "tariff", "military", "geopolitical", "middle east"],
                    "labor": ["jobs", "nfp", "payroll", "unemployment", "hiring", "layoff"],
                    "growth": ["gdp", "recession", "growth", "soft landing", "slowdown"],
                }
                for kw in keywords.get(cat, []):
                    if kw in scenario_lower:
                        topics.update(cat_topics)
                        break

            if not topics:
                topics = {"yields", "fx", "credit"}  # default breadth

            return get_theory_context(
                depth=depth,
                topics=list(topics),
            )
        except Exception as e:
            logger.warning(f"Theory context failed: {e}")
            return "", {}

    def _system_prompt(self) -> str:
        return """You are an institutional macro strategist simulating the cascading market impact of hypothetical scenarios.

Your role is to trace how a single economic or geopolitical event propagates through interconnected markets:
Bonds → FX → Credit → Equities → Volatility → Regime

Rules:
- Ground your analysis in the theoretical frameworks provided
- Use the CURRENT MARKET STATE as your starting point
- Be specific about magnitudes (basis points for yields/credit, percent for FX/equities)
- Distinguish between immediate (same day), short-term (1-2 weeks), and medium-term (1-3 months) effects
- Assign confidence levels honestly — some cascades are more predictable than others
- Consider both first-order and second-order effects
- Reference specific transmission mechanisms (e.g., "carry trade unwind", "flight to quality", "term premium repricing")

Writing style for the narrative field:
- Write in clear, flowing prose. Each paragraph should develop one idea fully.
- Use direct, declarative sentences. Avoid hedging phrases like "it is worth noting that" or "one might argue."
- Never use dashes or em-dashes as clause separators. Restructure into separate sentences instead.
- Avoid triple-clause constructions ("not X, but Y, and Z"). Keep sentence structure simple: subject-verb-object.
- Do not front-load sentences with caveats. State the conclusion first, then qualify if needed.
- Avoid AI-isms: no "it's important to note," "it bears mentioning," "one cannot overstate," or "the key takeaway here is."
- Write as a Goldman Sachs morning note would read: confident, precise, economical with words.

Always respond with valid JSON matching the requested format."""

    def _build_prompt(self, scenario: str, briefing: str, regime: str, theory_block: str) -> str:
        return f"""CURRENT MARKET STATE (as of now):
Regime: {regime}

{briefing}

{theory_block}

SCENARIO TO SIMULATE:
"{scenario}"

Analyze this scenario and respond with a JSON object containing:

{{
  "scenario_summary": "1-2 sentence restatement of what happens",
  "simulated_impacts": [
    {{
      "asset_class": "Treasury Yields",
      "direction": "up" | "down" | "unchanged",
      "magnitude": "specific estimate, e.g. '+15-25bps on 10Y'",
      "confidence": "high" | "medium" | "low",
      "reasoning": "1-2 sentences explaining WHY"
    }},
    // Include entries for: Treasury Yields, FX (USD), Credit Spreads, Equities, Volatility (VIX)
  ],
  "cascade_chain": [
    {{
      "step": 1,
      "from": "Scenario",
      "to": "Bond Market",
      "mechanism": "description of transmission",
      "timeframe": "immediate" | "short-term" | "medium-term"
    }},
    // Trace the full cascade: Scenario → Bonds → FX → Credit → Equities → Regime
  ],
  "regime_shift": {{
    "probability": "high" | "medium" | "low" | "negligible",
    "current": "{regime}",
    "projected": "RISK_ON" | "CAUTIOUS" | "RISK_OFF" | "CRISIS",
    "reasoning": "Why regime does or doesn't shift"
  }},
  "historical_parallel": "1-2 sentences citing a similar historical episode and its outcome",
  "narrative": "3-5 paragraph professional narrative weaving together all the impacts, written as if for an institutional morning note"
}}

Respond ONLY with the JSON object, no other text."""

    def _parse_response(self, text: str) -> Dict[str, Any]:
        """Parse Claude's JSON response with robust fallback handling.

        Guarantees a consistent output structure regardless of whether
        the AI returns valid JSON, partial JSON, or plain text.
        """
        # Template with all required fields
        result = {
            "scenario_summary": "",
            "simulated_impacts": [],
            "cascade_chain": [],
            "regime_shift": {
                "probability": "unknown",
                "current": "",
                "projected": "",
                "reasoning": "",
            },
            "historical_parallel": "",
            "narrative": "",
        }

        cleaned = text.strip()

        # Strip markdown code fences if present
        if "```" in cleaned:
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        # Try to find JSON object in the response (may be surrounded by text)
        parsed = None
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract JSON from within the text
            import re
            json_match = re.search(r'\{[\s\S]*\}', cleaned)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

        if parsed and isinstance(parsed, dict):
            # Merge parsed data into template, normalizing field names
            result["scenario_summary"] = parsed.get("scenario_summary", "")

            # Normalize impacts — handle various field name patterns
            impacts = parsed.get("simulated_impacts", parsed.get("impacts", []))
            if isinstance(impacts, list):
                normalized_impacts = []
                for imp in impacts:
                    if isinstance(imp, dict):
                        normalized_impacts.append({
                            "asset_class": imp.get("asset_class", imp.get("asset", "Unknown")),
                            "direction": imp.get("direction", "unchanged"),
                            "magnitude": imp.get("magnitude", imp.get("move", "N/A")),
                            "confidence": imp.get("confidence", "medium"),
                            "reasoning": imp.get("reasoning", imp.get("rationale", imp.get("explanation", ""))),
                        })
                result["simulated_impacts"] = normalized_impacts

            # Normalize cascade chain
            chain = parsed.get("cascade_chain", parsed.get("cascade", []))
            if isinstance(chain, list):
                normalized_chain = []
                for i, step in enumerate(chain):
                    if isinstance(step, dict):
                        normalized_chain.append({
                            "step": step.get("step", i + 1),
                            "from": step.get("from", step.get("source", "")),
                            "to": step.get("to", step.get("target", step.get("destination", ""))),
                            "mechanism": step.get("mechanism", step.get("description", step.get("transmission", ""))),
                            "timeframe": step.get("timeframe", step.get("timing", "short-term")),
                        })
                result["cascade_chain"] = normalized_chain

            # Normalize regime shift
            regime = parsed.get("regime_shift", parsed.get("regime", {}))
            if isinstance(regime, dict):
                result["regime_shift"] = {
                    "probability": regime.get("probability", "unknown"),
                    "current": regime.get("current", ""),
                    "projected": regime.get("projected", regime.get("new_regime", regime.get("target", ""))),
                    "reasoning": regime.get("reasoning", regime.get("rationale", "")),
                }

            result["historical_parallel"] = parsed.get("historical_parallel", parsed.get("historical", ""))
            result["narrative"] = parsed.get("narrative", parsed.get("analysis", ""))
        else:
            # Complete parse failure — use the raw text as the narrative
            result["narrative"] = text
            result["scenario_summary"] = "Simulation completed (unstructured response)"

        return result
