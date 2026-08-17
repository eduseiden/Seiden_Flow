from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger("seiden_flow.profile_configs")

EEA_ANALYSIS_TYPES = {"human_comfort", "informational"}
TCA_ANALYSIS_TYPES = {"environmental_compliance"}

DEFAULT_EEA = {
    "schema_version": "1.0",
    "configuration_mode": "authoritative",
    "managed_by": "seiden_flow",
    "profiles": {
        "human_indoor": {
            "label": "Conforto humano interno",
            "analysis_type": "human_comfort",
            "ruleset": "seiden_environmental_profile_human_indoor_v1",
            "temperature": {
                "optimal": {"min": 20.0, "max": 26.0},
                "attention": {"min": 17.0, "max": 29.0},
                "critical": {"min": 12.0, "max": 34.0},
                "weight": 0.6,
            },
            "humidity": {
                "optimal": {"min": 40.0, "max": 65.0},
                "attention": {"min": 30.0, "max": 75.0},
                "critical": {"min": 20.0, "max": 85.0},
                "weight": 0.4,
            },
        },
        "human_outdoor": {
            "label": "Ambiente externo",
            "analysis_type": "informational",
            "ruleset": "seiden_environmental_profile_human_outdoor_v1",
            "temperature": {
                "optimal": {"min": 16.0, "max": 30.0},
                "attention": {"min": 8.0, "max": 36.0},
                "critical": {"min": 0.0, "max": 42.0},
                "weight": 0.7,
            },
            "humidity": {
                "optimal": {"min": 30.0, "max": 80.0},
                "attention": {"min": 20.0, "max": 90.0},
                "critical": {"min": 10.0, "max": 100.0},
                "weight": 0.3,
            },
        },
    },
}

DEFAULT_TCA = {
    "schema_version": "1.0",
    "configuration_mode": "authoritative",
    "managed_by": "seiden_flow",
    "profiles": {
        "refrigerator": {
            "label": "Geladeira",
            "analysis_type": "environmental_compliance",
            "ruleset": "seiden_environmental_profile_refrigerator_v1",
            "temperature": {
                "optimal": {"min": 1.0, "max": 5.0},
                "attention": {"min": -1.0, "max": 8.0},
                "critical": {"min": -3.0, "max": 10.0},
                "weight": 1.0,
            },
            "humidity": None,
        },
        "freezer": {
            "label": "Freezer",
            "analysis_type": "environmental_compliance",
            "ruleset": "seiden_environmental_profile_freezer_v1",
            "temperature": {
                "optimal": {"min": -24.0, "max": -16.0},
                "attention": {"min": -27.0, "max": -12.0},
                "critical": {"min": -30.0, "max": -5.0},
                "weight": 1.0,
            },
            "humidity": None,
        },
        "wine_cellar": {
            "label": "Adega de vinhos",
            "analysis_type": "environmental_compliance",
            "ruleset": "seiden_environmental_profile_wine_cellar_v1",
            "temperature": {
                "optimal": {"min": 12.0, "max": 18.0},
                "attention": {"min": 10.0, "max": 20.0},
                "critical": {"min": 7.0, "max": 24.0},
                "weight": 0.8,
            },
            "humidity": {
                "optimal": {"min": 50.0, "max": 80.0},
                "attention": {"min": 40.0, "max": 88.0},
                "critical": {"min": 30.0, "max": 95.0},
                "weight": 0.2,
            },
        },
        "beer_cooler": {
            "label": "Cervejeira",
            "analysis_type": "environmental_compliance",
            "ruleset": "seiden_environmental_profile_beer_cooler_v1",
            "temperature": {
                "optimal": {"min": 0.0, "max": 6.0},
                "attention": {"min": -2.0, "max": 9.0},
                "critical": {"min": -4.0, "max": 12.0},
                "weight": 1.0,
            },
            "humidity": None,
        },
    },
}


def _clone(data: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(data, ensure_ascii=False))


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("profiles"), dict):
        raise ValueError(f"catálogo de perfis inválido: {path}")
    return data


