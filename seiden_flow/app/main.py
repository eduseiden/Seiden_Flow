from __future__ import annotations
import csv,io,json,logging,os,threading,time
from datetime import datetime,timedelta,timezone
from functools import wraps
from flask import Flask,Response,abort,jsonify,make_response,redirect,render_template,request
from config import load_settings
from database import FlowDatabase
from ha_client import HomeAssistantClient
from service import FlowService
from version import VERSION,SCHEMA_VERSION,DATABASE_SCHEMA_VERSION
from environmental_analytics import calculate_environmental_analytics, period_bounds, utc_iso
from tca import extract_tca_measurements
from tca_analytics import calculate_tca
settings=load_settings();logging.basicConfig(level=getattr(logging,settings.log_level.upper(),logging.INFO),format='%(asctime)s [%(levelname)s] %(name)s: %(message)s');LOGGER=logging.getLogger('seiden_flow')

_ENV_CACHE_TTL_SECONDS=30
_ENV_CACHE_MAX_ITEMS=32
_ENV_CACHE={}
_ENV_CACHE_LOCK=threading.RLock()

def _env_cache_get(key):
 now=time.monotonic()
 with _ENV_CACHE_LOCK:
  item=_ENV_CACHE.get(key)
  if not item:return None
  expires,payload=item
  if expires<=now:
   _ENV_CACHE.pop(key,None);return None
  return payload

def _env_cache_put(key,payload):
 now=time.monotonic()
 with _ENV_CACHE_LOCK:
  expired=[k for k,(expires,_) in _ENV_CACHE.items() if expires<=now]
  for k in expired:_ENV_CACHE.pop(k,None)
  if len(_ENV_CACHE)>=_ENV_CACHE_MAX_ITEMS:
   oldest=next(iter(_ENV_CACHE),None)
   if oldest is not None:_ENV_CACHE.pop(oldest,None)
  _ENV_CACHE[key]=(now+_ENV_CACHE_TTL_SECONDS,payload)

def _timed_environment_call(label,fn):
 started=time.perf_counter()
 try:return fn()
 finally:
  elapsed=time.perf_counter()-started
  log=LOGGER.warning if elapsed>=0.5 else LOGGER.debug
  log('%s concluído em %.3f s',label,elapsed)
app=Flask(__name__);app.config['MAX_CONTENT_LENGTH']=settings.webhook_max_body_mb*1024*1024
db=FlowDatabase(os.path.join(settings.config_dir,'seiden_flow.db'),settings.organization_id,settings.organization_name,settings.site_id,settings.site_name)
ha=HomeAssistantClient();service=FlowService(db,ha,settings.publish_summary_to_home_assistant,settings);service.publish_summary();service.start_cleanup(settings.retention_days,settings.cleanup_interval_hours)
if settings.subscribe_home_assistant_events:
 event_types=[settings.bridge_event,settings.connection_online_event,settings.connection_offline_event]
 if settings.vision_event:
  event_types.append(settings.vision_event)
 if settings.environmental_storage_enabled and settings.environment_event:
  event_types.append(settings.environment_event)
 # Remove duplicidades preservando a ordem de configuração.
 event_types=list(dict.fromkeys(e for e in event_types if e))
 ha.start_event_listener(event_types,lambda t,d:service.ingest(d,transport='home_assistant_event',ha_event_type=t),service.publish_connection)

def _ingress_path() -> str:
 path=(request.headers.get('X-Ingress-Path') or '').split(',')[0].strip()
 return path.rstrip('/')

def _request_hostname() -> str:
 forwarded=(request.headers.get('X-Forwarded-Host') or '').split(',')[0].strip()
 host=forwarded or request.host
 # Hostnames are compared without port and trailing dot. IPv6 literals are not expected here.
 return host.split(':',1)[0].strip().lower().rstrip('.')

def _is_public_hea_host() -> bool:
 return bool(settings.hea_public_hostname and _request_hostname()==settings.hea_public_hostname)

@app.before_request
def restrict_public_hea_host():
 if not (settings.hea_public_restrict_routes and _is_public_hea_host()):
  return None
 if request.path=='/':
  return redirect('/hea',code=302)
 allowed_exact={'/hea','/api/v1/public/hea/dashboard'}
 if request.path in allowed_exact:
  return None
 # Do not disclose which operational routes exist on a public HEA hostname.
 abort(404)

def _parse_iso(value, default):
 if not value:return default
 try:
  parsed=datetime.fromisoformat(str(value).replace('Z','+00:00'))
  if parsed.tzinfo is None:parsed=parsed.replace(tzinfo=timezone.utc)
  return parsed.astimezone(timezone.utc)
 except ValueError:abort(400,description='Data/hora inválida')

