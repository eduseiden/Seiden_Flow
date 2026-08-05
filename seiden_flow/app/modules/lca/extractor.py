from __future__ import annotations
import hashlib, json, re, unicodedata
from datetime import datetime, timezone
from typing import Any


def _slug(value: Any) -> str:
    text=unicodedata.normalize("NFKD",str(value or "")).encode("ascii","ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+","_",text).strip("_") or "unknown"

def _utc(value: Any) -> str:
    text=str(value or "").strip()
    if not text:return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    try:
        dt=datetime.fromisoformat(text.replace("Z","+00:00"))
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00","Z")
    except ValueError:return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def _state(value: Any) -> str|None:
    if isinstance(value,bool):return "on" if value else "off"
    text=str(value or "").strip().lower()
    if text in {"on","1","true","ligado","open"}:return "on"
    if text in {"off","0","false","desligado","closed"}:return "off"
    return None

def _topic(payload: dict) -> str:
    raw=payload.get("raw") if isinstance(payload.get("raw"),dict) else {}
    origin=payload.get("origin") if isinstance(payload.get("origin"),dict) else {}
    return str(payload.get("topic") or origin.get("topic") or raw.get("topic") or "").strip()

def _allowed(topic: str, prefixes: tuple[str,...]) -> bool:
    if not prefixes:return True
    low=topic.lower()
    return any(low.startswith(p.lower().rstrip("+/#")) for p in prefixes if p)

def extract_lca_events(payload: dict[str,Any], ha_event_type: str|None=None, topic_prefixes: tuple[str,...]=()) -> list[dict]:
    if not isinstance(payload,dict):return []
    event_type=str(payload.get("event_type") or ha_event_type or "").lower()
    topic=_topic(payload)
    canonical=event_type.startswith("lighting.")
    mqtt=("mqtt" in event_type or bool(topic) or str(payload.get("connector") or "").lower()=="mqtt")
    if not canonical and (not mqtt or not _allowed(topic,topic_prefixes)):return []
    data=payload.get("data") if isinstance(payload.get("data"),dict) else {}
    raw_payload=payload.get("payload") if isinstance(payload.get("payload"),dict) else {}
    merged={**raw_payload,**data,**payload}
    leaf=topic.rstrip("/").split("/")[-1] if topic else str(payload.get("device_id") or payload.get("source_id") or "lighting_source")
    origin=payload.get("origin") if isinstance(payload.get("origin"),dict) else {}
    device_id=str(origin.get("source_id") or origin.get("id") or payload.get("device_id") or payload.get("source_id") or f"mqtt_{_slug(topic)}").strip()
    device_name=str(origin.get("source_name") or origin.get("name") or payload.get("source_name") or leaf or device_id).strip()
    occurred=_utc(payload.get("timestamp") or payload.get("occurred_at"))
    base_id=str(payload.get("event_id") or "") or "lca-"+hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()[:28]
    availability=str(merged.get("availability") or "").lower()
    model=str(merged.get("model") or origin.get("model") or "").strip() or None
    manufacturer=str(merged.get("manufacturer") or origin.get("manufacturer") or "").strip() or None
    result=[]
    common={"message_id":base_id,"device_id":device_id,"device_name":device_name,"topic":topic or None,"occurred_at":occurred,"model":model,"manufacturer":manufacturer,"payload":payload}
    if availability in {"online","offline"}:
        result.append({**common,"lca_event_id":base_id+":availability","kind":"availability","state":availability,"channel":None,"action":None,"brightness":None})
    action=merged.get("action") or merged.get("button_action") or merged.get("click")
    channel=merged.get("channel") or merged.get("endpoint") or merged.get("button") or merged.get("input")
    if action is not None or event_type=="lighting.interaction":
        result.append({**common,"lca_event_id":base_id+":interaction","kind":"interaction","state":None,"channel":str(channel or "default"),"action":str(action or merged.get("type") or "interaction"),"brightness":None})
    state_fields=[]
    if canonical and merged.get("state") is not None:state_fields.append((str(channel or "main"),merged.get("state")))
    for key,value in merged.items():
        kl=str(key).lower()
        if kl=="state" or kl.startswith("state_") or kl.startswith("state_l"):
            state_fields.append((str(key)[6:] if kl.startswith("state_") else (str(key)[5:] if kl.startswith("state_l") else "main"),value))
    seen=set()
    for ch,value in state_fields:
        st=_state(value)
        if not st or (ch,st) in seen:continue
        seen.add((ch,st))
        bright=merged.get("brightness")
        try:bright=float(bright) if bright is not None else None
        except (TypeError,ValueError):bright=None
        result.append({**common,"lca_event_id":f"{base_id}:state:{_slug(ch)}","kind":"state","state":st,"channel":str(ch or "main"),"action":None,"brightness":bright})
    return result
