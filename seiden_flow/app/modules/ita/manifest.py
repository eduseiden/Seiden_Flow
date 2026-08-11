from core.module_registry import ModuleManifest

MANIFEST = ModuleManifest(
    module_id="ita",
    name="Infrastructure Thermal Analytics",
    version="0.1.0",
    description="Saúde térmica e eficiência de infraestrutura computacional a partir de telemetria normalizada.",
    consumes=("infrastructure.telemetry_snapshot",),
    capabilities=("thermal_state", "thermal_deltas", "native_thresholds", "power_context", "history", "vendor_agnostic"),
    portal_paths=("/ita", "/intelligence/ita"),
    api_prefixes=("/api/v1/ita",),
    dependencies=("bridge", "flow_core"),
)
