from __future__ import annotations

import logging
import threading
import time
from typing import Any

from database import FlowDatabase
from ha_client import HomeAssistantClient
from normalizer import normalize_event

LOGGER = logging.getLogger(__name__)


class FlowService:
    def __init__(self, db: FlowDatabase, ha: HomeAssistantClient, publish_to_ha: bool):
        self.db = db
        self.ha = ha
        self.publish_to_ha = publish_to_ha
        self._lock = threading.RLock()

    def ingest(self, payload: dict[str, Any], transport: str = "api", ha_event_type: str | None = None) -> tuple[dict, bool]:
        event = normalize_event(payload, transport=transport, ha_event_type=ha_event_type)
        with self._lock:
            inserted = self.db.insert_event(event)
            if inserted:
                self.db.apply_state(event)
                self.publish_summary()
                LOGGER.info("Evento ingerido: %s | %s | %s", event["event_type"], event["event_id"], event["source"])
            else:
                LOGGER.info("Evento duplicado ignorado: %s", event["event_id"])
        event.pop("_flat", None)
        return event, inserted

    def publish_summary(self) -> None:
        if not self.publish_to_ha:
            return
        summary = self.db.summary()
        common = {"friendly_name": "Seiden FLOW", "icon": "mdi:database-cog", "summary": summary}
        self.ha.publish_sensor("sensor.seiden_flow_people_inside", summary["people_inside"], {**common, "unit_of_measurement": "pessoas"})
        self.ha.publish_sensor("sensor.seiden_flow_events_today", summary["events_today"], {**common, "unit_of_measurement": "eventos"})
        self.ha.publish_sensor("sensor.seiden_flow_sources_offline", summary["sources_offline"], {**common, "unit_of_measurement": "fontes"})

    def start_cleanup(self, retention_days: int, interval_hours: int) -> None:
        def loop():
            while True:
                time.sleep(max(1, interval_hours) * 3600)
                removed = self.db.cleanup(retention_days)
                if removed:
                    LOGGER.info("Retenção removeu %s evento(s)", removed)
        threading.Thread(target=loop, daemon=True, name="retention").start()
