from __future__ import annotations

from datetime import datetime, timezone, timedelta
from statistics import fmean

from profile_classification import classify_profile_value, validate_envelopes

OBSERVATION_WINDOW_MINUTES = 30
MEASURABLE_IMPACT_C = 0.2
ACCESS_SESSION_GAP_SECONDS = 60


def parse(value):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def rnd(value, digits=2):
    return round(float(value), digits) if value is not None else None


def _in_range(value, minimum, maximum):
    return (minimum is None or value >= float(minimum)) and (maximum is None or value <= float(maximum))


def _profile_ranges(asset):
    snap = ((asset.get("metadata") or {}).get("profile_snapshot") or {})
    temperature = snap.get("temperature") or {}
    return {
        "optimal": temperature.get("optimal") or {
            "min": asset.get("min_temperature_c"),
            "max": asset.get("max_temperature_c"),
        },
        "attention": temperature.get("attention") or {},
        "critical": temperature.get("critical") or {},
    }


def _power_wh(rows, start, finish):
    """Integrate instantaneous power with the trapezoidal rule.

    The accumulated-energy entity is intentionally not used for short episodes because
    many consumer devices update it in coarse, delayed steps.
    """
    points = [r for r in rows if start <= parse(r["occurred_at"]) <= finish and r.get("numeric_value") is not None]
    if len(points) < 2:
        return None
    total = 0.0
    for current, following in zip(points, points[1:]):
        seconds = max(0.0, (parse(following["occurred_at"]) - parse(current["occurred_at"])).total_seconds())
        average_power = (float(current["numeric_value"]) + float(following["numeric_value"])) / 2.0
        total += average_power * seconds / 3600.0
    return total


def _temperature_trend(rows):
    values = [r for r in rows if r.get("numeric_value") is not None]
    if len(values) < 2:
        return "unknown", None
    recent = values[-4:]
    first, last = recent[0], recent[-1]
    minutes = max((parse(last["occurred_at"]) - parse(first["occurred_at"])).total_seconds() / 60.0, 0.01)
    slope = (float(last["numeric_value"]) - float(first["numeric_value"])) / minutes
    if abs(slope) < 0.02:
        return "stable", slope
    return ("rising" if slope > 0 else "falling"), slope


def _build_access_sessions(door_events, end):
    raw = []
    opened = None
    for event in door_events:
        state = event.get("text_value")
        when = parse(event["occurred_at"])
        if state == "open" and opened is None:
            opened = event
        elif state == "closed" and opened is not None:
            raw.append({
                "opened_at": parse(opened["occurred_at"]),
                "closed_at": when,
                "open_seconds": max(0, round((when - parse(opened["occurred_at"])).total_seconds())),
                "access_count": 1,
            })
            opened = None
    if opened is not None:
        raw.append({
            "opened_at": parse(opened["occurred_at"]),
            "closed_at": None,
            "open_seconds": max(0, round((end - parse(opened["occurred_at"])).total_seconds())),
            "access_count": 1,
        })

    sessions = []
    for item in raw:
        if not sessions:
            sessions.append(item)
            continue
        previous = sessions[-1]
        if previous["closed_at"] and item["opened_at"] and (item["opened_at"] - previous["closed_at"]).total_seconds() <= ACCESS_SESSION_GAP_SECONDS:
            previous["closed_at"] = item["closed_at"]
            previous["open_seconds"] += item["open_seconds"]
            previous["access_count"] += 1
        else:
            sessions.append(item)
    return sessions


def _thermal_excursions(temp_rows, optimal, end):
    excursions = []
    current = None
    for row in temp_rows:
        value = float(row["numeric_value"])
        inside = _in_range(value, optimal.get("min"), optimal.get("max"))
        when = parse(row["occurred_at"])
        if not inside and current is None:
            current = {"started_at": when, "start_value": value, "values": [(when, value)]}
        elif current is not None:
            current["values"].append((when, value))
            if inside:
                current["ended_at"] = when
                excursions.append(current)
                current = None
    if current is not None:
        current["ended_at"] = None
        current["observation_end"] = end
        excursions.append(current)
    return excursions


