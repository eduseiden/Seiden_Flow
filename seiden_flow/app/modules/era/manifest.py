from core.module_registry import ModuleManifest

MANIFEST = ModuleManifest(
    module_id="era",
    name="Event Response Automation",
    version="0.1.0",
    description="Resposta transversal a eventos da Seiden One: correlação de incidentes, políticas, notificações e recuperação.",
    consumes=(
        "infrastructure.alert",
        "infrastructure.telemetry_stale",
        "infrastructure.telemetry_restored",
        "seiden.event",
    ),
    capabilities=(
        "incident_correlation",
        "deduplication",
        "policy_delays",
        "recovery",
        "telegram",
        "email",
        "audit_delivery",
        "cross_module_events",
    ),
    portal_paths=("/era", "/intelligence/era"),
    api_prefixes=("/api/v1/era",),
    dependencies=("flow_core",),
)
