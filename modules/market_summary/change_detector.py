"""
Market Change Detector

Compares current market snapshot against stored journal entries
to surface material changes for the AI chat context.
"""

from typing import Dict, List, Any, Optional
from modules.data_storage.schema import AIMarketJournal


# Materiality thresholds for flagging changes
CHANGE_THRESHOLDS = {
    "UNRATE": {"abs": 0.1, "label": "Unemployment Rate", "unit": "%"},
    "FEDFUNDS": {"abs": 0.25, "label": "Fed Funds Rate", "unit": "%"},
    "DGS10": {"abs": 0.10, "label": "10Y Yield", "unit": "%"},
    "DGS2": {"abs": 0.10, "label": "2Y Yield", "unit": "%"},
    "ICSA": {"abs": 15000, "label": "Initial Claims", "unit": "K", "divisor": 1000},
    "UMCSENT": {"abs": 2.0, "label": "Consumer Sentiment", "unit": ""},
    "INDPRO": {"abs": 0.5, "label": "Industrial Production", "unit": ""},
}

# Derived metric thresholds
DERIVED_THRESHOLDS = {
    "cpi_yoy": {"abs": 0.2, "label": "CPI YoY", "unit": "%"},
    "sahm_rule": {"abs": 0.1, "label": "Sahm Rule", "unit": "pp"},
    "real_fed_funds": {"abs": 0.3, "label": "Real Fed Funds", "unit": "%"},
}


def detect_changes(
    current_snapshot: Dict[str, Any],
    prior_entry: Optional[AIMarketJournal]
) -> Dict[str, Any]:
    """
    Compare current snapshot vs prior journal entry.
    Returns structured changes dict with material moves.
    """
    if not prior_entry or not prior_entry.indicator_snapshot:
        return {"has_prior": False, "changes": [], "regime_changed": False}

    prior = prior_entry.indicator_snapshot
    changes = []

    # Compare indicator values
    for series_id, thresholds in CHANGE_THRESHOLDS.items():
        current_data = current_snapshot.get(series_id, {})
        prior_data = prior.get(series_id, {})

        if not current_data or not prior_data:
            continue

        current_val = current_data.get("value")
        prior_val = prior_data.get("value")

        if current_val is None or prior_val is None:
            continue

        delta = current_val - prior_val
        if abs(delta) >= thresholds["abs"]:
            divisor = thresholds.get("divisor", 1)
            changes.append({
                "indicator": thresholds["label"],
                "series_id": series_id,
                "from": round(prior_val / divisor, 2) if divisor != 1 else prior_val,
                "to": round(current_val / divisor, 2) if divisor != 1 else current_val,
                "delta": round(delta / divisor, 3),
                "unit": thresholds["unit"],
                "prior_date": str(prior_entry.date),
            })

    # Compare derived metrics
    current_derived = current_snapshot.get("derived", {})
    prior_derived = prior.get("derived", {})

    for metric, thresholds in DERIVED_THRESHOLDS.items():
        current_val = current_derived.get(metric)
        prior_val = prior_derived.get(metric)

        if current_val is None or prior_val is None:
            continue

        delta = current_val - prior_val
        if abs(delta) >= thresholds["abs"]:
            changes.append({
                "indicator": thresholds["label"],
                "from": prior_val,
                "to": current_val,
                "delta": round(delta, 3),
                "unit": thresholds["unit"],
                "prior_date": str(prior_entry.date),
            })

    # Regime change detection
    regime_changed = False
    current_regime = current_snapshot.get("regime")
    prior_regime = prior.get("regime")
    if current_regime and prior_regime and current_regime != prior_regime:
        regime_changed = True
        changes.append({
            "indicator": "Market Regime",
            "from": prior_regime,
            "to": current_regime,
            "prior_date": str(prior_entry.date),
        })

    # Curve shape change
    current_shape = current_snapshot.get("curve_shape")
    prior_shape = prior.get("curve_shape")
    if current_shape and prior_shape and current_shape != prior_shape:
        changes.append({
            "indicator": "Yield Curve Shape",
            "from": prior_shape,
            "to": current_shape,
            "prior_date": str(prior_entry.date),
        })

    # Credit stress change
    current_stress = current_snapshot.get("credit_stress")
    prior_stress = prior.get("credit_stress")
    if current_stress and prior_stress and current_stress != prior_stress:
        changes.append({
            "indicator": "Credit Stress",
            "from": prior_stress,
            "to": current_stress,
            "prior_date": str(prior_entry.date),
        })

    # Theme evolution
    current_themes = set()
    prior_themes = set(prior_entry.key_themes or [])
    # Current themes need to be computed from snapshot
    # They'll be available when journal.create_or_update_today() runs
    new_themes = []
    resolved_themes = []

    return {
        "has_prior": True,
        "prior_date": str(prior_entry.date),
        "changes": changes,
        "regime_changed": regime_changed,
        "new_themes": new_themes,
        "resolved_themes": resolved_themes,
    }


def format_changes_section(changes_result: Dict[str, Any]) -> str:
    """Format changes into a concise text section for the chat context."""
    if not changes_result.get("has_prior"):
        return ""

    change_list = changes_result.get("changes", [])
    if not change_list:
        return ""

    lines = [f"WHAT CHANGED (since {changes_result['prior_date']}):"]

    for change in change_list:
        if "delta" in change:
            unit = change.get("unit", "")
            lines.append(
                f"  {change['indicator']}: {change['from']}{unit} -> "
                f"{change['to']}{unit} ({change['delta']:+.2f})"
            )
        else:
            lines.append(f"  {change['indicator']}: {change['from']} -> {change['to']}")

    new_themes = changes_result.get("new_themes", [])
    if new_themes:
        lines.append(f"  New themes: {', '.join(new_themes)}")

    resolved = changes_result.get("resolved_themes", [])
    if resolved:
        lines.append(f"  Resolved themes: {', '.join(resolved)}")

    return "\n".join(lines)
