from __future__ import annotations
import json, os
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Settings:
    log_level: str = "info"
    api_key: str = ""
    timezone: str = "America/Sao_Paulo"
    retention_days: int = 365
    subscribe_home_assistant_events: bool = True
    bridge_presence_event: str = "seiden_presence"
    bridge_online_event: str = "seiden_reader_online"
    bridge_offline_event: str = "seiden_reader_offline"
    publish_summary_to_home_assistant: bool = True
    cleanup_interval_hours: int = 12
    webhook_max_body_mb: int = 5
    organization_id: str = "default_organization"
    organization_name: str = "Organização padrão"
    site_id: str = "default_site"
    site_name: str = "Site padrão"
    config_dir: str = "/config"

def _bool(v, default):
    if isinstance(v, bool): return v
    if isinstance(v, str): return v.lower() in {"1","true","yes","on"}
    return default

def load_settings() -> Settings:
    p=Path(os.getenv("OPTIONS_PATH","/data/options.json")); raw={}
    if p.exists(): raw=json.loads(p.read_text(encoding="utf-8"))
    return Settings(
        log_level=str(raw.get("log_level","info")), api_key=str(raw.get("api_key","") or ""),
        timezone=str(raw.get("timezone","America/Sao_Paulo")), retention_days=int(raw.get("retention_days",365)),
        subscribe_home_assistant_events=_bool(raw.get("subscribe_home_assistant_events"),True),
        bridge_presence_event=str(raw.get("bridge_presence_event","seiden_presence")),
        bridge_online_event=str(raw.get("bridge_online_event","seiden_reader_online")),
        bridge_offline_event=str(raw.get("bridge_offline_event","seiden_reader_offline")),
        publish_summary_to_home_assistant=_bool(raw.get("publish_summary_to_home_assistant"),True),
        cleanup_interval_hours=int(raw.get("cleanup_interval_hours",12)), webhook_max_body_mb=int(raw.get("webhook_max_body_mb",5)),
        organization_id=str(raw.get("organization_id","default_organization")), organization_name=str(raw.get("organization_name","Organização padrão")),
        site_id=str(raw.get("site_id","default_site")), site_name=str(raw.get("site_name","Site padrão")),
        config_dir=os.getenv("FLOW_CONFIG_DIR","/config"))
