from __future__ import annotations

from typing import Any

LEVELS = ("ideal", "attention", "elevated_alert", "critical")


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def validate_envelopes(ranges: dict[str, Any] | None) -> dict[str, Any]:
    """Valida os três envelopes autoritativos sem alterar sua estrutura."""
    ranges = ranges or {}
    optimal = ranges.get("optimal") or {}
    attention = ranges.get("attention") or {}
    critical = ranges.get("critical") or {}
    values = {
        "critical_min": _number(critical.get("min")),
        "attention_min": _number(attention.get("min")),
        "optimal_min": _number(optimal.get("min")),
        "optimal_max": _number(optimal.get("max")),
        "attention_max": _number(attention.get("max")),
        "critical_max": _number(critical.get("max")),
    }
    missing = [key for key, value in values.items() if value is None]
    if missing:
        return {"valid": False, "reason": "missing_limits", "missing": missing}
    ordered = (
        values["critical_min"] <= values["attention_min"] <= values["optimal_min"]
        <= values["optimal_max"] <= values["attention_max"] <= values["critical_max"]
    )
    return {"valid": ordered, "reason": None if ordered else "invalid_envelope_order", "limits": values}


def classify_profile_value(value: Any, ranges: dict[str, Any] | None) -> dict[str, Any]:
    """Traduz optimal/attention/critical em quatro estados compreensíveis.

    Semântica preservada:
    - optimal: faixa recomendada;
    - attention: envelope de tolerância temporária;
    - critical: limites operacionais externos;
    - fora de critical: condição crítica.
    """
    numeric = _number(value)
    validation = validate_envelopes(ranges)
    if numeric is None:
        return {"level": "no_data", "direction": None, "value": None, "validation": validation}
    if not validation.get("valid"):
        return {"level": "invalid_profile", "direction": None, "value": numeric, "validation": validation}

    limits = validation["limits"]
    omin, omax = limits["optimal_min"], limits["optimal_max"]
    amin, amax = limits["attention_min"], limits["attention_max"]
    cmin, cmax = limits["critical_min"], limits["critical_max"]

    if omin <= numeric <= omax:
        level, direction, boundary = "ideal", "within", None
    elif amin <= numeric <= amax:
        level = "attention"
        direction = "low" if numeric < omin else "high"
        boundary = omin if direction == "low" else omax
    elif cmin <= numeric <= cmax:
        level = "elevated_alert"
        direction = "low" if numeric < amin else "high"
        boundary = amin if direction == "low" else amax
    else:
        level = "critical"
        direction = "low" if numeric < cmin else "high"
        boundary = cmin if direction == "low" else cmax

    return {
        "level": level,
        "direction": direction,
        "value": numeric,
        "boundary": boundary,
        "recommended": {"min": omin, "max": omax},
        "temporary_tolerance": {"min": amin, "max": amax},
        "operational_limits": {"min": cmin, "max": cmax},
        "validation": validation,
    }
