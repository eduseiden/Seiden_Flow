from core.module_registry import ModuleManifest

MANIFEST = ModuleManifest(
    module_id="ita",
    name="Infrastructure Thermal Analytics",
    version="0.1.1",
    description="Saúde térmica, margem operacional e comportamento da infraestrutura computacional a partir de telemetria normalizada.",
    consumes=("infrastructure.telemetry_snapshot",),
    capabilities=("thermal_state", "thermal_deltas", "native_thresholds", "thermal_headroom", "telemetry_freshness", "fan_balance", "power_context", "trends", "events", "history", "vendor_agnostic"),
    portal_paths=("/ita", "/intelligence/ita"),
    api_prefixes=("/api/v1/ita",),
    dependencies=("bridge", "flow_core"),
)
