from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import fmean
from typing import Any, Iterable

VALID_PERIODS = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "12h": timedelta(hours=12),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


def parse_utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def period_bounds(
    period: str | None = None,
    start: str | None = None,
    end: str | None = None,
    now: datetime | None = None,
) -> tuple[datetime, datetime, str]:
    resolved_end = parse_utc(end) if end else (now or datetime.now(timezone.utc))
    if start:
        resolved_start = parse_utc(start)
        label = "custom"
    else:
        label = (period or "24h").lower()
        if label not in VALID_PERIODS:
            raise ValueError("period inválido; use 1h, 6h, 12h, 24h, 7d ou 30d")
        resolved_start = resolved_end - VALID_PERIODS[label]
    if resolved_start >= resolved_end:
        raise ValueError("o início deve ser anterior ao fim")
    if resolved_end - resolved_start > timedelta(days=366):
        raise ValueError("o período máximo suportado é de 366 dias")
    return resolved_start, resolved_end, label


def _minute_floor(value: datetime, minutes: int) -> datetime:
    minute = (value.minute // minutes) * minutes
    return value.replace(minute=minute, second=0, microsecond=0)


def normalize_measurements(rows: Iterable[dict[str, Any]], window_minutes: int = 1) -> list[dict[str, Any]]:
    """Mantém a última leitura de cada fonte em cada janela temporal.

    O banco continua preservando todos os eventos brutos. A normalização é aplicada
    apenas no cálculo analítico para impedir que republicações MQTT enviesem médias.
    """
    window_minutes = max(1, min(int(window_minutes), 60))
    selected: dict[tuple[str, datetime], tuple[datetime, dict[str, Any]]] = {}
    for row in rows:
        try:
            occurred = parse_utc(row["occurred_at"])
        except (KeyError, TypeError, ValueError):
            continue
        source_id = str(row.get("source_id") or "unknown")
        bucket = _minute_floor(occurred, window_minutes)
        key = (source_id, bucket)
        current = selected.get(key)
        if current is None or occurred >= current[0]:
            item = dict(row)
            item["_occurred_dt"] = occurred
            item["_sample_bucket"] = bucket
            selected[key] = (occurred, item)
    return [value[1] for value in sorted(selected.values(), key=lambda item: item[0])]


def _round(value: float | None, digits: int = 2) -> float | None:
    return round(float(value), digits) if value is not None else None


def _series_stats(rows: list[dict[str, Any]], field: str) -> dict[str, float | None]:
    values = [float(row[field]) for row in rows if row.get(field) is not None]
    if not values:
        return {"average": None, "minimum": None, "maximum": None}
    return {"average": _round(fmean(values)), "minimum": _round(min(values)), "maximum": _round(max(values))}


def _timeline(rows: list[dict[str, Any]], bucket_minutes: int) -> list[dict[str, Any]]:
    grouped: dict[datetime, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_minute_floor(row["_occurred_dt"], bucket_minutes)].append(row)
    result = []
    for start in sorted(grouped):
        items = grouped[start]
        counts = defaultdict(int)
        for item in items:
            counts[str(item.get("condition") or "unknown")] += 1
        dominant = max(counts, key=counts.get) if counts else None
        result.append({
            "start": utc_iso(start),
            "end": utc_iso(start + timedelta(minutes=bucket_minutes)),
            "sample_count": len(items),
            "source_count": len({str(item.get("source_id") or "") for item in items}),
            "temperature_c": _series_stats(items, "temperature_c")["average"],
            "humidity_pct": _series_stats(items, "humidity_pct")["average"],
            "comfort_score": _series_stats(items, "comfort_score")["average"],
            "condition": dominant,
        })
    return result


def calculate_environmental_analytics(
    rows: list[dict[str, Any]],
    start: datetime,
    end: datetime,
    comparison_rows: list[dict[str, Any]] | None = None,
    sampling_minutes: int = 1,
    bucket_minutes: int = 60,
    minimum_samples: int = 10,
) -> dict[str, Any]:
    normalized = normalize_measurements(rows, sampling_minutes)
    comparison = normalize_measurements(comparison_rows or [], sampling_minutes)
    source_ids = sorted({str(row.get("source_id") or "unknown") for row in normalized})
    latest = max(normalized, key=lambda row: row["_occurred_dt"], default=None)

    condition_counts = {"comfortable": 0, "attention": 0, "uncomfortable": 0}
    for row in normalized:
        condition = str(row.get("condition") or "")
        if condition in condition_counts:
            condition_counts[condition] += 1
    total_condition = sum(condition_counts.values())
    distribution = {}
    for condition, count in condition_counts.items():
        distribution[condition] = {
            "samples": count,
            "estimated_minutes": count * sampling_minutes,
            "percentage": _round((count / total_condition * 100.0) if total_condition else 0.0),
        }

    comfort_values = [float(row["comfort_score"]) for row in normalized if row.get("comfort_score") is not None]
    index = _round(fmean(comfort_values)) if comfort_values else None
    previous_values = [float(row["comfort_score"]) for row in comparison if row.get("comfort_score") is not None]
    previous_index = _round(fmean(previous_values)) if previous_values else None
    delta = _round(index - previous_index) if index is not None and previous_index is not None else None
    if delta is None:
        direction = "insufficient_data"
    elif delta > 2.0:
        direction = "improving"
    elif delta < -2.0:
        direction = "worsening"
    else:
        direction = "stable"

    timeline = _timeline(normalized, bucket_minutes)
    scored_buckets = [item for item in timeline if item["comfort_score"] is not None]
    best = max(scored_buckets, key=lambda item: item["comfort_score"], default=None)
    worst = min(scored_buckets, key=lambda item: item["comfort_score"], default=None)

    period_minutes = max(1.0, (end - start).total_seconds() / 60.0)
    expected_samples = period_minutes / sampling_minutes * max(1, len(source_ids))
    coverage_pct = min(100.0, len(normalized) / expected_samples * 100.0) if normalized else 0.0
    avg_confidence = _series_stats(normalized, "confidence")["average"]
    if len(normalized) < minimum_samples:
        quality_status = "insufficient"
    elif coverage_pct >= 75 and (avg_confidence or 0) >= 0.8:
        quality_status = "high"
    elif coverage_pct >= 30 and (avg_confidence or 0) >= 0.6:
        quality_status = "medium"
    else:
        quality_status = "low"

    current = None
    if latest:
        current = {
            "occurred_at": utc_iso(latest["_occurred_dt"]),
            "source_id": latest.get("source_id"),
            "source_name": latest.get("source_name"),
            "location_id": latest.get("location_id"),
            "location_name": latest.get("location_name"),
            "temperature_c": _round(latest.get("temperature_c")),
            "humidity_pct": _round(latest.get("humidity_pct")),
            "comfort_score": _round(latest.get("comfort_score")),
            "condition": latest.get("condition"),
            "confidence": _round(latest.get("confidence")),
        }

    return {
        "period": {"start": utc_iso(start), "end": utc_iso(end)},
        "scope": {"source_count": len(source_ids), "source_ids": source_ids},
        "current": current,
        "eea_index": index,
        "temperature": _series_stats(normalized, "temperature_c"),
        "humidity": _series_stats(normalized, "humidity_pct"),
        "comfort": {
            "average_score": index,
            "minimum_score": _round(min(comfort_values)) if comfort_values else None,
            "maximum_score": _round(max(comfort_values)) if comfort_values else None,
            "distribution": distribution,
        },
        "trend": {
            "direction": direction,
            "score_delta": delta,
            "previous_eea_index": previous_index,
            "comparison_start": utc_iso(start - (end - start)),
            "comparison_end": utc_iso(start),
        },
        "best_period": best,
        "worst_period": worst,
        "data_quality": {
            "status": quality_status,
            "sample_count_raw": len(rows),
            "sample_count_normalized": len(normalized),
            "average_confidence": avg_confidence,
            "coverage_pct": _round(coverage_pct),
            "sampling_window_minutes": sampling_minutes,
            "minimum_samples": minimum_samples,
        },
        "timeline": timeline,
    }
