from __future__ import annotations

import csv
import io
import json
import logging
import os
from functools import wraps

from flask import Flask, Response, jsonify, render_template, request

from config import load_settings
from database import FlowDatabase
from ha_client import HomeAssistantClient
from service import FlowService
from version import VERSION, SCHEMA_VERSION

settings = load_settings()
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
LOGGER = logging.getLogger("seiden_flow")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = settings.webhook_max_body_mb * 1024 * 1024

db = FlowDatabase(os.path.join(settings.config_dir, "seiden_flow.db"))
ha = HomeAssistantClient()
service = FlowService(db, ha, settings.publish_summary_to_home_assistant)
service.publish_summary()
service.start_cleanup(settings.retention_days, settings.cleanup_interval_hours)
if settings.subscribe_home_assistant_events:
    ha.start_event_listener([settings.bridge_presence_event, settings.bridge_online_event, settings.bridge_offline_event],
                            lambda event_type, data: service.ingest(data, transport="home_assistant_event", ha_event_type=event_type))


def require_api_key(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if settings.api_key:
            token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            if token != settings.api_key:
                return jsonify({"error": "unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapped


@app.get("/")
def dashboard():
    return render_template("dashboard.html", version=VERSION, summary=db.summary(), events=db.list_events(limit=20), people=db.people_inside(), sources=db.sources_state())


@app.get("/health")
@app.get("/api/v1/health")
def health():
    return jsonify({"status": "ok", "service": "seiden_flow", "version": VERSION, "schema_version": SCHEMA_VERSION})


@app.post("/api/v1/events")
@app.post("/api/v1/ingest")
@require_api_key
def ingest():
    payload = request.get_json(silent=False)
    event, inserted = service.ingest(payload, transport="api")
    return jsonify({"accepted": inserted, "duplicate": not inserted, "event": event}), 201 if inserted else 200


@app.get("/api/v1/events")
def events():
    limit = int(request.args.get("limit", 100))
    return jsonify({"items": db.list_events(limit=limit, event_type=request.args.get("event_type"), person=request.args.get("person"))})


@app.get("/api/v1/state/people")
def people_state():
    return jsonify({"items": db.people_state()})


@app.get("/api/v1/state/people/inside")
def people_inside():
    items = db.people_inside()
    return jsonify({"count": len(items), "items": items})


@app.get("/api/v1/state/sources")
def sources_state():
    return jsonify({"items": db.sources_state()})


@app.get("/api/v1/summary")
def summary():
    return jsonify(db.summary())


@app.get("/api/v1/export/events.json")
def export_json():
    data = db.list_events(limit=min(int(request.args.get("limit", 5000)), 5000))
    return Response(json.dumps(data, ensure_ascii=False, indent=2), mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=seiden-flow-events.json"})


@app.get("/api/v1/export/events.csv")
def export_csv():
    data = db.list_events(limit=min(int(request.args.get("limit", 5000)), 5000))
    out = io.StringIO()
    fields = ["event_id", "event_type", "source", "timestamp", "reader_id", "reader_name", "person_id", "person_name", "action"]
    writer = csv.DictWriter(out, fieldnames=fields); writer.writeheader()
    for e in data:
        writer.writerow({
            "event_id": e.get("event_id"), "event_type": e.get("event_type"), "source": e.get("source"), "timestamp": e.get("timestamp"),
            "reader_id": (e.get("reader") or {}).get("id"), "reader_name": (e.get("reader") or {}).get("name"),
            "person_id": (e.get("person") or {}).get("id"), "person_name": (e.get("person") or {}).get("name"),
            "action": (e.get("operation") or {}).get("action"),
        })
    return Response(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=seiden-flow-events.csv"})


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "payload_too_large"}), 413


LOGGER.info("Seiden FLOW %s iniciado", VERSION)
