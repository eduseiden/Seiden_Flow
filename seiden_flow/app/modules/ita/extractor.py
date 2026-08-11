from __future__ import annotations
from typing import Any

TEMP_UNITS={"cel","c","celsius","degc","°c"}
POWER_UNITS={"w","watt","watts"}
PERCENT_UNITS={"%","percent","pct"}


def _norm_unit(v:Any)->str:
    return str(v or '').strip().lower()


def _metric_kind(item:dict)->str:
    unit=_norm_unit(item.get('units'))
    ctx=str(item.get('physical_context') or '').strip().lower()
    name=str(item.get('name') or '').lower()
    sid=str(item.get('id') or '').lower()
    if unit in TEMP_UNITS:return 'temperature'
    if unit in POWER_UNITS:return 'power'
    if unit in PERCENT_UNITS and ('fan' in name or 'fan' in sid or ctx=='fan'):return 'fan_speed'
    return 'other'


def extract_ita_snapshot(payload:dict[str,Any],ha_event_type:str|None=None)->dict|None:
    if not isinstance(payload,dict):return None
    internal_type=str(payload.get('event_type') or '')
    if internal_type!='infrastructure.telemetry_snapshot':return None
    connection=payload.get('connection') if isinstance(payload.get('connection'),dict) else {}
    asset=payload.get('asset') if isinstance(payload.get('asset'),dict) else {}
    raw=payload.get('measurements')
    if not isinstance(raw,list):raw=payload.get('sensors')
    if not isinstance(raw,list):return None
    measurements=[]
    for item in raw:
        if not isinstance(item,dict) or item.get('reading') is None:continue
        try:reading=float(item.get('reading'))
        except (TypeError,ValueError):continue
        thresholds=item.get('thresholds') if isinstance(item.get('thresholds'),dict) else {}
        measurements.append({
            'sensor_id':str(item.get('id') or item.get('odata_id') or 'unknown'),
            'sensor_name':str(item.get('name') or item.get('id') or 'Sensor'),
            'physical_context':str(item.get('physical_context') or 'Unknown'),
            'metric_kind':_metric_kind(item),
            'reading':reading,
            'units':str(item.get('units') or ''),
            'health':str(item.get('health') or 'Unknown'),
            'state':str(item.get('state') or 'Unknown'),
            'range_min':item.get('range_min'),'range_max':item.get('range_max'),
            'thresholds':thresholds,
            'related_items':item.get('related_items') if isinstance(item.get('related_items'),list) else [],
            'odata_id':item.get('odata_id'),
        })
    if not measurements:return None
    system_id=str(asset.get('system_id') or payload.get('system_id') or connection.get('id') or 'unknown_system')
    return {
        'event_id':str(payload.get('event_id') or ''),
        'occurred_at':str(payload.get('timestamp') or ''),
        'connection_id':str(connection.get('id') or payload.get('connection_id') or 'unknown_connection'),
        'connection_name':str(connection.get('name') or payload.get('connection_name') or connection.get('id') or 'Infrastructure source'),
        'connector':str(connection.get('connector') or payload.get('connector') or 'unknown'),
        'system_id':system_id,
        'system_name':str(asset.get('system_name') or payload.get('system_name') or system_id),
        'chassis_ids':asset.get('chassis_ids') if isinstance(asset.get('chassis_ids'),list) else [],
        'measurements':measurements,
    }