def _split_legacy(legacy: dict[str, Any], analysis_types: set[str], managed_by: str) -> dict[str, Any]:
    profiles = {}
    for profile_id, profile in legacy.get("profiles", {}).items():
        if isinstance(profile, dict) and str(profile.get("analysis_type") or "").strip() in analysis_types:
            profiles[str(profile_id)] = profile
    return {
        "schema_version": str(legacy.get("schema_version") or "1.0"),
        "configuration_mode": "authoritative",
        "managed_by": managed_by,
        "migrated_from": "/homeassistant/seiden_vision/environmental_profiles.json",
        "profiles": profiles,
    }


def ensure_profile_configs(config_dir: str) -> dict[str, str]:
    """Create Flow-owned EEA/TCA profile catalogs once, preserving legacy values.

    Existing Flow configuration files are never overwritten. If the old Vision catalog
    exists, it is split by analysis_type so the exact deployed ranges survive the move
    of business-rule ownership from Vision to Flow.
    """
    base = Path(config_dir)
    eea_path = base / "config_eea.json"
    tca_path = base / "config_tca.json"
    legacy_path = Path("/homeassistant/seiden_vision/environmental_profiles.json")

    legacy = None
    if (not eea_path.exists() or not tca_path.exists()) and legacy_path.exists():
        try:
            legacy = _load_json(legacy_path)
        except Exception as exc:
            LOGGER.warning("Não foi possível importar catálogo legado do Vision: %s", exc)

    if not eea_path.exists():
        payload = _split_legacy(legacy, EEA_ANALYSIS_TYPES, "seiden_flow") if legacy else _clone(DEFAULT_EEA)
        if not payload.get("profiles"):
            payload = _clone(DEFAULT_EEA)
        _atomic_write(eea_path, payload)
        LOGGER.info("[EEA] Catálogo de perfis criado em %s (%s)", eea_path, "migração Vision" if legacy else "defaults Flow")

    if not tca_path.exists():
        payload = _split_legacy(legacy, TCA_ANALYSIS_TYPES, "seiden_flow") if legacy else _clone(DEFAULT_TCA)
        if not payload.get("profiles"):
            payload = _clone(DEFAULT_TCA)
        _atomic_write(tca_path, payload)
        LOGGER.info("[TCA] Catálogo de perfis criado em %s (%s)", tca_path, "migração Vision" if legacy else "defaults Flow")

    return {"eea": str(eea_path), "tca": str(tca_path)}


def _catalog(path: Path, fallback: dict[str, Any], allowed_types: set[str]) -> dict[str, Any]:
    error = None
    try:
        data = _load_json(path)
        source = str(path)
    except Exception as exc:
        error = str(exc)
        data = _clone(fallback)
        source = "embedded_safety_fallback"
        LOGGER.error("Falha ao carregar %s; usando fallback de segurança: %s", path, exc)

    items = []
    for profile_id, profile in data.get("profiles", {}).items():
        if not isinstance(profile, dict):
            continue
        analysis_type = str(profile.get("analysis_type") or "").strip()
        if analysis_type not in allowed_types:
            continue
        items.append({
            "profile_id": str(profile_id),
            "label": profile.get("label") or str(profile_id),
            "analysis_type": analysis_type,
            "ruleset": profile.get("ruleset"),
            "temperature": profile.get("temperature"),
            "humidity": profile.get("humidity"),
            "humidity_enabled": bool(profile.get("humidity")),
        })
    items.sort(key=lambda item: (str(item.get("label") or "").lower(), item["profile_id"]))
    return {
        "schema_version": data.get("schema_version"),
        "configuration_mode": data.get("configuration_mode"),
        "managed_by": data.get("managed_by"),
        "source": source,
        "error": error,
        "items": items,
    }


def load_eea_profiles(config_dir: str) -> dict[str, Any]:
    ensure_profile_configs(config_dir)
    return _catalog(Path(config_dir) / "config_eea.json", DEFAULT_EEA, EEA_ANALYSIS_TYPES)


def load_tca_profile_catalog(config_dir: str) -> dict[str, Any]:
    ensure_profile_configs(config_dir)
    return _catalog(Path(config_dir) / "config_tca.json", DEFAULT_TCA, TCA_ANALYSIS_TYPES)


def eea_profile_map(config_dir: str) -> dict[str, dict[str, Any]]:
    return {item["profile_id"]: item for item in load_eea_profiles(config_dir)["items"]}


def eea_profile_ids(config_dir: str) -> set[str]:
    return set(eea_profile_map(config_dir))