def _portal_payload():
 end=_parse_iso(request.args.get('end'),datetime.now(timezone.utc))
 start_value=request.args.get('start')
 if start_value:start=_parse_iso(start_value,end-timedelta(hours=settings.hea_portal_default_hours))
 else:
  hours=max(1,min(87600,int(request.args.get('hours',settings.hea_portal_default_hours))))
  start=end-timedelta(hours=hours)
 if start>=end:abort(400,description='O início deve ser anterior ao fim')
 source_id=(request.args.get('source_id') or '').strip() or None
 location_id=(request.args.get('location_id') or '').strip() or None
 result=db.hea_query(start.isoformat(),end.isoformat(),settings.human_experience_minimum_samples,service.weights,source_id,location_id,96)
 return {
  'title':settings.hea_portal_title,'subtitle':settings.hea_portal_subtitle,
  'privacy_notice':settings.hea_portal_privacy_notice,'summary':result['summary'],
  'sources':result['sources'] if settings.hea_portal_show_sources else [],'history':result['history'],
  'filters':result['filters'],'updated_at':datetime.now(timezone.utc).isoformat(),'version':VERSION
 }

@app.after_request
def portal_cors(response):
 origin=request.headers.get('Origin')
 if origin and origin in settings.hea_portal_allowed_origins and request.path.startswith('/api/v1/public/hea'):
  response.headers['Access-Control-Allow-Origin']=origin
  response.headers['Vary']='Origin'
  response.headers['Access-Control-Allow-Methods']='GET, OPTIONS'
  response.headers['Access-Control-Allow-Headers']='Content-Type'
 return response

def require_api_key(fn):
 @wraps(fn)
 def wrapped(*a,**kw):
  if settings.api_key and request.headers.get('Authorization','').removeprefix('Bearer ').strip()!=settings.api_key:return jsonify({'error':'unauthorized'}),401
  return fn(*a,**kw)
 return wrapped
@app.get('/')
def dashboard():return render_template('dashboard.html',version=VERSION,ingress_path=_ingress_path(),display_timezone=settings.timezone,datetime_format=settings.datetime_format,summary=db.summary(),operational=db.operational_summary(),occurrences=db.list_occurrences(limit=50),captured_events=db.list_events(limit=100),people=db.people_inside(),sources=db.sources_state(),ha_status=ha.connection_status,hea=db.hea_summary(24,settings.human_experience_minimum_samples),hea_sources=db.hea_sources(24),hea_history=db.hea_history(24,limit=96),hea_config={'minimum_samples':settings.human_experience_minimum_samples,'window_minutes':settings.human_experience_aggregation_window_minutes,'minimum_confidence':settings.human_experience_minimum_confidence})

@app.get('/environment')
def environment_portal():
 return render_template('environment_portal.html',version=VERSION,ingress_path=_ingress_path(),display_timezone=settings.timezone,datetime_format=settings.datetime_format)

@app.get('/intelligence/environment')
def environment_intelligence_alias():
 return environment_portal()

@app.get('/tca')
def tca_portal():return render_template('tca_portal.html',version=VERSION,ingress_path=_ingress_path(),display_timezone=settings.timezone)

@app.get('/intelligence/tca')
def tca_intelligence_alias():return tca_portal()

@app.get('/hea')
def hea_portal():
 if not settings.hea_portal_enabled: abort(404)
 return render_template(
  'hea_portal.html',
  title=settings.hea_portal_title,
  subtitle=settings.hea_portal_subtitle,
  privacy_notice=settings.hea_portal_privacy_notice,
  default_hours=settings.hea_portal_default_hours,
  refresh_seconds=settings.hea_portal_refresh_seconds,
  show_sources=settings.hea_portal_show_sources,
  version=VERSION,
  ingress_path=_ingress_path(),
  display_timezone=settings.timezone,
  datetime_format=settings.datetime_format
 )

@app.route('/api/v1/public/hea/dashboard',methods=['GET','OPTIONS'])
def public_hea_dashboard():
 if not settings.hea_portal_enabled: abort(404)
 if request.method=='OPTIONS': return make_response('',204)
 return jsonify(_portal_payload())

@app.get('/health')
@app.get('/api/v1/health')
def health():return jsonify({'status':'ok','service':'seiden_flow','version':VERSION,'schema_version':SCHEMA_VERSION,'database_schema_version':DATABASE_SCHEMA_VERSION,'home_assistant_connection':ha.connection_status})
@app.post('/api/v1/events')
@app.post('/api/v1/ingest')
@require_api_key
def ingest():
 e,i=service.ingest(request.get_json(silent=False),transport='api');return jsonify({'accepted':i,'duplicate':not i,'event':e}),201 if i else 200

