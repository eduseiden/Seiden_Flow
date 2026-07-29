from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

VALID_CONDITIONS = {"comfortable", "attention", "uncomfortable", "critical", "optimal"}


def _utc_iso(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp ambiental inválido") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _number(value: Any, name: str, minimum: float, maximum: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} ambiental inválido") from exc
    if not minimum <= result <= maximum:
        raise ValueError(f"{name} ambiental fora do intervalo suportado")
    return result


def extract_environmental_measurement(payload: dict[str, Any], ha_event_type: str | None = None) -> dict[str, Any] | None:
    """Valida e normaliza um environment.observation produzido pelo Vision."""
    if not isinstance(payload, dict):
        return None
    event_type = str(payload.get("event_type") or ha_event_type or "").strip()
    if event_type != "environment.observation":
        return None

    origin = payload.get("origin") or {}
    measurements = payload.get("measurements") or {}
    analysis = payload.get("analysis") or {}
    correlation = payload.get("correlation") or {}
    source_health = payload.get("source_health") or {}
    temperature = measurements.get("temperature") or {}
    humidity = measurements.get("humidity") or {}

    event_id = str(payload.get("event_id") or "").strip()
    source_event_id = str(correlation.get("source_event_id") or "").strip()
    source_id = str(origin.get("source_id") or "").strip()
    if not event_id:
        raise ValueError("event_id ambiental ausente")
    if not source_event_id:
        raise ValueError("source_event_id ambiental ausente")
    if not source_id:
        raise ValueError("source_id ambiental ausente")

    temperature_c = _number(temperature.get("value"), "temperature", -100.0, 150.0)
    humidity_pct = None
    if humidity and humidity.get("value") is not None:
        humidity_pct = _number(humidity.get("value"), "humidity", 0.0, 100.0)
    if str(temperature.get("unit") or "").lower() not in {"celsius", "°c", "c"}:
        raise ValueError("unidade de temperatura ambiental não suportada")
    if humidity_pct is not None and str(humidity.get("unit") or "").lower() not in {"percent", "%", "percentage"}:
        raise ValueError("unidade de umidade ambiental não suportada")

    condition = str(analysis.get("condition") or "").strip().lower()
    if condition not in VALID_CONDITIONS:
        raise ValueError("condition ambiental inválida")
    environmental_score = _number(analysis.get("environmental_score", analysis.get("comfort_score")), "environmental_score", 0.0, 100.0)
    comfort_score = _number(analysis.get("comfort_score", environmental_score), "comfort_score", 0.0, 100.0)
    confidence = _number(analysis.get("confidence"), "confidence", 0.0, 1.0)

    battery = source_health.get("battery_pct")
    linkquality = source_health.get("linkquality")
    return {
        "event_id": event_id,
        "source_event_id": source_event_id,
        "schema_version": str(payload.get("schema_version") or "2.0"),
        "occurred_at": _utc_iso(payload.get("timestamp")),
        "source_id": source_id,
        "source_name": str(origin.get("source_name") or source_id),
        "location_id": str(origin.get("location_id") or "").strip() or None,
        "location_name": str(origin.get("location_name") or "").strip() or None,
        "connection_id": str(origin.get("connection_id") or "").strip() or None,
        "connector": str(origin.get("connector") or "").strip() or None,
        "topic": str(origin.get("topic") or "").strip() or None,
        "temperature_c": temperature_c,
        "humidity_pct": humidity_pct,
        "condition": condition,
        "comfort_score": comfort_score,
        "environmental_score": environmental_score,
        "analysis_type": str(analysis.get("analysis_type") or "human_comfort").strip(),
        "operational_state": str(analysis.get("operational_state") or condition).strip().lower(),
        "profile_id": str(analysis.get("profile_id") or origin.get("profile_id") or "").strip() or None,
        "resolved_profile_id": str(analysis.get("resolved_profile_id") or origin.get("resolved_profile_id") or analysis.get("profile_id") or origin.get("profile_id") or "").strip() or None,
        "profile_label": str(analysis.get("profile_label") or "").strip() or None,
        "profile_fallback": bool(analysis.get("profile_fallback", False)),
        "profile_customized": bool(analysis.get("profile_customized", False)),
        "ruleset_source": str(analysis.get("ruleset_source") or "").strip() or None,
        "metric_scores": analysis.get("metric_scores") if isinstance(analysis.get("metric_scores"), dict) else {},
        "applied_ranges": analysis.get("applied_ranges") if isinstance(analysis.get("applied_ranges"), dict) else {},
        "reason_codes": analysis.get("reason_codes") if isinstance(analysis.get("reason_codes"), list) else [],
        "confidence": confidence,
        "ruleset": str(analysis.get("ruleset") or "").strip() or None,
        "battery_pct": float(battery) if battery is not None else None,
        "linkquality": float(linkquality) if linkquality is not None else None,
        "source_last_seen": _utc_iso(source_health.get("last_seen")) if source_health.get("last_seen") else None,
        "payload": payload,
    }
