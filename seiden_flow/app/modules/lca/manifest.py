from core.module_registry import ModuleManifest

MANIFEST = ModuleManifest(
    module_id="lca",
    name="Lighting Context Analytics",
    version="0.1.0",
    description="Compreende eventos, sessões, padrões e contexto espacial da iluminação, sem controlar dispositivos.",
    consumes=("lighting.state_changed", "lighting.interaction", "mqtt.message"),
    capabilities=("device_discovery", "interaction_context", "lighting_sessions", "usage_analytics", "route_evidence"),
    portal_paths=("/lca", "/intelligence/lca"),
    api_prefixes=("/api/v1/lca",),
    dependencies=("bridge", "flow_core"),
)
