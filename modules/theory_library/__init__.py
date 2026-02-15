"""
Theory Library Module

Provides structured economic, political economy, and geopolitical theory
for AI-powered market analysis. Theory documents are loaded selectively
based on current market conditions and user queries.

Supports three analytical depth tiers:
- Executive Brief: C-suite conclusions
- Analyst: Working-level with framework citations
- Research: Full academic depth with incentive analysis
"""

from .context import TheoryContext, get_theory_context, get_available_tiers, DEPTH_TIERS

__all__ = [
    'TheoryContext',
    'get_theory_context',
    'get_available_tiers',
    'DEPTH_TIERS',
]
