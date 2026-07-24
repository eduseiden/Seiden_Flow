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
    observation_engine_enabled: bool = True
    observation_retain_raw_minutes: int = 30
    human_experience_enabled: bool = True
    human_experience_minimum_samples: int = 10
    human_experience_aggregation_window_minutes: int = 15
    human_experience_minimum_confidence: float = 0.75
    human_experience_enabled_sources: tuple[str, ...] = ()
    human_experience_positive_weight: float = 1.0
    human_experience_neutral_weight: float = 0.0
    human_experience_negative_weight: float = -1.0
    hea_portal_enabled: bool = True
    hea_portal_title: str = "Human Experience Analytics"
    hea_portal_subtitle: str = "Indicadores agregados de experiência"
    hea_portal_default_hours: int = 24
    hea_portal_refresh_seconds: int = 10
    hea_portal_show_sources: bool = True
    hea_portal_privacy_notice: str = "Dados agregados e anônimos. Nenhuma identificação pessoal é exibida."
    hea_portal_allowed_origins: tuple[str, ...] = ()
    hea_public_hostname: str = ""
    hea_public_restrict_routes: bool = False
    config_dir: str = "/config"

def _bool(v, default):
    if isinstance(v, bool): return v
    if isinstance(v, str): return v.lower() in {"1","true","yes","on"}
    return default

def _sources(v):
    if isinstance(v, list): return tuple(str(x).strip() for x in v if str(x).strip())
    if isinstance(v, str): return tuple(x.strip() for x in v.split(',') if x.strip())
    return ()

def _strings(v):
    if isinstance(v, list): return tuple(str(x).strip() for x in v if str(x).strip())
    if isinstance(v, str): return tuple(x.strip() for x in v.split(',') if x.strip())
    return ()

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
        observation_engine_enabled=_bool(raw.get("observation_engine_enabled"),True),
        observation_retain_raw_minutes=max(1,int(raw.get("observation_retain_raw_minutes",30))),
        human_experience_enabled=_bool(raw.get("human_experience_enabled"),True),
        human_experience_minimum_samples=max(1,int(raw.get("human_experience_minimum_samples",10))),
        human_experience_aggregation_window_minutes=max(1,int(raw.get("human_experience_aggregation_window_minutes",15))),
        human_experience_minimum_confidence=max(0.0,min(1.0,float(raw.get("human_experience_minimum_confidence",0.75)))),
        human_experience_enabled_sources=_sources(raw.get("human_experience_enabled_sources",[])),
        human_experience_positive_weight=float(raw.get("human_experience_positive_weight",1.0)),
        human_experience_neutral_weight=float(raw.get("human_experience_neutral_weight",0.0)),
        human_experience_negative_weight=float(raw.get("human_experience_negative_weight",-1.0)),
        hea_portal_enabled=_bool(raw.get("hea_portal_enabled"),True),
        hea_portal_title=str(raw.get("hea_portal_title","Human Experience Analytics")),
        hea_portal_subtitle=str(raw.get("hea_portal_subtitle","Indicadores agregados de experiência")),
        hea_portal_default_hours=max(1,min(720,int(raw.get("hea_portal_default_hours",24)))),
        hea_portal_refresh_seconds=max(5,min(3600,int(raw.get("hea_portal_refresh_seconds",10)))),
        hea_portal_show_sources=_bool(raw.get("hea_portal_show_sources"),True),
        hea_portal_privacy_notice=str(raw.get("hea_portal_privacy_notice","Dados agregados e anônimos. Nenhuma identificação pessoal é exibida.")),
        hea_portal_allowed_origins=_strings(raw.get("hea_portal_allowed_origins",[])),
        hea_public_hostname=str(raw.get("hea_public_hostname","") or "").strip().lower().rstrip("."),
        hea_public_restrict_routes=_bool(raw.get("hea_public_restrict_routes"),False),
        config_dir=os.getenv("FLOW_CONFIG_DIR","/config"))
