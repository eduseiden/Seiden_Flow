from __future__ import annotations


def solution_catalog() -> list[dict]:
    """Catálogo inicial de composições; não ativa módulos ainda não implementados."""
    return [
        {
            "solution_id": "seiden_one_analytics",
            "name": "Seiden One Analytics",
            "status": "active",
            "modules": ["hea", "eea", "tca"],
            "description": "Composição atualmente disponível no Seiden Flow.",
        },
        {
            "solution_id": "intelligent_living",
            "name": "Intelligent Living",
            "status": "planned",
            "modules": ["eea", "tca", "lca", "oda", "pra", "sfa", "hia", "ana", "nca"],
            "description": "Composição residencial em evolução; módulos planejados não são anunciados como ativos.",
        },
    ]
