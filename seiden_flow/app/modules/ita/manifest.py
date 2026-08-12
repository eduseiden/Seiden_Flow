from core.module_registry import ModuleManifest

MANIFEST = ModuleManifest(
    module_id="ita",
    name="Infrastructure Telemetry Analytics",
    version="0.2.0",
    description="Saúde e contexto operacional da infraestrutura a partir das capacidades de telemetria efetivamente disponíveis em cada ativo.",
    consumes=("infrastructure.telemetry_snapshot",),
    capabilities=("adaptive_telemetry", "compute", "memory", "storage", "network", "thermal", "power", "cooling", "availability", "native_thresholds", "telemetry_freshness", "events", "history", "asset_lifecycle", "vendor_agnostic"),
    portal_paths=("/ita", "/intelligence/ita"),
    api_prefixes=("/api/v1/ita",),
    dependencies=("bridge", "flow_core"),
)
