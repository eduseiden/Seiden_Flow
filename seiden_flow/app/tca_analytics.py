from __future__ import annotations

from datetime import datetime, timezone, timedelta
from statistics import fmean

OBSERVATION_WINDOW_MINUTES = 30
MEASURABLE_IMPACT_C = 0.2


def parse(value):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def rnd(value, digits=2):
    return round(float(value), digits) if value is not None else None


def _in_range(value, minimum, maximum):
    return (minimum is None or value >= float(minimum)) and (maximum is None or value <= float(maximum))


def _integrated_power_wh(rows, start, finish):
    points = [r for r in rows if start <= parse(r["occurred_at"]) <= finish and r.get("numeric_value") is not None]
    if len(points) < 2:
        return None
    total = 0.0
    for current, following in zip(points, points[1:]):
        seconds = max(0.0, (parse(following["occurred_at"]) - parse(current["occurred_at"])).total_seconds())
        total += float(current["numeric_value"]) * seconds / 3600.0
    return total


def _energy_delta_wh(rows, start, finish):
    points = [r for r in rows if start <= parse(r["occurred_at"]) <= finish and r.get("numeric_value") is not None]
    if len(points) < 2:
        return None
    delta_kwh = float(points[-1]["numeric_value"]) - float(points[0]["numeric_value"])
    return max(0.0, delta_kwh * 1000.0)


