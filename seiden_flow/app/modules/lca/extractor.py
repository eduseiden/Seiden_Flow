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
    data=payload.get("data") if isinstance(payload.get("data"),dict) else {}
    raw_payload=payload.get("payload") if isinstance(payload.get("payload"),dict) else {}
    merged={**raw_payload,**data,**payload}
    event_type=str(merged.get("event_type") or ha_event_type or "").lower()
    topic=_topic(payload)

    # Interaction-origin events are an explicit Seiden contract and must be
    # accepted even when normal LCA MQTT prefixes only include Zigbee2MQTT.
    explicit_interaction=(
        event_type in {"lighting_interaction","lighting.interaction"}
        or topic.rstrip("/").lower()=="seiden/lca/interactions"
    )

    # Bridge State Drivers emit compact transition events instead of raw
    # technology-specific payloads. LCA consumes one canonical transition
    # contract for MQTT and Home Assistant sources.
    explicit_state_transition = event_type in {"state_transition", "lighting.state_transition"}
    if explicit_state_transition:
        connection = payload.get("connection") if isinstance(payload.get("connection"), dict) else {}
        connector = str(payload.get("connector") or connection.get("connector") or "").strip().lower()
        operation = payload.get("operation") if isinstance(payload.get("operation"), dict) else {}
        current_state = _state(
            merged.get("current_state")
            if merged.get("current_state") is not None
            else operation.get("current_state")
        )
        previous_state = _state(
            merged.get("previous_state")
            if merged.get("previous_state") is not None
            else operation.get("previous_state")
        )
        if current_state is None:
            return []

        occurred = _utc(merged.get("timestamp") or merged.get("occurred_at"))
        base_id = str(payload.get("event_id") or "") or "lca-" + hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()
        ).hexdigest()[:28]

        if connector == "home_assistant":
            device = payload.get("device") if isinstance(payload.get("device"), dict) else {}
            entity_id = str(
                merged.get("entity_id")
                or device.get("entity_id")
                or device.get("id")
                or ""
            ).strip()
            if not entity_id:
                return []

            # One HA entity is one direct state source. The LCA channel is
            # deliberately technology-neutral and stable.
            channel = "main"
            device_id = f"ha_{_slug(entity_id)}"
            device_name = str(
                payload.get("device_name")
                or device.get("name")
                or entity_id
            ).strip()
            common = {
                "message_id": base_id,
                "device_id": device_id,
                "device_name": device_name,
                "topic": None,
                "occurred_at": occurred,
                "model": None,
                "manufacturer": None,
                "payload": payload,
            }
            return [{
                **common,
                "lca_event_id": f"{base_id}:state:main",
                "kind": "state",
                "state": current_state,
                "previous_state": previous_state,
                "channel": channel,
                "action": None,
                "brightness": None,
                "source_entity": entity_id,
                "explicit_transition": True,
                "transition_source": "bridge_ha_state_driver",
            }]

        if connector in {"", "mqtt"}:
            if not topic or not _allowed(topic, topic_prefixes):
                return []

            channel = str(
                merged.get("channel") or operation.get("channel") or "main"
            ).strip().lower() or "main"
            leaf = topic.rstrip("/").split("/")[-1]
            device_id = f"mqtt_{_slug(topic)}"
            device_name = str(
                payload.get("device_name")
                or (payload.get("device") or {}).get("name")
                or leaf
                or device_id
            ).strip()
            common = {
                "message_id": base_id,
                "device_id": device_id,
                "device_name": device_name,
                "topic": topic,
                "occurred_at": occurred,
                "model": None,
                "manufacturer": None,
                "payload": payload,
            }
            return [{
                **common,
                "lca_event_id": f"{base_id}:state:{_slug(channel)}",
                "kind": "state",
                "state": current_state,
                "previous_state": previous_state,
                "channel": channel,
                "action": None,
                "brightness": None,
                "explicit_transition": True,
                "transition_source": "bridge_mqtt_state_driver",
            }]

        # Future connectors require an explicit identity mapping before LCA
        # interprets them as lighting points.
        return []
    canonical=event_type.startswith("lighting.") or explicit_interaction
    mqtt=("mqtt" in event_type or bool(topic) or str(payload.get("connector") or "").lower()=="mqtt")
    if not canonical and (not mqtt or not _allowed(topic,topic_prefixes)):return []

    leaf=topic.rstrip("/").split("/")[-1] if topic else str(payload.get("device_id") or payload.get("source_id") or "lighting_source")
    origin=payload.get("origin") if isinstance(payload.get("origin"),dict) else {}
    source_device=str(merged.get("source_device") or "").strip() or None
    source_entity=str(merged.get("source_entity") or "").strip() or None
    source_channel=str(merged.get("source_channel") or "").strip() or None
    device_id=str(origin.get("source_id") or origin.get("id") or payload.get("device_id") or payload.get("source_id") or source_device or f"mqtt_{_slug(topic)}").strip()
    device_name=str(origin.get("source_name") or origin.get("name") or payload.get("source_name") or source_device or leaf or device_id).strip()
    occurred=_utc(merged.get("timestamp") or merged.get("occurred_at"))
    base_id=str(payload.get("event_id") or merged.get("interaction_id") or "") or "lca-"+hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()[:28]
    availability=str(merged.get("availability") or "").lower()
    model=str(merged.get("model") or origin.get("model") or "").strip() or None
    manufacturer=str(merged.get("manufacturer") or origin.get("manufacturer") or "").strip() or None
    result=[]
    common={"message_id":base_id,"device_id":device_id,"device_name":device_name,"topic":topic or None,"occurred_at":occurred,"model":model,"manufacturer":manufacturer,"payload":payload}

    if explicit_interaction:
        requested=_state(merged.get("requested_state")) or str(merged.get("requested_state") or "execute").lower()
        result.append({
            **common,
            "lca_event_id":base_id+":interaction",
            "kind":"interaction",
            "state":None,
            "channel":source_channel or str(merged.get("channel") or "default"),
            "action":requested,
            "brightness":None,
            "source_entity":source_entity,
            "source_device":source_device,
            "source_channel":source_channel,
            "requested_state":requested,
            "target_entity":merged.get("target_entity"),
            "circuit_id":merged.get("circuit_id"),
            "interaction_kind":merged.get("interaction_kind") or "switch_trigger",
            "origin_mode":merged.get("origin_mode") or "unknown",
            "ha_context_id":merged.get("ha_context_id"),
            "ha_parent_id":merged.get("ha_parent_id"),
            "ha_user_id":merged.get("ha_user_id"),
        })
        return result

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
    # Alguns modelos publicam dois nomes para a mesma tecla física, por
    # exemplo l1/left, l2/center e l3/right. Quando ambos aparecem no mesmo
    # payload, normalizamos para o identificador numérico e evitamos eventos
    # e canais duplicados.
    raw_keys={str(ch).lower() for ch,_ in state_fields}
    alias_map={}
    for canonical,alias in (("l1","left"),("l2","center"),("l3","right")):
        if canonical in raw_keys and alias in raw_keys:
            alias_map[alias]=canonical

    seen=set()
    for ch,value in state_fields:
        normalized_ch=alias_map.get(str(ch).lower(),str(ch or "main"))
        st=_state(value)
        if not st or (normalized_ch,st) in seen:continue
        seen.add((normalized_ch,st))
        bright=merged.get("brightness")
        try:bright=float(bright) if bright is not None else None
        except (TypeError,ValueError):bright=None
        result.append({**common,"lca_event_id":f"{base_id}:state:{_slug(normalized_ch)}","kind":"state","state":st,"channel":normalized_ch,"action":None,"brightness":bright})
    return result
