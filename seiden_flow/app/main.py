from __future__ import annotations
import csv,io,json,logging,os
from functools import wraps
from flask import Flask,Response,jsonify,render_template,request
from config import load_settings
from database import FlowDatabase
from ha_client import HomeAssistantClient
from service import FlowService
from version import VERSION,SCHEMA_VERSION,DATABASE_SCHEMA_VERSION
settings=load_settings();logging.basicConfig(level=getattr(logging,settings.log_level.upper(),logging.INFO),format='%(asctime)s [%(levelname)s] %(name)s: %(message)s');LOGGER=logging.getLogger('seiden_flow')
app=Flask(__name__);app.config['MAX_CONTENT_LENGTH']=settings.webhook_max_body_mb*1024*1024
db=FlowDatabase(os.path.join(settings.config_dir,'seiden_flow.db'),settings.organization_id,settings.organization_name,settings.site_id,settings.site_name)
ha=HomeAssistantClient();service=FlowService(db,ha,settings.publish_summary_to_home_assistant,settings);service.publish_summary();service.start_cleanup(settings.retention_days,settings.cleanup_interval_hours)
if settings.subscribe_home_assistant_events:ha.start_event_listener([settings.bridge_presence_event,settings.bridge_online_event,settings.bridge_offline_event],lambda t,d:service.ingest(d,transport='home_assistant_event',ha_event_type=t),service.publish_connection)
def require_api_key(fn):
 @wraps(fn)
 def wrapped(*a,**kw):
  if settings.api_key and request.headers.get('Authorization','').removeprefix('Bearer ').strip()!=settings.api_key:return jsonify({'error':'unauthorized'}),401
  return fn(*a,**kw)
 return wrapped
@app.get('/')
def dashboard():return render_template('dashboard.html',version=VERSION,summary=db.summary(),events=db.list_events(limit=20),people=db.people_inside(),sources=db.sources_state(),ha_status=ha.connection_status,hea=db.hea_summary(24,settings.human_experience_minimum_samples),hea_sources=db.hea_sources(24),hea_history=db.hea_history(24,limit=96),hea_config={'minimum_samples':settings.human_experience_minimum_samples,'window_minutes':settings.human_experience_aggregation_window_minutes,'minimum_confidence':settings.human_experience_minimum_confidence})
@app.get('/health')
@app.get('/api/v1/health')
def health():return jsonify({'status':'ok','service':'seiden_flow','version':VERSION,'schema_version':SCHEMA_VERSION,'database_schema_version':DATABASE_SCHEMA_VERSION,'home_assistant_connection':ha.connection_status})
@app.post('/api/v1/events')
@app.post('/api/v1/ingest')
@require_api_key
def ingest():
 e,i=service.ingest(request.get_json(silent=False),transport='api');return jsonify({'accepted':i,'duplicate':not i,'event':e}),201 if i else 200
@app.get('/api/v1/events')
def events():return jsonify({'items':db.list_events(limit=int(request.args.get('limit',100)),event_type=request.args.get('event_type'),person=request.args.get('person'))})
@app.get('/api/v1/state/people')
def people_state():return jsonify({'items':db.people_state()})
@app.get('/api/v1/state/people/inside')
def people_inside():
 x=db.people_inside();return jsonify({'count':len(x),'items':x})
@app.get('/api/v1/state/sources')
def sources_state():return jsonify({'items':db.sources_state()})
@app.get('/api/v1/summary')
def summary():return jsonify(db.summary())
@app.get('/api/v1/dashboard-data')
def dashboard_data():
 return jsonify({'summary':db.summary(),'events':db.list_events(limit=20),'people':db.people_inside(),'home_assistant_connection':ha.connection_status,'version':VERSION,'human_experience':{'summary':db.hea_summary(24,settings.human_experience_minimum_samples),'sources':db.hea_sources(24),'history':db.hea_history(24,limit=96),'config':{'minimum_samples':settings.human_experience_minimum_samples,'window_minutes':settings.human_experience_aggregation_window_minutes,'minimum_confidence':settings.human_experience_minimum_confidence}}})

@app.post('/api/v1/observations')
@require_api_key
def ingest_observation():
 try:
  result,inserted=service.ingest_observation(request.get_json(silent=False))
  return jsonify({'accepted':inserted,'result':result}),201 if inserted else 200
 except ValueError as exc:return jsonify({'error':'invalid_observation','message':str(exc)}),400

@app.get('/api/v1/hea/summary')
def hea_summary():
 return jsonify(db.hea_summary(int(request.args.get('hours',24)),settings.human_experience_minimum_samples))

@app.get('/api/v1/hea/history')
def hea_history():
 return jsonify({'items':db.hea_history(int(request.args.get('hours',24)),request.args.get('source_id'),int(request.args.get('limit',500)))})

@app.get('/api/v1/hea/sources')
def hea_sources():
 return jsonify({'items':db.hea_sources(int(request.args.get('hours',24)))})

@app.get('/api/v1/hea/dashboard')
def hea_dashboard():
 hours=int(request.args.get('hours',24))
 return jsonify({'summary':db.hea_summary(hours,settings.human_experience_minimum_samples),'sources':db.hea_sources(hours),'history':db.hea_history(hours,limit=500),'config':{'enabled':settings.human_experience_enabled,'minimum_samples':settings.human_experience_minimum_samples,'aggregation_window_minutes':settings.human_experience_aggregation_window_minutes,'minimum_confidence':settings.human_experience_minimum_confidence,'raw_retention_minutes':settings.observation_retain_raw_minutes}})

@app.get('/api/v1/domain/organizations')
def organizations():return jsonify({'items':db.organizations()})
@app.get('/api/v1/domain/sites')
def sites():return jsonify({'items':db.sites()})
@app.get('/api/v1/domain/locations')
def locations():return jsonify({'items':db.locations()})
@app.get('/api/v1/domain/sources')
def sources():return jsonify({'items':db.sources()})
@app.get('/api/v1/domain/persons')
def persons():return jsonify({'items':db.persons()})
@app.get('/api/v1/domain/presences')
def presences():return jsonify({'items':db.presences()})
@app.get('/api/v1/export/events.json')
def export_json():return Response(json.dumps(db.list_events(limit=min(int(request.args.get('limit',5000)),5000)),ensure_ascii=False,indent=2),mimetype='application/json',headers={'Content-Disposition':'attachment; filename=seiden-flow-events.json'})
@app.get('/api/v1/export/events.csv')
def export_csv():
 data=db.list_events(limit=min(int(request.args.get('limit',5000)),5000));out=io.StringIO();fields=['event_id','event_type','source','timestamp','reader_id','reader_name','person_id','person_name','action'];w=csv.DictWriter(out,fieldnames=fields);w.writeheader()
 for e in data:w.writerow({'event_id':e.get('event_id'),'event_type':e.get('event_type'),'source':e.get('source'),'timestamp':e.get('timestamp'),'reader_id':(e.get('reader') or {}).get('id'),'reader_name':(e.get('reader') or {}).get('name'),'person_id':(e.get('person') or {}).get('id'),'person_name':(e.get('person') or {}).get('name'),'action':(e.get('operation') or {}).get('action')})
 return Response(out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=seiden-flow-events.csv'})
@app.errorhandler(413)
def too_large(_):return jsonify({'error':'payload_too_large'}),413
LOGGER.info('Seiden FLOW %s iniciado',VERSION)
