\
from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request


def create_era_blueprint(repo, service, version, ingress_path_fn, timezone_name):
    bp = Blueprint("era", __name__)

    @bp.get("/era")
    @bp.get("/intelligence/era")
    def portal():
        return render_template(
            "era_portal.html",
            version=version,
            ingress_path=ingress_path_fn(),
            display_timezone=timezone_name,
        )

    @bp.get("/api/v1/era/summary")
    def summary():
        return jsonify({
            **repo.summary(),
            "channels": service.configured_channels,
            "policy": {
                "critical_delay_minutes": service.settings.era_critical_delay_minutes,
                "warning_delay_minutes": service.settings.era_warning_delay_minutes,
                "telemetry_stale_minutes": service.settings.era_telemetry_stale_minutes,
                "notify_recovery": service.settings.era_notify_recovery,
            },
        })

    @bp.get("/api/v1/era/incidents")
    def incidents():
        return jsonify({"items": repo.list(request.args.get("state", "all"), request.args.get("limit", 200))})

    @bp.post("/api/v1/era/events")
    def ingest_event():
        body = request.get_json(silent=True) or {}
        try:
            result = service.ingest(body)
            return jsonify(result), 202
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.post("/api/v1/era/test/telegram")
    def test_telegram():
        result = service.test_telegram()
        return jsonify(result), 200 if result.get("ok") else 503

    @bp.post("/api/v1/era/test/email")
    def test_email():
        result = service.test_email()
        return jsonify(result), 200 if result.get("ok") else 503

    return bp
