from __future__ import annotations
import logging,threading,time
from typing import Any
from database import FlowDatabase
from ha_client import HomeAssistantClient
from normalizer import normalize_event
from observation import extract_vision_observation, sanitize_vision_event
from environmental import extract_environmental_measurement
from tca import extract_tca_measurements
from experience import DEFAULT_EMOTION_WEIGHTS
from modules.lca.extractor import extract_lca_events
from modules.ita.extractor import extract_ita_snapshot
LOGGER=logging.getLogger(__name__)

class FlowService:
    def __init__(self,db:FlowDatabase,ha:HomeAssistantClient,publish_to_ha:bool,settings):
        self.db=db;self.ha=ha;self.publish_to_ha=publish_to_ha;self.settings=settings;self._lock=threading.RLock()
        self.weights=dict(DEFAULT_EMOTION_WEIGHTS)
        self.lca_repository=None
        self.ita_repository=None

    def _source_enabled(self,source_id):
        enabled=self.settings.human_experience_enabled_sources
        return not enabled or source_id in enabled

    def ingest(self,payload:dict[str,Any],transport='api',ha_event_type=None):
        original=dict(payload)
        observation=extract_vision_observation(original) if self.settings.observation_engine_enabled and self.settings.human_experience_enabled else None
        environmental=extract_environmental_measurement(original,ha_event_type,self.settings.config_dir) if self.settings.environmental_storage_enabled else None
        tca_measurements=extract_tca_measurements(original,ha_event_type)
        lca_events=extract_lca_events(original,ha_event_type,self.settings.lca_topic_prefixes) if self.settings.lca_enabled else []
        ita_snapshot=extract_ita_snapshot(original,ha_event_type) if getattr(self.settings,'ita_enabled',True) else None
        if observation:
            payload=sanitize_vision_event(original)
        event=normalize_event(payload,transport=transport,ha_event_type=ha_event_type)
        hea_result=None
        with self._lock:
            inserted=self.db.insert_event(event)
            if inserted:
                self.db.apply_state(event)
                if observation:
                    if not self._source_enabled(observation['source_id']):
                        hea_result={'status':'source_disabled','source_id':observation['source_id']}
                    elif observation['confidence'] < self.settings.human_experience_minimum_confidence:
                        hea_result={'status':'low_confidence','confidence':observation['confidence'],'minimum_confidence':self.settings.human_experience_minimum_confidence}
                    else:
                        self.db.insert_observation(observation)
                        hea_result=self.db.aggregate_observation_window(observation,self.settings.human_experience_aggregation_window_minutes,self.settings.human_experience_minimum_samples,self.weights)
                if environmental:
                    environmental_inserted=self.db.insert_environmental_measurement(environmental)
                    if environmental_inserted:
                        LOGGER.info('Medição ambiental armazenada: %s | %.2f °C | %.2f%% | %s',environmental['source_id'],environmental['temperature_c'],environmental['humidity_pct'],environmental['condition'])
                    else:
                        LOGGER.info('Medição ambiental duplicada ignorada: %s',environmental['source_event_id'])
                if tca_measurements:
                    tca_inserted=self.db.insert_tca_measurements(tca_measurements)
                    if tca_inserted:LOGGER.info('TCA armazenou %s medição(ões)',tca_inserted)
                if lca_events and self.lca_repository:
                    lca_inserted=self.lca_repository.ingest(lca_events)
                    if lca_inserted:LOGGER.info('LCA armazenou %s evento(s)',lca_inserted)
                if ita_snapshot and self.ita_repository:
                    ita_inserted=self.ita_repository.ingest(ita_snapshot)
                    if ita_inserted:LOGGER.info('ITA armazenou %s medição(ões) para %s',ita_inserted,ita_snapshot['system_name'])
                self.publish_summary();LOGGER.info('Evento ingerido: %s | %s | %s',event['event_type'],event['event_id'],event['source'])
            else:LOGGER.info('Evento duplicado ignorado: %s',event['event_id'])
        event.pop('_flat',None)
        if hea_result is not None:event['human_experience']=hea_result
        return event,inserted

    def ingest_observation(self,payload):
        if not self.settings.observation_engine_enabled: return {'status':'disabled'},False
        metric=str(payload.get('metric_type') or payload.get('type') or '')
        if metric!='facial_expression': raise ValueError('Nesta versão, apenas facial_expression é suportado')
        from observation import normalize_expression
        import uuid
        from datetime import datetime,timezone
        obs={'observation_id':str(payload.get('observation_id') or ('obs_'+uuid.uuid4().hex)),'metric_type':'facial_expression','provider':str(payload.get('provider') or 'external'),'source_id':str(payload.get('source_id') or 'unknown_source'),'source_name':str(payload.get('source_name') or payload.get('source_id') or 'Fonte desconhecida'),'location_id':payload.get('location_id'),'occurred_at':str(payload.get('occurred_at') or datetime.now(timezone.utc).isoformat()),'value':normalize_expression(payload.get('value')),'raw_value':str(payload.get('value') or ''),'confidence':float(payload.get('confidence') or 0)}
        if not self.settings.human_experience_enabled:return {'status':'hea_disabled'},False
        if not self._source_enabled(obs['source_id']):return {'status':'source_disabled'},False
        if obs['confidence']>1:obs['confidence']/=100.0
        if obs['confidence']<self.settings.human_experience_minimum_confidence:return {'status':'low_confidence','confidence':obs['confidence']},False
        inserted=self.db.insert_observation(obs)
        result=self.db.aggregate_observation_window(obs,self.settings.human_experience_aggregation_window_minutes,self.settings.human_experience_minimum_samples,self.weights) if inserted else {'status':'duplicate'}
        return result,inserted

    def publish_connection(self,status):
        if self.publish_to_ha:self.ha.publish_sensor('sensor.seiden_flow_ha_connection',status,{'friendly_name':'Seiden FLOW — conexão HA','icon':'mdi:lan-connect'})
    def publish_summary(self):
        if not self.publish_to_ha:return
        s=self.db.summary();operational=self.db.operational_summary();common={'friendly_name':'Seiden FLOW','icon':'mdi:database-cog','summary':s,'operational':operational}
        self.ha.publish_sensor('sensor.seiden_flow_people_inside',s['people_inside'],{**common,'unit_of_measurement':'pessoas'})
        self.ha.publish_sensor('sensor.seiden_flow_events_today',operational['occurrences_today'],{**common,'friendly_name':'Seiden FLOW — ocorrências hoje','unit_of_measurement':'ocorrências'})
        self.ha.publish_sensor('sensor.seiden_flow_vision_analyses_today',operational['analyses_today'],{**common,'friendly_name':'Seiden FLOW — análises Vision hoje','unit_of_measurement':'análises'})
        self.ha.publish_sensor('sensor.seiden_flow_sources_offline',s['sources_offline'],{**common,'unit_of_measurement':'fontes'})
        hea=self.db.hea_summary(24,self.settings.human_experience_minimum_samples)
        self.ha.publish_sensor('sensor.seiden_flow_experience_index',hea.get('experience_index') if hea.get('experience_index') is not None else 'unknown',{'friendly_name':'Seiden FLOW — Experience Index','icon':'mdi:emoticon-outline','status':hea.get('status'),'classification':hea.get('classification'),'trend':hea.get('trend'),'delta':hea.get('delta'),'delta_percentage':hea.get('delta_percentage'),'previous_experience_index':hea.get('previous_experience_index'),'sample_count':hea.get('sample_count'),'average_confidence':hea.get('average_confidence'),'dominant_expression':hea.get('dominant_expression'),'distribution':hea.get('distribution'),'best_period':hea.get('best_period'),'worst_period':hea.get('worst_period')})
        self.publish_connection(self.ha.connection_status)
    def start_cleanup(self,days,hours):
        def event_loop():
            while True:
                time.sleep(max(1,hours)*3600);n=self.db.cleanup(days)
                if n:LOGGER.info('Retenção removeu %s evento(s)',n)
        def observation_loop():
            while True:
                time.sleep(60);o=self.db.cleanup_raw_observations(self.settings.hea_observation_retention_days)
                if o:LOGGER.info('Retenção HEA removeu %s observação(ões) anônima(s)',o)
        threading.Thread(target=event_loop,daemon=True,name='event-retention').start()
        threading.Thread(target=observation_loop,daemon=True,name='observation-privacy').start()
