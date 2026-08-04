from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class ModuleManifest:
    """Contrato mínimo de um módulo analítico do Seiden Flow."""

    module_id: str
    name: str
    version: str
    status: str = "active"
    description: str = ""
    consumes: tuple[str, ...] = field(default_factory=tuple)
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    portal_paths: tuple[str, ...] = field(default_factory=tuple)
    api_prefixes: tuple[str, ...] = field(default_factory=tuple)
    dependencies: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["enabled"] = self.status == "active"
        return payload


class ModuleRegistry:
    """Registro central e determinístico dos módulos carregados pela plataforma."""

    def __init__(self) -> None:
        self._modules: dict[str, ModuleManifest] = {}

    def register(self, manifest: ModuleManifest) -> None:
        module_id = manifest.module_id.strip().lower()
        if not module_id:
            raise ValueError("module_id não pode ser vazio")
        if module_id in self._modules:
            raise ValueError(f"Módulo já registrado: {module_id}")
        if module_id != manifest.module_id:
            raise ValueError("module_id deve estar em minúsculas e sem espaços")
        self._modules[module_id] = manifest

    def register_many(self, manifests: Iterable[ModuleManifest]) -> None:
        for manifest in manifests:
            self.register(manifest)

    def get(self, module_id: str) -> ModuleManifest | None:
        return self._modules.get(module_id.strip().lower())

    def all(self) -> list[ModuleManifest]:
        return [self._modules[key] for key in sorted(self._modules)]

    def public_catalog(self) -> list[dict]:
        return [manifest.to_dict() for manifest in self.all()]

    def summary(self) -> dict:
        modules = self.all()
        return {
            "registered": len(modules),
            "active": sum(1 for item in modules if item.status == "active"),
            "module_ids": [item.module_id for item in modules],
        }
