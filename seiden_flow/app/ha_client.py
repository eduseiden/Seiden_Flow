from __future__ import annotations
import json, logging, os, threading, time
from typing import Callable
import requests, websocket
LOGGER=logging.getLogger(__name__); SUPERVISOR_TOKEN=os.getenv("SUPERVISOR_TOKEN","")

class HomeAssistantClient:
    def __init__(self):
        self.headers={"Authorization":f"Bearer {SUPERVISOR_TOKEN}","Content-Type":"application/json"}
        self._status="disabled" if not SUPERVISOR_TOKEN else "disconnected"; self._status_lock=threading.Lock()
    @property
    def connection_status(self):
        with self._status_lock: return self._status
    def _set_status(self, status, callback=None):
        changed=status!=self.connection_status
        with self._status_lock: self._status=status
        if changed and callback:
            try: callback(status)
            except Exception: LOGGER.exception("Falha no callback de status do HA")
    def publish_sensor(self, entity_id, state, attributes):
        if not SUPERVISOR_TOKEN:return
        try: requests.post(f"http://supervisor/core/api/states/{entity_id}",headers=self.headers,json={"state":state,"attributes":attributes},timeout=5).raise_for_status()
        except Exception as exc: LOGGER.warning("Falha ao publicar %s no Home Assistant: %s",entity_id,exc)
    def start_event_listener(self,event_types:list[str],callback:Callable[[str,dict],None],status_callback=None):
        t=threading.Thread(target=self._listen_forever,args=(event_types,callback,status_callback),daemon=True,name="ha-events");t.start();return t
    def _listen_forever(self,event_types,callback,status_callback):
        if not SUPERVISOR_TOKEN:
            LOGGER.warning("SUPERVISOR_TOKEN ausente; assinatura de eventos HA desabilitada");self._set_status("disabled",status_callback);return
        delay=2
        while True:
            ws=None
            try:
                self._set_status("connecting",status_callback)
                ws=websocket.create_connection("ws://supervisor/core/websocket",timeout=15,enable_multithread=True)
                hello=json.loads(ws.recv())
                if hello.get("type")!="auth_required": raise RuntimeError(f"Handshake inesperado: {hello}")
                ws.send(json.dumps({"type":"auth","access_token":SUPERVISOR_TOKEN}))
                auth=json.loads(ws.recv())
                if auth.get("type")!="auth_ok": raise RuntimeError(f"Autenticação recusada: {auth}")
                for idx,event_type in enumerate(event_types,start=1): ws.send(json.dumps({"id":idx,"type":"subscribe_events","event_type":event_type}))
                ws.settimeout(None)
                self._set_status("connected",status_callback);delay=2
                LOGGER.info("Assinando eventos do Home Assistant: %s",", ".join(event_types))
                stop=threading.Event()
                def heartbeat():
                    while not stop.wait(25):
                        try: ws.ping("seiden-flow")
                        except Exception: return
                threading.Thread(target=heartbeat,daemon=True,name="ha-heartbeat").start()
                try:
                    while True:
                        raw=ws.recv()
                        if raw is None: raise ConnectionError("WebSocket encerrado")
                        msg=json.loads(raw)
                        if msg.get("type")!="event": continue
                        event=msg.get("event") or {};callback(str(event.get("event_type") or "unknown"),event.get("data") or {})
                finally: stop.set()
            except Exception as exc:
                self._set_status("reconnecting",status_callback)
                LOGGER.warning("Conexão com eventos do HA interrompida: %s. Reconectando em %ss.",exc,delay)
                time.sleep(delay);delay=min(delay*2,60)
            finally:
                if ws:
                    try: ws.close()
                    except Exception: pass
