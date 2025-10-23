"""
Tests pour les chemins de configuration du container.

Ce module teste les différents chemins de configuration du container selon les variables
d'environnement et les dépendances disponibles.
"""

from __future__ import annotations

import importlib
from typing import Any

from backend.core.container import Container


def _new_container(monkeypatch: Any, env: dict[str, str]) -> Any:
    """Crée un nouveau container avec un environnement isolé."""
    # Isolate environment for this container instance
    for k in [
        "REDIS_URL",
        "REQUIRE_REDIS",
    ]:
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    # Reload module to pick up new settings
    mod = importlib.import_module("backend.core.container")
    importlib.reload(mod)
    # Instantiate a fresh Container explicitly
    Container = mod.Container
    return Container()


def test_container_memory_path(monkeypatch: Any) -> None:
    """Teste que le container utilise le backend mémoire par défaut."""
    c = _new_container(monkeypatch, {})
    assert c.storage_backend in {"memory", "memory-fallback"}
    assert c.user_repo is not None


def test_container_redis_path_without_require(monkeypatch: Any) -> None:
    """Teste que le container peut utiliser Redis sans l'exiger."""
    # With REDIS_URL set but not required, constructor should not raise
    c = _new_container(monkeypatch, {"REDIS_URL": "redis://localhost:6379/0"})
    assert c.storage_backend in {"redis", "memory-fallback", "memory"}


def test_container_require_redis_without_url_raises(monkeypatch: Any) -> None:
    """Teste que le container plante si Redis est requis mais non disponible."""
    # REQUIRE_REDIS=true and no REDIS_URL should raise upon instantiation
    for k in ["REDIS_URL"]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("REQUIRE_REDIS", "true")

    raised = False
    try:
        Container()
    except RuntimeError:
        raised = True
    assert (
        raised
    ), "Container should raise when REQUIRE_REDIS=true and REDIS_URL is missing"
