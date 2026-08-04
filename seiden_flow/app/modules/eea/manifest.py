from core.module_registry import ModuleManifest

MANIFEST = ModuleManifest(
    module_id="eea",
    name="Environmental Experience Analytics",
    version="1.0",
    description="Conforto, estabilidade e evolução das condições ambientais.",
    consumes=("environment.observation",),
    capabilities=("environment_state", "experience_index", "timeline", "portfolio"),
    portal_paths=("/environment", "/intelligence/environment"),
    api_prefixes=("/api/v1/environment",),
    dependencies=("bridge", "flow_core"),
)
