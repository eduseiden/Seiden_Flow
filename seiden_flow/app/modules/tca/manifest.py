from core.module_registry import ModuleManifest

MANIFEST = ModuleManifest(
    module_id="tca",
    name="Thermal Control Analytics",
    version="0.6.1",
    description="Controle térmico analítico de ativos, excursões, recuperação, portas e energia.",
    consumes=("environment.temperature", "access.opening", "energy.power"),
    capabilities=("thermal_state", "thermal_excursion", "recovery_analysis", "cycle_analysis", "adaptive_views", "exceptions_first", "era_events"),
    portal_paths=("/tca", "/intelligence/tca"),
    api_prefixes=("/api/v1/tca",),
    dependencies=("bridge", "flow_core"),
)
