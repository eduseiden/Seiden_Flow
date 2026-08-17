from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from profile_classification import classify_profile_value
from profile_configs import eea_profile_map

VALID_CONDITIONS = {"comfortable", "attention", "uncomfortable", "critical", "optimal"}
_LEVEL_SCORE = {"ideal": 100.0, "attention": 80.0, "elevated_alert": 60.0, "critical": 30.0}
_LEVEL_CONDITION = {"ideal": "comfortable", "attention": "attention", "elevated_alert": "uncomfortable", "critical": "critical"}
_LEVEL_SEVERITY = {"ideal": 0, "attention": 1, "elevated_alert": 2, "critical": 3}


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


def _optional_number(value: Any, name: str, minimum: float, maximum: float) -> float | None:
    if value is None or value == "":
        return None
    return _number(value, name, minimum, maximum)


def _profile_measurement(
    *,
    profile_id: str,
    profile: dict[str, Any],
    temperature_c: float,
    humidity_pct: float | None,
) -> dict[str, Any]:
    """Apply the Flow-owned EEA policy to one raw environmental observation."""
    temperature_ranges = profile.get("temperature")
    humidity_ranges = profile.get("humidity")
    temp_class = classify_profile_value(temperature_c, temperature_ranges)
    humidity_class = classify_profile_value(humidity_pct, humidity_ranges) if humidity_ranges is not None and humidity_pct is not None else None

    classes = {"temperature": temp_class, "humidity": humidity_class}
    valid = [item for item in classes.values() if item and item.get("level") in _LEVEL_SEVERITY]
    worst_level = max((item["level"] for item in valid), key=lambda level: _LEVEL_SEVERITY[level], default="critical")
    condition = _LEVEL_CONDITION[worst_level]

    weighted_scores = []
    for metric, classification in classes.items():
        if not classification or classification.get("level") not in _LEVEL_SCORE:
            continue
        ranges = profile.get(metric) or {}
        weight = float(ranges.get("weight", 1.0) or 0.0)
        if weight > 0:
            weighted_scores.append((_LEVEL_SCORE[classification["level"]], weight))
    if weighted_scores:
        total_weight = sum(weight for _, weight in weighted_scores)
        score = sum(value * weight for value, weight in weighted_scores) / total_weight
    else:
        score = 30.0

    reason_codes = []
    for metric, classification in classes.items():
        if not classification:
            continue
        level = classification.get("level")
        direction = classification.get("direction")
        if level and level != "ideal":
            reason_codes.append(f"{metric}:{level}:{direction or 'unknown'}")

    return {
        "condition": condition,
        "comfort_score": round(score, 2),
        "environmental_score": round(score, 2),
        "analysis_type": profile["analysis_type"],
        "operational_state": "informational" if profile["analysis_type"] == "informational" else condition,
        "profile_id": profile_id,
        "resolved_profile_id": profile_id,
        "profile_label": profile["label"],
        "profile_fallback": False,
        "profile_customized": False,
        "ruleset_source": "flow_config_eea",
        "metric_scores": {
            metric: _LEVEL_SCORE.get(classification.get("level"), 30.0)
            for metric, classification in classes.items()
            if classification
        },
        "applied_ranges": {"temperature": temperature_ranges, "humidity": humidity_ranges},
        "reason_codes": reason_codes,
        "ruleset": profile.get("ruleset"),
    }