def calculate_tca(rows, asset, bindings, start, end):
    kinds = ("temperature", "humidity", "door", "power", "voltage", "current", "energy")
    by = {kind: [] for kind in kinds}
    for row in rows:
        if row["kind"] in by:
            by[row["kind"]].append(row)
    for values in by.values():
        values.sort(key=lambda row: row["occurred_at"])

    bound_kinds = {b["kind"] for b in bindings if b.get("enabled", True)}
    capabilities = {
        "temperature": bool(by["temperature"] or "temperature" in bound_kinds),
        "humidity": bool(by["humidity"] or "humidity" in bound_kinds),
        "door": bool(by["door"] or "door" in bound_kinds),
        "power": bool(by["power"] or "power" in bound_kinds),
        "voltage": bool(by["voltage"] or "voltage" in bound_kinds),
        "current": bool(by["current"] or "current" in bound_kinds),
        "energy_total": bool(by["energy"] or "energy" in bound_kinds),
    }
    capabilities.update({
        "thermal_monitoring": capabilities["temperature"],
        "thermal_excursion_analysis": capabilities["temperature"],
        "door_event_analysis": capabilities["door"],
        "door_correlated_recovery": capabilities["temperature"] and capabilities["door"],
        "energy_analysis": capabilities["power"],
        "energy_correlated_recovery": capabilities["temperature"] and capabilities["power"],
        "multi_zone_analysis": len({b["source_id"] for b in bindings if b["kind"] == "temperature" and b.get("enabled", True)}) > 1,
    })

    latest = {kind: (values[-1] if values else None) for kind, values in by.items()}
    temps = [float(r["numeric_value"]) for r in by["temperature"] if r.get("numeric_value") is not None]
    powers = [float(r["numeric_value"]) for r in by["power"] if r.get("numeric_value") is not None]
    ranges = _profile_ranges(asset)
    optimal, attention, critical = ranges["optimal"], ranges["attention"], ranges["critical"]

    primary_ids = [b["source_id"] for b in bindings if b["kind"] == "temperature" and b.get("is_primary")]
    temp_rows = [r for r in by["temperature"] if not primary_ids or r["source_id"] in primary_ids]
    if not temp_rows:
        temp_rows = by["temperature"]

    access_sessions = _build_access_sessions(by["door"], end) if capabilities["door"] else []
    episodes = []
    for idx, session in enumerate(access_sessions):
        opened_at, closed_at = session["opened_at"], session["closed_at"]
        if closed_at is None:
            episodes.append({
                "event_type": "access_session",
                "opened_at": opened_at.isoformat(),
                "closed_at": None,
                "open_seconds": session["open_seconds"],
                "access_count": session["access_count"],
                "status": "open",
                "energy_final": False,
                "temperature_samples": 0,
                "correlation": "door",
            })
            continue
        next_open = access_sessions[idx + 1]["opened_at"] if idx + 1 < len(access_sessions) else None
        observation_limit = min(end, closed_at + timedelta(minutes=OBSERVATION_WINDOW_MINUTES))
        analysis_end = min(observation_limit, next_open) if next_open else observation_limit
        before = [t for t in temp_rows if parse(t["occurred_at"]) <= opened_at]
        baseline = float(before[-1]["numeric_value"]) if before else None
        observed = [t for t in temp_rows if closed_at <= parse(t["occurred_at"]) <= analysis_end]
        values = [float(t["numeric_value"]) for t in observed if t.get("numeric_value") is not None]
        impact = max((abs(value - baseline) for value in values), default=None) if baseline is not None else None
        out_of_optimal_seen = any(not _in_range(value, optimal.get("min"), optimal.get("max")) for value in values)
        recovered = None
        if out_of_optimal_seen:
            for item in observed:
                if _in_range(float(item["numeric_value"]), optimal.get("min"), optimal.get("max")):
                    recovered = item
                    break
        elapsed_since_close = max(0.0, (end - closed_at).total_seconds())
        interrupted = bool(next_open and next_open <= observation_limit and not recovered)
        enough_time = elapsed_since_close >= OBSERVATION_WINDOW_MINUTES * 60
        if recovered:
            status, final_at = "recovered", parse(recovered["occurred_at"])
        elif interrupted:
            status, final_at = "interrupted", next_open
        elif not observed:
            status, final_at = ("insufficient_data" if enough_time else "observing"), analysis_end
        elif not out_of_optimal_seen and (impact is None or impact < MEASURABLE_IMPACT_C):
            status, final_at = "no_measurable_impact", analysis_end
        elif enough_time:
            status, final_at = "not_recovered", observation_limit
        else:
            status, final_at = "observing", analysis_end
        recovery_minutes = (parse(recovered["occurred_at"]) - closed_at).total_seconds() / 60.0 if recovered else None
        energy_wh = _power_wh(by["power"], closed_at, final_at) if capabilities["power"] else None
        episodes.append({
            "event_type": "access_session",
            "opened_at": opened_at.isoformat(),
            "closed_at": closed_at.isoformat(),
            "open_seconds": session["open_seconds"],
            "access_count": session["access_count"],
            "baseline_temperature_c": rnd(baseline),
            "maximum_temperature_c": rnd(max(values)) if values else None,
            "minimum_temperature_c": rnd(min(values)) if values else None,
            "thermal_impact_c": rnd(impact),
            "recovered_at": recovered["occurred_at"] if recovered else None,
            "recovery_minutes": rnd(recovery_minutes),
            "recovery_energy_wh": rnd(energy_wh, 3),
            "energy_final": status in {"recovered", "interrupted", "no_measurable_impact", "not_recovered"},
            "temperature_samples": len(values),
            "status": status,
            "correlation": "door",
        })

    # When no door exists, recovery is still a valid thermal concept; only its cause is unknown.
    thermal_excursions = []
    if capabilities["temperature"] and not capabilities["door"]:
        for exc in _thermal_excursions(temp_rows, optimal, end):
            started = exc["started_at"]
            finished = exc.get("ended_at") or end
            values = [v for _, v in exc["values"]]
            energy_wh = _power_wh(by["power"], started, finished) if capabilities["power"] else None
            thermal_excursions.append({
                "event_type": "thermal_excursion",
                "started_at": started.isoformat(),
                "ended_at": exc.get("ended_at").isoformat() if exc.get("ended_at") else None,
                "duration_minutes": rnd((finished - started).total_seconds() / 60.0),
                "maximum_temperature_c": rnd(max(values)) if values else None,
                "minimum_temperature_c": rnd(min(values)) if values else None,
                "recovery_energy_wh": rnd(energy_wh, 3),
                "energy_final": bool(exc.get("ended_at")),
                "status": "recovered" if exc.get("ended_at") else "observing",
                "correlation": "unidentified",
            })

    current_door = latest["door"]["text_value"] if latest["door"] else "unknown"
    current_temp = latest["temperature"]["numeric_value"] if latest["temperature"] else None
    trend, slope = _temperature_trend(temp_rows)
    thermal_classification = classify_profile_value(current_temp, ranges)
    profile_validation = validate_envelopes(ranges)
    in_optimal = thermal_classification.get("level") == "ideal"
    in_attention = thermal_classification.get("level") in {"ideal", "attention"}
    in_critical = thermal_classification.get("level") in {"ideal", "attention", "elevated_alert"}
    recovering_direction = False
    if current_temp is not None:
        if optimal.get("max") is not None and float(current_temp) > float(optimal["max"]):
            recovering_direction = trend == "falling"
        elif optimal.get("min") is not None and float(current_temp) < float(optimal["min"]):
            recovering_direction = trend == "rising"
    if current_temp is None:
        state = "no_data"
    elif capabilities["door"] and current_door == "open":
        state = "door_open"
    elif in_optimal:
        state = "stable"
    elif in_attention and recovering_direction:
        state = "recovering"
    elif thermal_classification.get("level") == "attention":
        state = "attention"
    elif thermal_classification.get("level") == "elevated_alert":
        state = "elevated_alert"
    else:
        state = "critical"

    timeline = [{
        "occurred_at": r["occurred_at"],
        "source_id": r["source_id"],
        "source_name": r.get("source_name"),
        "kind": r["kind"],
        "role": r.get("role"),
        "value": r.get("text_value") if r["kind"] == "door" else r.get("numeric_value"),
        "unit": r.get("unit"),
    } for r in rows]

    recoveries = [e["recovery_minutes"] for e in episodes if e.get("recovery_minutes") is not None]
    metadata = asset.get("metadata") or {}
    return {
        "asset": asset,
        "scope": {
            "organization": metadata.get("organization"),
            "site": metadata.get("site"),
            "area": metadata.get("area"),
        },
        "period": {"start": start.isoformat().replace("+00:00", "Z"), "end": end.isoformat().replace("+00:00", "Z")},
        "capabilities": capabilities,
        "profile_ranges": ranges,
        "current": {
            "state": state,
            "temperature_c": rnd(current_temp),
            "humidity_pct": rnd(latest["humidity"]["numeric_value"]) if latest["humidity"] else None,
            "door": current_door,
            "power_w": rnd(latest["power"]["numeric_value"]) if latest["power"] else None,
            "voltage_v": rnd(latest["voltage"]["numeric_value"]) if latest["voltage"] else None,
            "current_a": rnd(latest["current"]["numeric_value"]) if latest["current"] else None,
            "in_range": in_optimal,
            "in_optimal": in_optimal,
            "in_attention": in_attention,
            "in_critical": in_critical,
            "trend": trend,
            "trend_c_per_min": rnd(slope, 3),
            "thermal_classification": thermal_classification,
            "profile_validation": profile_validation,
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
            "door_openings": sum(e.get("access_count", 0) for e in episodes),
            "access_sessions": len([e for e in episodes if e.get("closed_at")]),
            "door_open_seconds": sum(e.get("open_seconds", 0) for e in episodes),
            "average_recovery_minutes": rnd(fmean(recoveries)) if recoveries else None,
            "recovered_episodes": len(recoveries),
            "observing_episodes": len([e for e in episodes if e.get("status") == "observing"]),
            "interrupted_episodes": len([e for e in episodes if e.get("status") == "interrupted"]),
            "thermal_excursions": len(thermal_excursions),
        },
        "episodes": episodes,
        "thermal_excursions": thermal_excursions,
        "bindings": bindings,
        "timeline": timeline,
    }
