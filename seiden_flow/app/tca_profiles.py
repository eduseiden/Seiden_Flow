from __future__ import annotations

from typing import Any

from profile_configs import load_tca_profile_catalog


def load_tca_profiles(config_dir: str) -> dict[str, Any]:
    """Load the Flow-owned TCA catalog from config_tca.json."""
    return load_tca_profile_catalog(config_dir)


def resolve_tca_asset(data: dict[str, Any], config_dir: str) -> dict[str, Any]:
    out = dict(data or {})
    catalog = load_tca_profiles(config_dir)
    profiles = {profile["profile_id"]: profile for profile in catalog["items"]}
    profile_id = str(out.get("profile_id") or out.get("asset_type") or "").strip()
    profile = profiles.get(profile_id)
    if not profile:
        raise ValueError("perfil TCA inválido ou indisponível")

    optimal = (profile.get("temperature") or {}).get("optimal") or {}
    out["profile_id"] = profile_id
    out["asset_type"] = str(out.get("asset_type") or profile_id)
    out["min_temperature_c"] = optimal.get("min")
    out["max_temperature_c"] = optimal.get("max")
    out["humidity_enabled"] = bool(profile.get("humidity"))
    metadata = dict(out.get("metadata") or {})
    metadata["profile_snapshot"] = {
        "label": profile.get("label"),
        "ruleset": profile.get("ruleset"),
        "temperature": profile.get("temperature"),
        "humidity": profile.get("humidity"),
        "source": catalog.get("source"),
        "schema_version": catalog.get("schema_version"),
    }
    out["metadata"] = metadata
    return out