@app.get('/api/v1/occurrences')
def occurrences():return jsonify({'items':db.list_occurrences(limit=int(request.args.get('limit',100)))})

@app.get('/api/v1/occurrences/<occurrence_id>')
def occurrence_detail(occurrence_id):
 result=db.occurrence_detail(occurrence_id)
 if not result:abort(404)
 return jsonify(result)

@app.get('/intelligence/hea')
def hea_intelligence_alias():
 return hea_portal()

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
 return jsonify({'summary':db.summary(),'operational':db.operational_summary(),'occurrences':db.list_occurrences(limit=50),'captured_events':db.list_events(limit=100),'people':db.people_inside(),'sources':db.sources_state(),'home_assistant_connection':ha.connection_status,'version':VERSION,'human_experience':{'summary':db.hea_summary(24,settings.human_experience_minimum_samples),'sources':db.hea_sources(24),'history':db.hea_history(24,limit=96),'config':{'minimum_samples':settings.human_experience_minimum_samples,'window_minutes':settings.human_experience_aggregation_window_minutes,'minimum_confidence':settings.human_experience_minimum_confidence}},'environmental_experience':_environment_analytics_payload(include_timeline=False)})

@app.post('/api/v1/observations')
@require_api_key
def ingest_observation():
 try:
  result,inserted=service.ingest_observation(request.get_json(silent=False))
  return jsonify({'accepted':inserted,'result':result}),201 if inserted else 200
 except ValueError as exc:return jsonify({'error':'invalid_observation','message':str(exc)}),400


@app.get('/api/v2/experience')
def experience_v2():
 end=_parse_iso(request.args.get('end'),datetime.now(timezone.utc))
 start_value=request.args.get('start')
 if start_value:start=_parse_iso(start_value,end-timedelta(hours=settings.hea_portal_default_hours))
 else:
  hours=max(1,min(87600,int(request.args.get('hours',settings.hea_portal_default_hours))))
  start=end-timedelta(hours=hours)
 if start>=end:abort(400,description='O início deve ser anterior ao fim')
 result=db.hea_query(start.isoformat(),end.isoformat(),settings.human_experience_minimum_samples,service.weights,(request.args.get('source_id') or '').strip() or None,(request.args.get('location_id') or '').strip() or None,96)
 return jsonify({'experience_index':result['summary'],'history':result['history'],'version':VERSION})

@app.get('/api/v1/environment/measurements')
def environment_measurements():
 return jsonify({'items':db.environmental_measurements(limit=int(request.args.get('limit',500)),source_id=(request.args.get('source_id') or '').strip() or None,location_id=(request.args.get('location_id') or '').strip() or None,start_at=(request.args.get('start') or '').strip() or None,end_at=(request.args.get('end') or '').strip() or None)})

@app.get('/api/v1/environment/latest')
def environment_latest():
 return jsonify({'item':db.environmental_latest((request.args.get('source_id') or '').strip() or None)})

@app.get('/api/v1/environment/summary')
def environment_summary():
 return jsonify({'measurement_count':db.environmental_count(),'latest':db.environmental_latest(),'storage_enabled':settings.environmental_storage_enabled})

def _environment_sources_payload():
 key=('sources',)
 payload=_env_cache_get(key)
 if payload is None:
  payload=_timed_environment_call('environment.sources',db.environmental_sources_catalog)
  _env_cache_put(key,payload)
 return payload

def _environment_alias_scope(source_id=None,location_id=None):
 catalog=_environment_sources_payload()
 source_ids=[];location_ids=[]
 if source_id:
  for item in catalog.get('items',[]):
   if source_id==item.get('source_id') or source_id in (item.get('source_aliases') or []):
    source_ids=item.get('source_aliases') or [item.get('source_id')]
    if not location_id:location_ids=item.get('location_aliases') or []
    break
  if not source_ids:source_ids=[source_id]
 if location_id:
  for item in catalog.get('locations',[]):
   if location_id==item.get('location_id') or location_id in (item.get('location_aliases') or []):
    location_ids=item.get('location_aliases') or [item.get('location_id')]
    break
  if not location_ids:location_ids=[location_id]
 return source_ids,location_ids

@app.get('/api/v1/environment/sources')
def environment_sources():
 return jsonify(_environment_sources_payload())


def _environment_request_key():
 return ('analytics_full',tuple(sorted((k,v) for k,v in request.args.items())))

