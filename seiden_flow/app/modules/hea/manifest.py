from core.module_registry import ModuleManifest

MANIFEST = ModuleManifest(
    module_id="hea",
    name="Human Experience Analytics",
    version="1.0",
    description="Indicadores agregados de experiência humana a partir de evidências normalizadas.",
    consumes=("vision.analysis_completed", "observation.human_experience"),
    capabilities=("experience_index", "emotion_distribution", "confidence", "history"),
    portal_paths=("/hea", "/intelligence/hea"),
    api_prefixes=("/api/v1/hea", "/api/v1/public/hea", "/api/v2/experience"),
    dependencies=("vision", "flow_core"),
)
