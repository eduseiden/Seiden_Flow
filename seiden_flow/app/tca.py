from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import hashlib, json

KINDS={"temperature","humidity","door","power","voltage","current","energy"}

def utc_iso(value:Any)->str:
 text=str(value or '').strip()
 if not text:return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
 dt=datetime.fromisoformat(text.replace('Z','+00:00'))
 if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
 return dt.astimezone(timezone.utc).isoformat().replace('+00:00','Z')

def _number(value):
 try:return float(value)
 except (TypeError,ValueError):return None

def extract_tca_measurements(payload:dict[str,Any], ha_event_type:str|None=None)->list[dict[str,Any]]:
 """Extract canonical thermal-control signals without coupling to a device/protocol.

 Accepted shapes include canonical metrics dictionaries, one metric/value pair, and
 access state events. Asset association may be supplied by the event itself or later
 resolved in Flow through source bindings.
 """
 if not isinstance(payload,dict):return []
 event_type=str(payload.get('event_type') or ha_event_type or '').strip().lower()
 origin=payload.get('origin') or payload.get('reader') or {}
 source_id=str(origin.get('source_id') or origin.get('id') or payload.get('source_id') or payload.get('device_id') or '').strip()
 if not source_id:return []
 source_name=str(origin.get('source_name') or origin.get('name') or payload.get('source_name') or source_id)
 asset_id=str(payload.get('asset_id') or (payload.get('context') or {}).get('asset_id') or '').strip() or None
 role=str(payload.get('role') or origin.get('role') or 'main').strip() or 'main'
 occurred_at=utc_iso(payload.get('timestamp') or payload.get('occurred_at'))
 event_id=str(payload.get('event_id') or '').strip()
 if not event_id:
  event_id='tca-'+hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()[:32]
 metrics={}
 for candidate in (payload.get('metrics'),payload.get('measurements'),payload.get('data')):
  if isinstance(candidate,dict):metrics.update(candidate)
 # Canonical nested environmental measurements.
 for key,kind in (("temperature","temperature"),("humidity","humidity")):
  item=metrics.get(key)
  if isinstance(item,dict):metrics[kind]=item.get('value')
 # Direct fields and common aliases.
 aliases={
  'temperature':['temperature_c','temperature'], 'humidity':['humidity_pct','humidity'],
  'power':['power_w','power'], 'voltage':['voltage_v','voltage'], 'current':['current_a','current'],
  'energy':['energy_kwh','energy_total_kwh','energy'], 'door':['door','contact','state']}
 for kind,names in aliases.items():
  if kind in metrics and not isinstance(metrics[kind],dict):continue
  for name in names:
   if payload.get(name) is not None:metrics[kind]=payload.get(name);break
 # Metric/value canonical event.
 metric=str(payload.get('metric') or payload.get('metric_type') or '').strip().lower()
 if metric in KINDS and payload.get('value') is not None:metrics[metric]=payload.get('value')
 if event_type in {'access.state','access_state','door.state','door_state'} or 'door' in event_type:
  metrics['door']=payload.get('state') or payload.get('value') or (payload.get('operation') or {}).get('action')
 result=[]
 units={'temperature':'celsius','humidity':'percent','power':'W','voltage':'V','current':'A','energy':'kWh','door':'state'}
 for kind,value in metrics.items():
  canonical={'temperature_c':'temperature','humidity_pct':'humidity','power_w':'power','voltage_v':'voltage','current_a':'current','energy_kwh':'energy'}.get(kind,kind)
  if canonical not in KINDS:continue
  if canonical=='door':
   text=str(value).strip().lower()
   if text in {'on','1','true','open','opened'}:normalized='open'
   elif text in {'off','0','false','closed','close'}:normalized='closed'
   else:continue
   numeric=None;text_value=normalized
  else:
   numeric=_number(value)
   if numeric is None:continue
   text_value=None
  result.append({'measurement_id':f'{event_id}:{source_id}:{canonical}','event_id':event_id,'asset_id':asset_id,'source_id':source_id,'source_name':source_name,'kind':canonical,'role':role,'occurred_at':occurred_at,'numeric_value':numeric,'text_value':text_value,'unit':units[canonical],'payload':payload})
 return result