def _environment_analytics_payload(include_timeline=True):
 cache_key=_environment_request_key()
 cached=_env_cache_get(cache_key)
 if cached is not None:
  result=dict(cached)
  if not include_timeline:result.pop('timeline',None)
  return result
 try:
  start,end,period=period_bounds(period=(request.args.get('period') or '24h').strip(),start=(request.args.get('start') or '').strip() or None,end=(request.args.get('end') or '').strip() or None)
  sampling_minutes=max(1,min(60,int(request.args.get('sampling_minutes',1))))
  bucket_minutes=max(sampling_minutes,min(1440,int(request.args.get('bucket_minutes',60))))
 except (ValueError,TypeError) as exc:
  abort(400,description=str(exc))
 source_id=(request.args.get('source_id') or '').strip() or None
 location_id=(request.args.get('location_id') or '').strip() or None
 previous_start=start-(end-start)
 source_ids,location_ids=_environment_alias_scope(source_id,location_id)
 rows=db.environmental_range(utc_iso(start),utc_iso(end),source_id,location_id,source_ids=source_ids,location_ids=location_ids)
 previous=db.environmental_range(utc_iso(previous_start),utc_iso(start),source_id,location_id,source_ids=source_ids,location_ids=location_ids)
 result=calculate_environmental_analytics(rows,start,end,previous,sampling_minutes,bucket_minutes,minimum_samples=10)
 result['period']['preset']=period
 result['scope']['source_id']=source_id
 result['scope']['location_id']=location_id
 _env_cache_put(cache_key,result)
 response=dict(result)
 if not include_timeline:response.pop('timeline',None)
 return response


@app.get('/api/v1/environment/portfolio')
def environment_portfolio():
 try:
  start,end,period=period_bounds(period=(request.args.get('period') or '24h').strip(),start=(request.args.get('start') or '').strip() or None,end=(request.args.get('end') or '').strip() or None)
  sampling_minutes=max(1,min(60,int(request.args.get('sampling_minutes',1))))
  bucket_minutes=max(sampling_minutes,min(1440,int(request.args.get('bucket_minutes',60))))
 except (ValueError,TypeError) as exc:abort(400,description=str(exc))
 location_id=(request.args.get('location_id') or '').strip() or None
 catalog=_environment_sources_payload();items=[]
 for source in catalog.get('items',[]):
  if location_id and location_id!=source.get('location_id') and location_id not in (source.get('location_aliases') or []):continue
  aliases=source.get('source_aliases') or [source.get('source_id')]
  rows=db.environmental_range(utc_iso(start),utc_iso(end),source_ids=aliases)
  if not rows:continue
  result=calculate_environmental_analytics(rows,start,end,[],sampling_minutes,bucket_minutes,minimum_samples=10)
  current=result.get('current') or {}
  items.append({
   'source_id':source.get('source_id'),'source_name':source.get('source_name'),
   'location_id':source.get('location_id'),'location_name':source.get('location_name'),
   'source_aliases':aliases,'eea_index':result.get('eea_index'),
   'condition':current.get('condition') or ('comfortable' if (result.get('eea_index') or 0)>=85 else 'attention' if (result.get('eea_index') or 0)>=70 else 'uncomfortable' if (result.get('eea_index') or 0)>=50 else 'critical'),
   'temperature_c':current.get('temperature_c'),'humidity_pct':current.get('humidity_pct'),
   'occurred_at':current.get('occurred_at'),'coverage_pct':result.get('data_quality',{}).get('coverage_pct'),
   'quality_status':result.get('data_quality',{}).get('status'),'observed_minutes':result.get('data_quality',{}).get('sample_count_normalized'),
   'analysis_type':current.get('analysis_type'),'profile_id':current.get('resolved_profile_id') or current.get('profile_id'),
   'profile_label':current.get('profile_label'),'environmental_score':current.get('environmental_score'),
   'operational_state':current.get('operational_state'),'metric_scores':current.get('metric_scores') or {},
   'applied_ranges':current.get('applied_ranges') or {},'reason_codes':current.get('reason_codes') or [],
  })
 counts={k:sum(1 for x in items if x.get('condition')==k) for k in ('comfortable','attention','uncomfortable','critical')}
 return jsonify({'period':{'start':utc_iso(start),'end':utc_iso(end),'preset':period},'items':items,'counts':counts,'source_count':len(items),'version':VERSION})

