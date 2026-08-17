from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from profile_classification import classify_profile_value

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



BRIDGE_EEA_PROFILES = {
    "human_indoor": {
        "label": "Ambiente interno humano",
        "analysis_type": "human_comfort",
        "ruleset": "seiden_bridge_human_indoor_v1",
        "temperature": {
            "optimal": {"min": 20.0, "max": 26.0},
            "attention": {"min": 17.0, "max": 29.0},
            "critical": {"min": 12.0, "max": 34.0},
        },
        "humidity": {
            "optimal": {"min": 40.0, "max": 65.0},
            "attention": {"min": 30.0, "max": 70.0},
            "critical": {"min": 20.0, "max": 80.0},
        },
    }
}

_LEVEL_SCORE = {"ideal": 100.0, "attention": 80.0, "elevated_alert": 60.0, "critical": 30.0}
_LEVEL_CONDITION = {"ideal": "comfortable", "attention": "attention", "elevated_alert": "uncomfortable", "critical": "critical"}
_LEVEL_SEVERITY = {"ideal": 0, "attention": 1, "elevated_alert": 2, "critical": 3}


def _bridge_environmental_measurement(payload: dict[str, Any], event_type: str) -> dict[str, Any] | None:
    """Normalize Bridge 2.0 MQTT environmental envelopes into native EEA storage.

    Only profiles explicitly owned by EEA are accepted here. Thermal profiles such
    as freezer/refrigerator remain TCA-only even when they use the same sensors.
    """
    if event_type not in {"mqtt.message_received", "mqtt.message", "environment.measurement"}:
        return None
    environment = payload.get("environment")
    if not isinstance(environment, dict):
        return None
    profile_id = str(environment.get("profile_id") or payload.get("profile_id") or "").strip()
    profile = BRIDGE_EEA_PROFILES.get(profile_id)
    if not profile:
        return None

    measurements = environment.get("measurements") if isinstance(environment.get("measurements"), dict) else {}
    temperature_c = _number(measurements.get("temperature_c", payload.get("temperature_c")), "temperature", -100.0, 150.0)
    humidity_pct = _number(measurements.get("humidity_pct", payload.get("humidity_pct")), "humidity", 0.0, 100.0)
    temp_class = classify_profile_value(temperature_c, profile["temperature"])
    humidity_class = classify_profile_value(humidity_pct, profile["humidity"])
    classes = {"temperature": temp_class, "humidity": humidity_class}
    valid_levels = [c.get("level") for c in classes.values() if c.get("level") in _LEVEL_SEVERITY]
    worst_level = max(valid_levels, key=lambda level: _LEVEL_SEVERITY[level]) if valid_levels else "critical"
    score = min(_LEVEL_SCORE.get(level, 30.0) for level in valid_levels) if valid_levels else 30.0
    condition = _LEVEL_CONDITION[worst_level]

    event_id = str(payload.get("event_id") or "").strip()
    source_id = str(environment.get("source_id") or payload.get("source_id") or "").strip()
    if not event_id:
        raise ValueError("event_id ambiental ausente")
    if not source_id:
        raise ValueError("source_id ambiental ausente")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    connection = payload.get("connection") if isinstance(payload.get("connection"), dict) else {}
    reason_codes = []
    for metric, classification in classes.items():
        level = classification.get("level")
        direction = classification.get("direction")
        if level and level != "ideal":
            reason_codes.append(f"{metric}:{level}:{direction or 'unknown'}")

    return {
        "event_id": event_id,
        "source_event_id": event_id,
        "schema_version": str(payload.get("schema_version") or "2.0"),
        "occurred_at": _utc_iso(payload.get("timestamp") or payload.get("occurred_at")),
        "source_id": source_id,
        "source_name": str(environment.get("source_name") or payload.get("source_name") or source_id),
        "location_id": str(environment.get("location_id") or payload.get("location_id") or "").strip() or None,
        "location_name": str(environment.get("location_name") or payload.get("location_name") or "").strip() or None,
        "connection_id": str(payload.get("connection_id") or connection.get("id") or "").strip() or None,
        "connector": str(payload.get("connector") or connection.get("connector") or "").strip() or None,
        "topic": str(payload.get("topic") or (payload.get("raw") or {}).get("topic") or "").strip() or None,
        "temperature_c": temperature_c,
        "humidity_pct": humidity_pct,
        "condition": condition,
        "comfort_score": score,
        "environmental_score": score,
        "analysis_type": profile["analysis_type"],
        "operational_state": condition,
        "profile_id": profile_id,
        "resolved_profile_id": profile_id,
        "profile_label": profile["label"],
        "profile_fallback": False,
        "profile_customized": False,
        "ruleset_source": "flow_embedded_bridge_profile",
        "metric_scores": {metric: _LEVEL_SCORE.get(c.get("level"), 30.0) for metric, c in classes.items()},
        "applied_ranges": {"temperature": profile["temperature"], "humidity": profile["humidity"]},
        "reason_codes": reason_codes,
        "confidence": 1.0,
        "ruleset": profile["ruleset"],
        "battery_pct": float(measurements.get("battery_pct")) if measurements.get("battery_pct") is not None else None,
        "linkquality": float(data.get("linkquality")) if data.get("linkquality") is not None else None,
        "source_last_seen": _utc_iso(data.get("last_seen")) if data.get("last_seen") else None,
        "payload": payload,
    }

def extract_environmental_measurement(payload: dict[str, Any], ha_event_type: str | None = None) -> dict[str, Any] | None:
    """Normaliza observações EEA do Vision e envelopes ambientais do Bridge 2.0."""
    if not isinstance(payload, dict):
        return None
    event_type = str(payload.get("event_type") or ha_event_type or "").strip()
    bridge_measurement = _bridge_environmental_measurement(payload, event_type)
    if bridge_measurement is not None:
        return bridge_measurement
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
