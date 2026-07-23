from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Callable

import requests
import websocket

LOGGER = logging.getLogger(__name__)
SUPERVISOR_TOKEN = os.getenv("SUPERVISOR_TOKEN", "")


class HomeAssistantClient:
    def __init__(self):
        self.headers = {"Authorization": f"Bearer {SUPERVISOR_TOKEN}", "Content-Type": "application/json"}

    def publish_sensor(self, entity_id: str, state, attributes: dict) -> None:
        if not SUPERVISOR_TOKEN:
            return
        try:
            requests.post(f"http://supervisor/core/api/states/{entity_id}", headers=self.headers,
                          json={"state": state, "attributes": attributes}, timeout=5).raise_for_status()
        except Exception as exc:
            LOGGER.warning("Falha ao publicar %s no Home Assistant: %s", entity_id, exc)

    def start_event_listener(self, event_types: list[str], callback: Callable[[str, dict], None]) -> threading.Thread:
        thread = threading.Thread(target=self._listen_forever, args=(event_types, callback), daemon=True, name="ha-events")
        thread.start()
        return thread

    def _listen_forever(self, event_types: list[str], callback: Callable[[str, dict], None]) -> None:
        if not SUPERVISOR_TOKEN:
            LOGGER.warning("SUPERVISOR_TOKEN ausente; assinatura de eventos HA desabilitada")
            return
        while True:
            try:
                ws = websocket.create_connection("ws://supervisor/core/websocket", timeout=30)
                hello = json.loads(ws.recv())
                if hello.get("type") != "auth_required":
                    raise RuntimeError(f"Handshake inesperado: {hello}")
                ws.send(json.dumps({"type": "auth", "access_token": SUPERVISOR_TOKEN}))
                auth = json.loads(ws.recv())
                if auth.get("type") != "auth_ok":
                    raise RuntimeError(f"Autenticação recusada: {auth}")
                for idx, event_type in enumerate(event_types, start=1):
                    ws.send(json.dumps({"id": idx, "type": "subscribe_events", "event_type": event_type}))
                LOGGER.info("Assinando eventos do Home Assistant: %s", ", ".join(event_types))
                while True:
                    msg = json.loads(ws.recv())
                    if msg.get("type") != "event":
                        continue
                    event = msg.get("event") or {}
                    callback(str(event.get("event_type") or "unknown"), event.get("data") or {})
            except Exception as exc:
                LOGGER.warning("Conexão com eventos do HA interrompida: %s. Reconectando em 10s.", exc)
                time.sleep(10)