def _bridge_environmental_measurement(payload: dict[str, Any], event_type: str, profiles: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if event_type not in {"mqtt.message_received", "mqtt.message", "environment.measurement"}:
        return None
    environment = payload.get("environment")
    if not isinstance(environment, dict):
        return None
    profile_id = str(environment.get("profile_id") or payload.get("profile_id") or "").strip()
    profile = profiles.get(profile_id)
    if not profile:
        return None

    measurements = environment.get("measurements") if isinstance(environment.get("measurements"), dict) else {}
    temperature_c = _number(measurements.get("temperature_c", payload.get("temperature_c")), "temperature", -100.0, 150.0)
    humidity_pct = _optional_number(measurements.get("humidity_pct", payload.get("humidity_pct")), "humidity", 0.0, 100.0)
    classified = _profile_measurement(profile_id=profile_id, profile=profile, temperature_c=temperature_c, humidity_pct=humidity_pct)

    event_id = str(payload.get("event_id") or "").strip()
    source_id = str(environment.get("source_id") or payload.get("source_id") or "").strip()
    if not event_id:
        raise ValueError("event_id ambiental ausente")
    if not source_id:
        raise ValueError("source_id ambiental ausente")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    connection = payload.get("connection") if isinstance(payload.get("connection"), dict) else {}

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
        **classified,
        "confidence": 1.0,
        "battery_pct": float(measurements.get("battery_pct")) if measurements.get("battery_pct") is not None else None,
        "linkquality": float(data.get("linkquality")) if data.get("linkquality") is not None else None,
        "source_last_seen": _utc_iso(data.get("last_seen")) if data.get("last_seen") else None,
        "payload": payload,
    }


def _vision_environmental_measurement(payload: dict[str, Any], profiles: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    origin = payload.get("origin") or {}
    measurements = payload.get("measurements") or {}
    analysis = payload.get("analysis") or {}
    correlation = payload.get("correlation") or {}
    source_health = payload.get("source_health") or {}
    temperature = measurements.get("temperature") or {}
    humidity = measurements.get("humidity") or {}

    profile_id = str(
        analysis.get("resolved_profile_id")
        or analysis.get("profile_id")
        or origin.get("resolved_profile_id")
        or origin.get("profile_id")
        or ""
    ).strip()
    profile = profiles.get(profile_id)
    if not profile:
        # The Flow EEA owns only profiles present in config_eea.json. Equipment profiles
        # intentionally fall through so they can be handled by TCA instead.
        return None

    event_id = str(payload.get("event_id") or "").strip()
    source_event_id = str(correlation.get("source_event_id") or event_id).strip()
    source_id = str(origin.get("source_id") or "").strip()
    if not event_id:
        raise ValueError("event_id ambiental ausente")
    if not source_event_id:
        raise ValueError("source_event_id ambiental ausente")
    if not source_id:
        raise ValueError("source_id ambiental ausente")

    temperature_c = _number(temperature.get("value"), "temperature", -100.0, 150.0)
    humidity_pct = _optional_number(humidity.get("value") if humidity else None, "humidity", 0.0, 100.0)
    if str(temperature.get("unit") or "").lower() not in {"celsius", "°c", "c"}:
        raise ValueError("unidade de temperatura ambiental não suportada")
    if humidity_pct is not None and str(humidity.get("unit") or "").lower() not in {"percent", "%", "percentage"}:
        raise ValueError("unidade de umidade ambiental não suportada")

    classified = _profile_measurement(profile_id=profile_id, profile=profile, temperature_c=temperature_c, humidity_pct=humidity_pct)
    confidence = _optional_number(analysis.get("confidence"), "confidence", 0.0, 1.0)
    if confidence is None:
        confidence = 1.0
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
        **classified,
        "confidence": confidence,
        "battery_pct": float(battery) if battery is not None else None,
        "linkquality": float(linkquality) if linkquality is not None else None,
        "source_last_seen": _utc_iso(source_health.get("last_seen")) if source_health.get("last_seen") else None,
        "payload": payload,
    }


def extract_environmental_measurement(
    payload: dict[str, Any],
    ha_event_type: str | None = None,
    config_dir: str = "/config",
) -> dict[str, Any] | None:
    """Normalize raw observations and apply the Flow-owned EEA profile policy.

    Vision/Bridge identify the source and profile. Seiden Flow owns profile ranges,
    classification and EEA/TCA domain boundaries.
    """
    if not isinstance(payload, dict):
        return None
    event_type = str(payload.get("event_type") or ha_event_type or "").strip()
    profiles = eea_profile_map(config_dir)

    bridge_measurement = _bridge_environmental_measurement(payload, event_type, profiles)
    if bridge_measurement is not None:
        return bridge_measurement
    if event_type != "environment.observation":
        return None
    return _vision_environmental_measurement(payload, profiles)