def calculate_tca(rows, asset, bindings, start, end):
    by = {k: [] for k in ("temperature", "humidity", "door", "power", "voltage", "current", "energy")}
    for row in rows:
        if row["kind"] in by:
            by[row["kind"]].append(row)
    for values in by.values():
        values.sort(key=lambda row: row["occurred_at"])

    latest = {kind: (values[-1] if values else None) for kind, values in by.items()}
    temps = [float(r["numeric_value"]) for r in by["temperature"] if r.get("numeric_value") is not None]
    powers = [float(r["numeric_value"]) for r in by["power"] if r.get("numeric_value") is not None]

    min_t = asset.get("min_temperature_c")
    max_t = asset.get("max_temperature_c")
    primary_ids = [b["source_id"] for b in bindings if b["kind"] == "temperature" and b.get("is_primary")]
    temp_rows = [r for r in by["temperature"] if not primary_ids or r["source_id"] in primary_ids]
    if not temp_rows:
        temp_rows = by["temperature"]

    door_events = by["door"]
    episodes = []
    opened = None
    for index, door_event in enumerate(door_events):
        state = door_event.get("text_value")
        if state == "open" and opened is None:
            opened = door_event
            continue
        if state != "closed" or opened is None:
            continue

        opened_at = parse(opened["occurred_at"])
        closed_at = parse(door_event["occurred_at"])
        next_open = next(
            (parse(item["occurred_at"]) for item in door_events[index + 1 :] if item.get("text_value") == "open"),
            None,
        )
        observation_limit = min(end, closed_at + timedelta(minutes=OBSERVATION_WINDOW_MINUTES))
        analysis_end = min(observation_limit, next_open) if next_open else observation_limit

        before = [t for t in temp_rows if parse(t["occurred_at"]) <= opened_at]
        baseline = float(before[-1]["numeric_value"]) if before else None
        observed = [t for t in temp_rows if closed_at <= parse(t["occurred_at"]) <= analysis_end]
        values = [float(t["numeric_value"]) for t in observed if t.get("numeric_value") is not None]

        peak = max(values) if values else None
        low = min(values) if values else None
        impact = max((abs(value - baseline) for value in values), default=None) if baseline is not None else None
        out_of_range_seen = any(not _in_range(value, min_t, max_t) for value in values)

        recovered = None
        if out_of_range_seen:
            for item in observed:
                value = float(item["numeric_value"])
                if _in_range(value, min_t, max_t):
                    recovered = item
                    break

        elapsed_since_close = max(0.0, (end - closed_at).total_seconds())
        interrupted = bool(next_open and next_open <= observation_limit and not recovered)
        enough_time = elapsed_since_close >= OBSERVATION_WINDOW_MINUTES * 60

        if recovered:
            status = "recovered"
            final_at = parse(recovered["occurred_at"])
        elif interrupted:
            status = "interrupted"
            final_at = next_open
        elif not observed:
            status = "insufficient_data" if enough_time else "observing"
            final_at = analysis_end
        elif not out_of_range_seen and (impact is None or impact < MEASURABLE_IMPACT_C):
            status = "no_measurable_impact"
            final_at = analysis_end
        elif enough_time:
            status = "not_recovered"
            final_at = observation_limit
        else:
            status = "observing"
            final_at = analysis_end

        recovery_minutes = (
            (parse(recovered["occurred_at"]) - closed_at).total_seconds() / 60.0 if recovered else None
        )
        energy_wh = _energy_delta_wh(by["energy"], closed_at, final_at)
        if energy_wh is None:
            energy_wh = _integrated_power_wh(by["power"], closed_at, final_at)
        energy_final = status in {"recovered", "interrupted", "no_measurable_impact", "not_recovered"}

        episodes.append(
            {
                "opened_at": opened["occurred_at"],
                "closed_at": door_event["occurred_at"],
                "open_seconds": round((closed_at - opened_at).total_seconds()),
                "baseline_temperature_c": rnd(baseline),
                "maximum_temperature_c": rnd(peak),
                "minimum_temperature_c": rnd(low),
                "thermal_impact_c": rnd(impact),
                "recovered_at": recovered["occurred_at"] if recovered else None,
                "recovery_minutes": rnd(recovery_minutes),
                "recovery_energy_wh": rnd(energy_wh, 3),
                "energy_final": energy_final,
                "temperature_samples": len(values),
                "status": status,
            }
        )
        opened = None

    if opened:
        episodes.append(
            {
                "opened_at": opened["occurred_at"],
                "closed_at": None,
                "open_seconds": round((end - parse(opened["occurred_at"])).total_seconds()),
                "status": "open",
                "energy_final": False,
                "temperature_samples": 0,
            }
        )

    recoveries = [e["recovery_minutes"] for e in episodes if e.get("recovery_minutes") is not None]
    current_door = latest["door"]["text_value"] if latest["door"] else "unknown"
    current_temp = latest["temperature"]["numeric_value"] if latest["temperature"] else None
    in_range = current_temp is not None and _in_range(float(current_temp), min_t, max_t)
    state = "door_open" if current_door == "open" else ("stable" if in_range else "out_of_range" if current_temp is not None else "no_data")

    timeline = [
        {
            "occurred_at": r["occurred_at"],
            "source_id": r["source_id"],
            "source_name": r.get("source_name"),
            "kind": r["kind"],
            "role": r.get("role"),
            "value": r.get("text_value") if r["kind"] == "door" else r.get("numeric_value"),
            "unit": r.get("unit"),
        }
        for r in rows
    ]

    return {
        "asset": asset,
        "period": {"start": start.isoformat().replace("+00:00", "Z"), "end": end.isoformat().replace("+00:00", "Z")},
        "current": {
            "state": state,
            "temperature_c": rnd(current_temp),
            "humidity_pct": rnd(latest["humidity"]["numeric_value"]) if latest["humidity"] else None,
            "door": current_door,
            "power_w": rnd(latest["power"]["numeric_value"]) if latest["power"] else None,
            "voltage_v": rnd(latest["voltage"]["numeric_value"]) if latest["voltage"] else None,
            "current_a": rnd(latest["current"]["numeric_value"]) if latest["current"] else None,
            "in_range": in_range,
            "last_update": max((r["occurred_at"] for r in rows), default=None),
        },
        "summary": {
            "sample_count": len(rows),
            "temperature_sample_count": len(temps),
            "power_sample_count": len(powers),
            "temperature_average_c": rnd(fmean(temps)) if temps else None,
            "temperature_minimum_c": rnd(min(temps)) if temps else None,
            "temperature_maximum_c": rnd(max(temps)) if temps else None,
            "power_average_w": rnd(fmean(powers)) if powers else None,
            "door_openings": len([e for e in episodes if e.get("closed_at")]),
            "door_open_seconds": sum(e.get("open_seconds", 0) for e in episodes),
            "average_recovery_minutes": rnd(fmean(recoveries)) if recoveries else None,
            "recovered_episodes": len(recoveries),
            "observing_episodes": len([e for e in episodes if e.get("status") == "observing"]),
            "incomplete_episodes": len([e for e in episodes if e.get("status") in {"insufficient_data", "not_recovered"}]),
        },
        "episodes": episodes,
        "bindings": bindings,
        "timeline": timeline,
    }
