from core.module_registry import ModuleRegistry
from modules.eea.manifest import MANIFEST as EEA_MANIFEST
from modules.hea.manifest import MANIFEST as HEA_MANIFEST
from modules.tca.manifest import MANIFEST as TCA_MANIFEST
from modules.lca.manifest import MANIFEST as LCA_MANIFEST


def build_module_registry() -> ModuleRegistry:
    registry = ModuleRegistry()
    registry.register_many((HEA_MANIFEST, EEA_MANIFEST, TCA_MANIFEST, LCA_MANIFEST))
    return registry
