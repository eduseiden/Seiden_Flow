from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import uuid

POSITIVE = {"HAPPY", "POSITIVE", "SMILE", "SMILING"}
NEUTRAL = {"CALM", "NEUTRAL", "SURPRISED", "SURPRISE"}
NEGATIVE = {"SAD", "ANGRY", "ANGER", "DISGUSTED", "DISGUST", "CONFUSED", "CONFUSION", "FEAR", "FEARFUL", "NEGATIVE"}


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    # AWS Rekognition commonly emits 0..100; canonical Vision can emit 0..1.
    if v > 1.0:
        v /= 100.0
    return max(0.0, min(1.0, v))


def normalize_expression(value: Any) -> str:
    name = str(value or "UNKNOWN").strip().upper()
    if name in POSITIVE:
        return "positive"
    if name in NEUTRAL:
        return "neutral"
    if name in NEGATIVE:
        return "negative"
    return "uncertain"


def extract_vision_observation(payload: dict[str, Any]) -> dict[str, Any] | None:
    if str(payload.get("event_type") or "") != "vision.analysis_completed":
        return None
    analysis = payload.get("analysis") or {}
    origin = payload.get("origin") or payload.get("reader") or {}
    raw_expression = analysis.get("dominant_emotion") or analysis.get("observed_expression")
    if not raw_expression:
        return None
    source_id = origin.get("source_id") or origin.get("device_id") or payload.get("source_id")
    source_name = origin.get("source_name") or payload.get("source_name") or source_id
    location_id = origin.get("location_id") or payload.get("location_id")
    confidence = _as_float(analysis.get("confidence"), 0.0)
    occurred_at = payload.get("timestamp") or payload.get("occurred_at") or datetime.now(timezone.utc).isoformat()
    try:
        parsed = datetime.fromisoformat(str(occurred_at).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        occurred_at = parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        occurred_at = datetime.now(timezone.utc).isoformat()
    return {
        "observation_id": "obs_" + uuid.uuid4().hex,
        "metric_type": "facial_expression",
        "provider": "seiden_vision",
        "source_id": str(source_id or "unknown_source"),
        "source_name": str(source_name or source_id or "Fonte desconhecida"),
        "location_id": str(location_id) if location_id else None,
        "occurred_at": str(occurred_at),
        "value": normalize_expression(raw_expression),
        "raw_value": str(raw_expression),
        "confidence": confidence,
    }


def sanitize_vision_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove expressão do evento persistente.

    A expressão segue apenas para o pipeline anônimo de observações. O evento técnico
    pode continuar contendo origem, qualidade e sujeito, mas jamais a expressão.
    """
    if str(payload.get("event_type") or "") != "vision.analysis_completed":
        return payload
    clean = dict(payload)
    analysis = dict(clean.get("analysis") or {})
    analysis.pop("dominant_emotion", None)
    analysis.pop("observed_expression", None)
    analysis.pop("emotions", None)
    clean["analysis"] = analysis
    return clean
