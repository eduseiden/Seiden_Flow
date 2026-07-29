from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable

# Default profile for Epic 1. Segment-specific profiles will be introduced in Epic 4.
DEFAULT_EMOTION_WEIGHTS: dict[str, float] = {
    "happy": 100.0,
    "positive": 100.0,
    "smile": 100.0,
    "smiling": 100.0,
    "calm": 40.0,
    "surprised": 20.0,
    "surprise": 20.0,
    "neutral": 0.0,
    "confused": -20.0,
    "confusion": -20.0,
    "sad": -60.0,
    "disgusted": -70.0,
    "disgust": -70.0,
    "fear": -80.0,
    "fearful": -80.0,
    "angry": -100.0,
    "anger": -100.0,
    "negative": -100.0,
}

CATEGORY_FALLBACK_WEIGHTS = {"positive": 100.0, "neutral": 0.0, "negative": -100.0, "uncertain": 0.0}


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        value = getattr(row, key, default)
    return default if value is None else value


def emotion_key(row: Any) -> str:
    raw = str(_row_get(row, "raw_value", "") or "").strip().lower()
    return raw or str(_row_get(row, "value", "uncertain") or "uncertain").strip().lower()


def observation_score(row: Any, weights: dict[str, float] | None = None) -> float:
    profile = weights or DEFAULT_EMOTION_WEIGHTS
    category = str(_row_get(row, "value", "uncertain") or "uncertain").lower()
    base = profile.get(emotion_key(row), CATEGORY_FALLBACK_WEIGHTS.get(category, 0.0))
    confidence = float(_row_get(row, "confidence", 0.0) or 0.0)
    confidence = max(0.0, min(1.0, confidence))
    return base * confidence


def classify(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 75:
        return "excellent"
    if score >= 40:
        return "positive"
    if score >= 10:
        return "slightly_positive"
    if score > -10:
        return "neutral"
    if score > -40:
        return "slightly_negative"
    if score > -75:
        return "negative"
    return "critical"


def trend_from_delta(delta: float | None, stable_threshold: float = 2.0) -> str | None:
    if delta is None:
        return None
    if delta > stable_threshold:
        return "up"
    if delta < -stable_threshold:
        return "down"
    return "stable"


def calculate_stats(rows: Iterable[Any], minimum_samples: int, weights: dict[str, float] | None = None) -> dict[str, Any]:
    items = list(rows)
    counts = {"positive": 0, "neutral": 0, "negative": 0, "uncertain": 0}
    emotion_distribution: dict[str, int] = {}
    for row in items:
        category = str(_row_get(row, "value", "uncertain") or "uncertain").lower()
        if category not in counts:
            category = "uncertain"
        counts[category] += 1
        key = emotion_key(row)
        emotion_distribution[key] = emotion_distribution.get(key, 0) + 1

    count = len(items)
    available = count >= minimum_samples
    base = {
        "available": available,
        "status": "available" if available else "insufficient_data",
        "minimum_samples": minimum_samples,
        "sample_count": count,
        "distribution": counts,
        "emotion_distribution": emotion_distribution,
    }
    if not available:
        return {**base, "experience_index": None, "classification": None, "dominant_expression": None, "average_confidence": None}

    average_confidence = sum(float(_row_get(row, "confidence", 0.0) or 0.0) for row in items) / count
    score = sum(observation_score(row, weights) for row in items) / count
    score = max(-100.0, min(100.0, score))
    dominant = max(("positive", "neutral", "negative"), key=lambda item: counts[item])
    return {
        **base,
        "experience_index": round(score, 1),
        "classification": classify(score),
        "dominant_expression": dominant,
        "average_confidence": round(average_confidence, 4),
    }


def compare_periods(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    current_score = current.get("experience_index")
    previous_score = previous.get("experience_index")
    if current_score is None or previous_score is None:
        return {
            "previous_experience_index": previous_score,
            "previous_sample_count": previous.get("sample_count", 0),
            "delta": None,
            "delta_percentage": None,
            "trend": None,
        }
    delta = round(float(current_score) - float(previous_score), 1)
    # Percentage change around zero is mathematically unstable and potentially misleading.
    delta_percentage = None if abs(float(previous_score)) < 1.0 else round((delta / abs(float(previous_score))) * 100.0, 1)
    return {
        "previous_experience_index": previous_score,
        "previous_sample_count": previous.get("sample_count", 0),
        "delta": delta,
        "delta_percentage": delta_percentage,
        "trend": trend_from_delta(delta),
    }
