from __future__ import annotations

from flask import Blueprint, jsonify

from solutions.catalog import solution_catalog


def create_platform_blueprint(registry, version: str, schema_version: str):
    blueprint = Blueprint("platform", __name__)

    @blueprint.get("/api/v1/platform")
    def platform():
        return jsonify({
            "platform": "Seiden Flow",
            "architecture": "modular_foundation",
            "version": version,
            "schema_version": schema_version,
            "modules": registry.summary(),
        })

    @blueprint.get("/api/v1/platform/modules")
    def modules():
        return jsonify({"items": registry.public_catalog()})

    @blueprint.get("/api/v1/platform/modules/<module_id>")
    def module_detail(module_id: str):
        manifest = registry.get(module_id)
        if manifest is None:
            return jsonify({"error": "module_not_found", "module_id": module_id}), 404
        return jsonify(manifest.to_dict())

    @blueprint.get("/api/v1/platform/solutions")
    def solutions():
        return jsonify({"items": solution_catalog()})

    return blueprint
