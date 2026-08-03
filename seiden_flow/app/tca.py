from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import hashlib
import json
import re
import unicodedata

KINDS = {"temperature", "humidity", "door", "power", "voltage", "current", "energy"}


def utc_iso(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _slug(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "unknown"


def _friendly_topic_name(topic: str) -> str:
    leaf = str(topic or "").rstrip("/").split("/")[-1] or "Fonte MQTT"
    leaf = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", leaf)
    leaf = re.sub(r"[_-]+", " ", leaf).strip()
    return leaf[:1].upper() + leaf[1:] if leaf else "Fonte MQTT"


def _mqtt_identity(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """Build a stable source identity for generic MQTT events from connection + topic."""
    topic = str(payload.get("topic") or (payload.get("raw") or {}).get("topic") or "").strip()
    connection = payload.get("connection") if isinstance(payload.get("connection"), dict) else {}
    connection_id = str(payload.get("connection_id") or connection.get("id") or "mqtt").strip()
    connector = str(payload.get("connector") or connection.get("connector") or "").lower()
    event_type = str(payload.get("event_type") or "").lower()
    if not topic or not (connector == "mqtt" or "mqtt" in event_type or connection.get("type") == "message_broker"):
        return None, None
    return f"mqtt_{_slug(connection_id)}_{_slug(topic)}", _friendly_topic_name(topic)


def _door_state(value: Any, *, contact_semantics: bool = False) -> str | None:
    """Normalize door state.

    Zigbee2MQTT's ``contact`` is true when the magnetic contact is closed and false
    when the door is open. Generic door/state values follow the more usual
    true/on/open = open convention.
    """
    if isinstance(value, bool):
        if contact_semantics:
            return "closed" if value else "open"
        return "open" if value else "closed"
    text = str(value).strip().lower()
    if contact_semantics:
        if text in {"true", "1", "on", "closed", "close"}:
            return "closed"
        if text in {"false", "0", "off", "open", "opened"}:
            return "open"
        return None
    if text in {"on", "1", "true", "open", "opened"}:
        return "open"
    if text in {"off", "0", "false", "closed", "close"}:
        return "closed"
    return None


def extract_tca_measurements(payload: dict[str, Any], ha_event_type: str | None = None) -> list[dict[str, Any]]:
    """Extract protocol-independent thermal-control measurements.

    Environmental events normally carry an explicit source identity. Generic MQTT
    events do not, so their stable identity is derived from ``connection_id`` and
    ``topic``. Electrical metrics deliberately require unit-qualified field names
    (``power_w``, ``voltage_v``, ``current_a`` and energy fields), avoiding the
    common Zigbee ``voltage`` battery attribute being mistaken for mains voltage.
    """
    if not isinstance(payload, dict):
        return []

    event_type = str(payload.get("event_type") or ha_event_type or "").strip().lower()
    origin = payload.get("origin") or payload.get("reader") or {}
    if not isinstance(origin, dict):
        origin = {}

    source_id = str(
        origin.get("source_id")
        or origin.get("id")
        or payload.get("source_id")
        or payload.get("device_id")
        or ""
    ).strip()
    source_name = str(origin.get("source_name") or origin.get("name") or payload.get("source_name") or "").strip()
    if not source_id:
        source_id, mqtt_name = _mqtt_identity(payload)
        source_name = source_name or mqtt_name or ""
    if not source_id:
        return []
    source_name = source_name or source_id

    asset_id = str(payload.get("asset_id") or (payload.get("context") or {}).get("asset_id") or "").strip() or None
    role = str(payload.get("role") or origin.get("role") or "main").strip() or "main"
    occurred_at = utc_iso(payload.get("timestamp") or payload.get("occurred_at"))
    event_id = str(payload.get("event_id") or "").strip()
    if not event_id:
        event_id = "tca-" + hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()
        ).hexdigest()[:32]

    # Merge supported measurement containers. Top-level canonical fields take
    # precedence, while generic MQTT payloads are normally nested in ``data``.
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    metrics: dict[str, Any] = {}
    for candidate in (payload.get("metrics"), payload.get("measurements")):
        if isinstance(candidate, dict):
            metrics.update(candidate)

    # Nested canonical environmental measurements.
    for key, kind in (("temperature", "temperature"), ("humidity", "humidity")):
        item = metrics.get(key)
        if isinstance(item, dict):
            metrics[kind] = item.get("value")

    merged = dict(data)
    merged.update(payload)

    # Temperature and humidity accept their established environmental aliases.
    if "temperature" not in metrics:
        for name in ("temperature_c", "temperature"):
            if merged.get(name) is not None:
                metrics["temperature"] = merged.get(name)
                break
    if "humidity" not in metrics:
        for name in ("humidity_pct", "humidity"):
            if merged.get(name) is not None:
                metrics["humidity"] = merged.get(name)
                break

    # Electrical signals require unit-qualified canonical names. This intentionally
    # rejects plain ``voltage`` from Zigbee environmental devices (battery voltage).
    electrical_aliases = {
        "power": ("power_w",),
        "voltage": ("voltage_v",),
        "current": ("current_a",),
        "energy": ("energy_total_kwh", "energy_kwh"),
    }
    for kind, names in electrical_aliases.items():
        if kind in metrics and not isinstance(metrics[kind], dict):
            continue
        for name in names:
            if merged.get(name) is not None:
                metrics[kind] = merged.get(name)
                break

    # Door/contact states. ``contact`` has inverse Zigbee2MQTT semantics.
    door_value = None
    contact_semantics = False
    if merged.get("contact") is not None:
        door_value = merged.get("contact")
        contact_semantics = True
    else:
        for name in ("door", "door_state"):
            if merged.get(name) is not None:
                door_value = merged.get(name)
                break
    if door_value is None and (event_type in {"access.state", "access_state", "door.state", "door_state"} or "door" in event_type):
        door_value = merged.get("state") or merged.get("value") or (payload.get("operation") or {}).get("action")
    if door_value is not None:
        normalized_door = _door_state(door_value, contact_semantics=contact_semantics)
        if normalized_door:
            metrics["door"] = normalized_door

    # Explicit canonical metric/value event.
    metric = str(payload.get("metric") or payload.get("metric_type") or "").strip().lower()
    if metric in KINDS and payload.get("value") is not None:
        metrics[metric] = payload.get("value")

    result: list[dict[str, Any]] = []
    units = {
        "temperature": "celsius",
        "humidity": "percent",
        "power": "W",
        "voltage": "V",
        "current": "A",
        "energy": "kWh",
        "door": "state",
    }
    canonical_names = {
        "temperature_c": "temperature",
        "humidity_pct": "humidity",
        "power_w": "power",
        "voltage_v": "voltage",
        "current_a": "current",
        "energy_kwh": "energy",
        "energy_total_kwh": "energy",
    }

    seen: set[str] = set()
    for kind, value in metrics.items():
        canonical = canonical_names.get(kind, kind)
        if canonical not in KINDS or canonical in seen:
            continue
        seen.add(canonical)
        if canonical == "door":
            normalized = value if value in {"open", "closed"} else _door_state(value)
            if not normalized:
                continue
            numeric = None
            text_value = normalized
        else:
            numeric = _number(value)
            if numeric is None:
                continue
            text_value = None
        result.append(
            {
                "measurement_id": f"{event_id}:{source_id}:{canonical}",
                "event_id": event_id,
                "asset_id": asset_id,
                "source_id": source_id,
                "source_name": source_name,
                "kind": canonical,
                "role": role,
                "occurred_at": occurred_at,
                "numeric_value": numeric,
                "text_value": text_value,
                "unit": units[canonical],
                "payload": payload,
            }
        )
    return result
