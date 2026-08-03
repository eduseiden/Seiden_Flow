from __future__ import annotations
import json
from pathlib import Path
from typing import Any

_FALLBACK = {
 "schema_version":"1.0","configuration_mode":"fallback","managed_by":"seiden_flow",
 "profiles":{
  "refrigerator":{"label":"Geladeira","analysis_type":"environmental_compliance","ruleset":"seiden_environmental_profile_refrigerator_v1","temperature":{"optimal":{"min":2.0,"max":5.0},"attention":{"min":0.0,"max":8.0},"critical":{"min":-2.0,"max":10.0},"weight":1.0},"humidity":None},
  "freezer":{"label":"Freezer","analysis_type":"environmental_compliance","ruleset":"seiden_environmental_profile_freezer_v1","temperature":{"optimal":{"min":-22.0,"max":-18.0},"attention":{"min":-25.0,"max":-15.0},"critical":{"min":-30.0,"max":-10.0},"weight":1.0},"humidity":None},
  "wine_cellar":{"label":"Adega de vinhos","analysis_type":"environmental_compliance","ruleset":"seiden_environmental_profile_wine_cellar_v1","temperature":{"optimal":{"min":12.0,"max":16.0},"attention":{"min":10.0,"max":18.0},"critical":{"min":7.0,"max":22.0},"weight":0.6},"humidity":{"optimal":{"min":55.0,"max":75.0},"attention":{"min":45.0,"max":80.0},"critical":{"min":35.0,"max":90.0},"weight":0.4}},
  "beer_cooler":{"label":"Cervejeira","analysis_type":"environmental_compliance","ruleset":"seiden_environmental_profile_beer_cooler_v1","temperature":{"optimal":{"min":2.0,"max":6.0},"attention":{"min":0.0,"max":8.0},"critical":{"min":-2.0,"max":10.0},"weight":1.0},"humidity":None}
 }}

def _candidates(config_dir:str):
 base=Path(config_dir)
 return [base/'seiden_vision'/'environmental_profiles.json',Path('/homeassistant/seiden_vision/environmental_profiles.json')]

def load_tca_profiles(config_dir:str)->dict[str,Any]:
 data=None;source=None;error=None
 for path in _candidates(config_dir):
  try:
   if path.exists():
    candidate=json.loads(path.read_text(encoding='utf-8'))
    if isinstance(candidate.get('profiles'),dict):data=candidate;source=str(path);break
  except Exception as exc:error=str(exc)
 if data is None:data=_FALLBACK;source='embedded_fallback'
 items=[]
 for profile_id,p in data.get('profiles',{}).items():
  if not isinstance(p,dict) or p.get('analysis_type')!='environmental_compliance':continue
  temp=p.get('temperature') or {};humidity=p.get('humidity')
  items.append({'profile_id':profile_id,'label':p.get('label') or profile_id,'analysis_type':p.get('analysis_type'),'ruleset':p.get('ruleset'),'temperature':temp,'humidity':humidity,'humidity_enabled':bool(humidity)})
 items.sort(key=lambda x:x['label'])
 return {'schema_version':data.get('schema_version'),'configuration_mode':data.get('configuration_mode'),'managed_by':data.get('managed_by'),'source':source,'error':error,'items':items}

def resolve_tca_asset(data:dict[str,Any],config_dir:str)->dict[str,Any]:
 out=dict(data or {});catalog=load_tca_profiles(config_dir);profiles={p['profile_id']:p for p in catalog['items']}
 profile_id=str(out.get('profile_id') or out.get('asset_type') or '').strip()
 profile=profiles.get(profile_id)
 if not profile:raise ValueError('perfil TCA inválido ou indisponível')
 optimal=(profile.get('temperature') or {}).get('optimal') or {}
 out['profile_id']=profile_id
 out['asset_type']=str(out.get('asset_type') or profile_id)
 out['min_temperature_c']=optimal.get('min')
 out['max_temperature_c']=optimal.get('max')
 out['humidity_enabled']=bool(profile.get('humidity'))
 metadata=dict(out.get('metadata') or {})
 metadata['profile_snapshot']={'label':profile.get('label'),'ruleset':profile.get('ruleset'),'temperature':profile.get('temperature'),'humidity':profile.get('humidity'),'source':catalog.get('source'),'schema_version':catalog.get('schema_version')}
 out['metadata']=metadata
 return out
