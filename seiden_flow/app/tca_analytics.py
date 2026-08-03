from __future__ import annotations
from datetime import datetime,timezone,timedelta
from statistics import fmean

def parse(v):
 d=datetime.fromisoformat(str(v).replace('Z','+00:00'));return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
def rnd(v,d=2):return round(float(v),d) if v is not None else None

def calculate_tca(rows, asset, bindings, start, end):
 by={k:[] for k in ('temperature','humidity','door','power','voltage','current','energy')}
 for r in rows:
  if r['kind'] in by:by[r['kind']].append(r)
 for values in by.values():values.sort(key=lambda r:r['occurred_at'])
 latest={k:(v[-1] if v else None) for k,v in by.items()}
 temps=[float(r['numeric_value']) for r in by['temperature'] if r.get('numeric_value') is not None]
 powers=[float(r['numeric_value']) for r in by['power'] if r.get('numeric_value') is not None]
 # Door episodes and thermal recovery. An episode closes at closed event and recovers
 # when the primary/first temperature next re-enters configured range.
 min_t=asset.get('min_temperature_c');max_t=asset.get('max_temperature_c')
 primary_ids=[b['source_id'] for b in bindings if b['kind']=='temperature' and b.get('is_primary')]
 temp_rows=[r for r in by['temperature'] if not primary_ids or r['source_id'] in primary_ids]
 episodes=[];opened=None
 for d in by['door']:
  if d.get('text_value')=='open' and opened is None:opened=d
  elif d.get('text_value')=='closed' and opened is not None:
   opened_at=parse(opened['occurred_at']);closed_at=parse(d['occurred_at'])
   before=[t for t in temp_rows if parse(t['occurred_at'])<=opened_at]
   after=[t for t in temp_rows if parse(t['occurred_at'])>=closed_at]
   baseline=float(before[-1]['numeric_value']) if before else None
   recovered=None
   for t in after:
    val=float(t['numeric_value'])
    in_range=(min_t is None or val>=float(min_t)) and (max_t is None or val<=float(max_t))
    if in_range:recovered=t;break
   during=[t for t in temp_rows if opened_at<=parse(t['occurred_at'])<=(parse(recovered['occurred_at']) if recovered else end)]
   vals=[float(t['numeric_value']) for t in during]
   peak=max(vals) if vals else None;low=min(vals) if vals else None
   impact=None
   if baseline is not None and vals:impact=max(abs(v-baseline) for v in vals)
   recovery_min=(parse(recovered['occurred_at'])-closed_at).total_seconds()/60 if recovered else None
   energy_rows=[x for x in by['power'] if closed_at<=parse(x['occurred_at'])<=(parse(recovered['occurred_at']) if recovered else end)]
   energy_wh=0.0
   for a,b in zip(energy_rows,energy_rows[1:]):energy_wh+=float(a['numeric_value'])*(parse(b['occurred_at'])-parse(a['occurred_at'])).total_seconds()/3600
   episodes.append({'opened_at':opened['occurred_at'],'closed_at':d['occurred_at'],'open_seconds':round((closed_at-opened_at).total_seconds()),'baseline_temperature_c':rnd(baseline),'maximum_temperature_c':rnd(peak),'minimum_temperature_c':rnd(low),'thermal_impact_c':rnd(impact),'recovered_at':recovered['occurred_at'] if recovered else None,'recovery_minutes':rnd(recovery_min),'recovery_energy_wh':rnd(energy_wh),'status':'recovered' if recovered else 'incomplete'})
   opened=None
 if opened:
  episodes.append({'opened_at':opened['occurred_at'],'closed_at':None,'open_seconds':round((end-parse(opened['occurred_at'])).total_seconds()),'status':'open'})
 recoveries=[e['recovery_minutes'] for e in episodes if e.get('recovery_minutes') is not None]
 current_door=latest['door']['text_value'] if latest['door'] else 'unknown'
 current_temp=latest['temperature']['numeric_value'] if latest['temperature'] else None
 in_range=current_temp is not None and (min_t is None or current_temp>=min_t) and (max_t is None or current_temp<=max_t)
 state='door_open' if current_door=='open' else ('stable' if in_range else 'out_of_range' if current_temp is not None else 'no_data')
 timeline=[]
 for r in rows:
  timeline.append({'occurred_at':r['occurred_at'],'source_id':r['source_id'],'source_name':r.get('source_name'),'kind':r['kind'],'role':r.get('role'),'value':r.get('text_value') if r['kind']=='door' else r.get('numeric_value'),'unit':r.get('unit')})
 return {'asset':asset,'period':{'start':start.isoformat().replace('+00:00','Z'),'end':end.isoformat().replace('+00:00','Z')},'current':{'state':state,'temperature_c':rnd(current_temp),'humidity_pct':rnd(latest['humidity']['numeric_value']) if latest['humidity'] else None,'door':current_door,'power_w':rnd(latest['power']['numeric_value']) if latest['power'] else None,'voltage_v':rnd(latest['voltage']['numeric_value']) if latest['voltage'] else None,'current_a':rnd(latest['current']['numeric_value']) if latest['current'] else None,'in_range':in_range,'last_update':max((r['occurred_at'] for r in rows),default=None)},'summary':{'sample_count':len(rows),'temperature_average_c':rnd(fmean(temps)) if temps else None,'temperature_minimum_c':rnd(min(temps)) if temps else None,'temperature_maximum_c':rnd(max(temps)) if temps else None,'power_average_w':rnd(fmean(powers)) if powers else None,'door_openings':len([e for e in episodes if e.get('closed_at')]),'door_open_seconds':sum(e.get('open_seconds',0) for e in episodes),'average_recovery_minutes':rnd(fmean(recoveries)) if recoveries else None,'recovered_episodes':len(recoveries),'incomplete_episodes':len([e for e in episodes if e.get('status')=='incomplete'])},'episodes':episodes,'bindings':bindings,'timeline':timeline}
