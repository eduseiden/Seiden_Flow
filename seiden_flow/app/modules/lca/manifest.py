from core.module_registry import ModuleManifest

MANIFEST = ModuleManifest(
    module_id="lca",
    name="Lighting Context Analytics",
    version="0.4.0.3",
    description="Compreende eventos, sessões, padrões e contexto espacial da iluminação, sem controlar dispositivos.",
    consumes=("lighting.state_changed", "lighting.interaction", "mqtt.message", "state_transition"),
    capabilities=("device_discovery", "spatial_configuration", "channel_configuration", "interaction_context", "relevant_event_processing", "lighting_sessions", "usage_analytics", "route_evidence", "device_lifecycle_management", "device_exclusions", "channel_scope_management", "lighting_relationship_model", "logical_lights", "virtual_parallels", "scene_learning", "interaction_origin_attribution", "effect_confirmation", "configurable_refresh", "event_consolidation", "advanced_diagnostics", "ux_refinement", "logical_state_consolidation", "seiden_visual_identity", "origin_analytics", "free_form_entity_resolution", "direct_point_confirmation", "channel_alias_normalization", "canonical_circuit_ids", "logical_circuit_consolidation", "interaction_point_metrics", "configuration_quality", "mqtt_device_identity", "canonical_channel_identity", "interaction_alias_suppression", "pending_interaction_resolution", "state_visual_language", "ui_density_refinement", "dark_mode_contrast", "canonical_circuit_state", "circuit_usage_sessions", "circuit_usage_analytics", "time_in_use_metrics", "bridge_state_transition_ingestion", "direct_state_canonicalization", "home_assistant_state_transition_ingestion", "multi_technology_direct_points"),
    portal_paths=("/lca", "/intelligence/lca"),
    api_prefixes=("/api/v1/lca",),
    dependencies=("bridge", "flow_core"),
)
