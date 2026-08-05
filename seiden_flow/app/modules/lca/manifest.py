from core.module_registry import ModuleManifest

MANIFEST = ModuleManifest(
    module_id="lca",
    name="Lighting Context Analytics",
    version="0.3.1",
    description="Compreende eventos, sessões, padrões e contexto espacial da iluminação, sem controlar dispositivos.",
    consumes=("lighting.state_changed", "lighting.interaction", "mqtt.message"),
    capabilities=("device_discovery", "spatial_configuration", "channel_configuration", "interaction_context", "relevant_event_processing", "lighting_sessions", "usage_analytics", "route_evidence", "device_lifecycle_management", "device_exclusions", "channel_scope_management", "lighting_relationship_model", "logical_lights", "virtual_parallels", "scene_learning", "interaction_origin_attribution", "effect_confirmation", "configurable_refresh"),
    portal_paths=("/lca", "/intelligence/lca"),
    api_prefixes=("/api/v1/lca",),
    dependencies=("bridge", "flow_core"),
)
