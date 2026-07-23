from __future__ import annotations
import logging,threading,time
from typing import Any
from database import FlowDatabase
from ha_client import HomeAssistantClient
from normalizer import normalize_event
LOGGER=logging.getLogger(__name__)
class FlowService:
    def __init__(self,db:FlowDatabase,ha:HomeAssistantClient,publish_to_ha:bool):self.db=db;self.ha=ha;self.publish_to_ha=publish_to_ha;self._lock=threading.RLock()
    def ingest(self,payload:dict[str,Any],transport='api',ha_event_type=None):
        event=normalize_event(payload,transport=transport,ha_event_type=ha_event_type)
        with self._lock:
            inserted=self.db.insert_event(event)
            if inserted:self.db.apply_state(event);self.publish_summary();LOGGER.info('Evento ingerido: %s | %s | %s',event['event_type'],event['event_id'],event['source'])
            else:LOGGER.info('Evento duplicado ignorado: %s',event['event_id'])
        event.pop('_flat',None);return event,inserted
    def publish_connection(self,status):
        if self.publish_to_ha:self.ha.publish_sensor('sensor.seiden_flow_ha_connection',status,{'friendly_name':'Seiden FLOW — conexão HA','icon':'mdi:lan-connect'})
    def publish_summary(self):
        if not self.publish_to_ha:return
        s=self.db.summary();common={'friendly_name':'Seiden FLOW','icon':'mdi:database-cog','summary':s}
        self.ha.publish_sensor('sensor.seiden_flow_people_inside',s['people_inside'],{**common,'unit_of_measurement':'pessoas'})
        self.ha.publish_sensor('sensor.seiden_flow_events_today',s['events_today'],{**common,'unit_of_measurement':'eventos'})
        self.ha.publish_sensor('sensor.seiden_flow_sources_offline',s['sources_offline'],{**common,'unit_of_measurement':'fontes'})
        self.publish_connection(self.ha.connection_status)
    def start_cleanup(self,days,hours):
        def loop():
            while True:
                time.sleep(max(1,hours)*3600);n=self.db.cleanup(days)
                if n:LOGGER.info('Retenção removeu %s evento(s)',n)
        threading.Thread(target=loop,daemon=True,name='retention').start()