@app.get('/api/v1/environment/dashboard')
def environment_dashboard():
 # Endpoint agregado mantido para compatibilidade, mas construído de forma defensiva.
 # O portal usa endpoints sequenciais comprovados para que uma falha no catálogo não
 # indisponibilize os indicadores ambientais.
 try:
  analytics=_timed_environment_call('environment.dashboard.analytics',lambda:_environment_analytics_payload(include_timeline=True))
  try:
   catalog=_timed_environment_call('environment.dashboard.sources',_environment_sources_payload)
  except Exception:
   LOGGER.exception('Falha ao montar catálogo ambiental; seguindo com catálogo vazio')
   catalog={'items':[],'locations':[]}
  return jsonify({
   'analytics':analytics,
   'timeline':{'period':analytics['period'],'scope':analytics['scope'],'data_quality':analytics['data_quality'],'items':analytics.get('timeline',[])},
   'catalog':catalog,
   'generated_at':datetime.now(timezone.utc).isoformat(),
   'cache_ttl_seconds':_ENV_CACHE_TTL_SECONDS,
   'version':VERSION,
  })
 except Exception:
  LOGGER.exception('Falha no endpoint agregado do dashboard ambiental')
  return jsonify({'error':'environment_dashboard_failed','message':'Falha ao montar dashboard ambiental'}),500

@app.get('/api/v1/environment/analytics')
def environment_analytics():
 # 0.10.0: analytics passa a entregar também a série temporal utilizada pelo portal.
 # Campo aditivo, mantendo compatibilidade com consumidores das versões anteriores.
 return jsonify(_environment_analytics_payload(include_timeline=True))

@app.get('/api/v1/environment/timeline')
def environment_timeline():
 payload=_environment_analytics_payload(include_timeline=True)
 return jsonify({'period':payload['period'],'scope':payload['scope'],'data_quality':payload['data_quality'],'items':payload['timeline']})

@app.get('/api/v1/tca/assets')
def tca_assets():return jsonify({'items':db.tca_assets()})
@app.post('/api/v1/tca/assets')
def tca_create_asset():
 try:return jsonify(db.tca_upsert_asset(request.get_json(force=True))),201
 except ValueError as exc:abort(400,description=str(exc))
@app.get('/api/v1/tca/assets/<asset_id>')
def tca_asset(asset_id):
 item=db.tca_asset(asset_id)
 if not item:abort(404)
 return jsonify(item)
@app.put('/api/v1/tca/assets/<asset_id>')
def tca_update_asset(asset_id):
 data=request.get_json(force=True);data['asset_id']=asset_id
 try:return jsonify(db.tca_upsert_asset(data))
 except ValueError as exc:abort(400,description=str(exc))
@app.delete('/api/v1/tca/assets/<asset_id>')
def tca_remove_asset(asset_id):return ('',204) if db.tca_delete_asset(asset_id) else abort(404)
@app.post('/api/v1/tca/assets/<asset_id>/bindings')
def tca_add_binding(asset_id):
 try:return jsonify({'items':db.tca_upsert_binding(asset_id,request.get_json(force=True))}),201
 except ValueError as exc:abort(400,description=str(exc))
@app.delete('/api/v1/tca/bindings/<binding_id>')
def tca_remove_binding(binding_id):return ('',204) if db.tca_delete_binding(binding_id) else abort(404)
@app.get('/api/v1/tca/sources')
def tca_sources():return jsonify({'items':db.tca_source_catalog()})
@app.post('/api/v1/tca/measurements')
def tca_measurement_ingest():
 payload=request.get_json(force=True);items=extract_tca_measurements(payload)
 if not items:abort(400,description='Nenhuma medição TCA reconhecida')
 return jsonify({'accepted':db.insert_tca_measurements(items),'recognized':len(items)}),201
@app.get('/api/v1/tca/assets/<asset_id>/analytics')
def tca_asset_analytics(asset_id):
 asset=db.tca_asset(asset_id)
 if not asset:abort(404)
 try:start,end,period=period_bounds(period=(request.args.get('period') or '24h'),start=request.args.get('start'),end=request.args.get('end'))
 except ValueError as exc:abort(400,description=str(exc))
 rows=db.tca_measurements(asset_id,utc_iso(start),utc_iso(end));result=calculate_tca(rows,asset,asset.get('bindings') or [],start,end);result['period']['preset']=period
 return jsonify(result)
@app.get('/api/v1/tca/dashboard')
def tca_dashboard():
 assets=db.tca_assets();items=[]
 for asset in assets:
  end=datetime.now(timezone.utc);start=end-timedelta(hours=24);rows=db.tca_measurements(asset['asset_id'],utc_iso(start),utc_iso(end));result=calculate_tca(rows,asset,asset.get('bindings') or [],start,end);items.append({'asset':asset,'current':result['current'],'summary':result['summary']})
 return jsonify({'items':items,'version':VERSION})

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
