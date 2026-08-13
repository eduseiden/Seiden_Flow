from core.module_registry import ModuleManifest

MANIFEST = ModuleManifest(
    module_id="ita",
    name="Infrastructure Telemetry Analytics",
    version="0.3.1.2",
    description="Saúde e contexto operacional unificados de servidores, hosts e ambientes Seiden CAST a partir de telemetria adaptativa e estado canônico do Seiden Pulse.",
    consumes=("infrastructure.telemetry_snapshot",),
    capabilities=("adaptive_telemetry", "compute", "memory", "storage", "network", "thermal", "power", "cooling", "availability", "native_thresholds", "telemetry_freshness", "events", "history", "asset_lifecycle", "unified_assets", "fleet", "pulse", "canonical_state", "host_health", "vendor_agnostic"),
    portal_paths=("/ita", "/intelligence/ita", "/ita/fleet", "/intelligence/ita/fleet"),
    api_prefixes=("/api/v1/ita",),
    dependencies=("bridge", "flow_core"),
)
