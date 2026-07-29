from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from version import SCHEMA_VERSION


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pick(data: dict, *keys: str, default=None):
    for key in keys:
        if data.get(key) not in (None, ""):
            return data[key]
    return default


def _stable_id(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()
    return "flow-" + hashlib.sha256(raw).hexdigest()[:32]


def normalize_event(payload: dict[str, Any], transport: str = "api", ha_event_type: str | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("O evento deve ser um objeto JSON")
    original = dict(payload)
    nested_reader = payload.get("reader") or payload.get("origin") or payload.get("connection") or {}
    nested_person = payload.get("person") or payload.get("subject") or {}
    nested_operation = payload.get("operation") or payload.get("operational") or {}

    source = str(_pick(payload, "source", default="external"))
    event_type = str(_pick(payload, "event_type", default=ha_event_type or "external.event"))
    if ha_event_type:
        # Eventos canônicos já trazem event_type/source no próprio payload.
        if "offline" in ha_event_type:
            event_type = "connection.offline"
            source = "seiden_bridge"
        elif "online" in ha_event_type:
            event_type = "connection.online"
            source = "seiden_bridge"
        elif ha_event_type == "vision.analysis_completed":
            event_type = str(payload.get("event_type") or "vision.analysis_completed")
            source = str(payload.get("source") or "seiden_vision")

    timestamp = str(_pick(payload, "timestamp", "occurred_at", "created_at", default=_now()))
    event_id = str(_pick(payload, "event_id", default=""))
    if not event_id:
        event_id = _stable_id({"transport": transport, "ha_event_type": ha_event_type, "payload": original}) if ha_event_type else str(uuid.uuid4())

    reader_name = _pick(nested_reader, "name", default=_pick(payload, "reader_name", "source_name"))
    reader_ip = _pick(nested_reader, "ip", default=_pick(payload, "reader_ip", "ip_address"))
    reader_id = _pick(
        nested_reader,
        "id",
        "source_id",
        "device_id",
        default=_pick(payload, "reader_id", "device_id", "source_id"),
    )
    if not reader_id:
        reader_id = reader_name or reader_ip
    if source == "seiden_vision" and reader_name and str(reader_id or "").startswith(("sensor.", "binary_sensor.", "event.")):
        import re, unicodedata
        canonical = unicodedata.normalize("NFKD", str(reader_name)).encode("ascii", "ignore").decode().lower()
        reader_id = re.sub(r"[^a-z0-9]+", "_", canonical).strip("_") or reader_id
    location_id = _pick(nested_reader, "location_id", default=_pick(payload, "location_id"))
    person_id = _pick(nested_person, "id", "person_id", "external_id", default=_pick(payload, "person_id", "user_id"))
    person_name = _pick(nested_person, "name", "person_name", default=_pick(payload, "person_name", "user_name", "name"))
    action = _pick(nested_operation, "action", default=_pick(payload, "action", "direction"))

    event = {
        "schema_version": str(payload.get("schema_version") or SCHEMA_VERSION),
        "event_id": event_id,
        "event_type": event_type,
        "source": source,
        "timestamp": timestamp,
        "received_at": _now(),
        "transport": transport,
        "correlation": payload.get("correlation") or {"source_event_id": payload.get("source_event_id")},
        "reader": {"id": reader_id, "name": reader_name, "ip": reader_ip, "location_id": location_id, "driver": nested_reader.get("driver") or payload.get("driver")},
        "person": {"id": person_id, "name": person_name, "authorized": nested_person.get("authorized")},
        "operation": {"action": action, "people_inside_count": nested_operation.get("people_inside_count") or payload.get("people_inside_count")},
        "payload": original,
        "_flat": {"reader_id": reader_id, "reader_name": reader_name, "location_id": location_id, "person_id": person_id, "person_name": person_name, "action": action},
    }
    return event
