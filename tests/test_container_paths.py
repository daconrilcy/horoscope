from __future__ import annotations

import os
import importlib
import types
from typing import Any


def _new_container(monkeypatch: Any, env: dict[str, str]) -> Any:
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
    Container = getattr(mod, "Container")
    return Container()


def test_container_memory_path(monkeypatch: Any) -> None:
    c = _new_container(monkeypatch, {})
    assert getattr(c, "storage_backend") in {"memory", "memory-fallback"}
    assert c.user_repo is not None


def test_container_redis_path_without_require(monkeypatch: Any) -> None:
    # With REDIS_URL set but not required, constructor should not raise
    c = _new_container(monkeypatch, {"REDIS_URL": "redis://localhost:6379/0"})
    assert getattr(c, "storage_backend") in {"redis", "memory-fallback", "memory"}


def test_container_require_redis_without_url_raises(monkeypatch: Any) -> None:
    # REQUIRE_REDIS=true and no REDIS_URL should raise upon instantiation
    for k in ["REDIS_URL"]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("REQUIRE_REDIS", "true")

    from backend.core.container import Container

    raised = False
    try:
        Container()
    except RuntimeError:
        raised = True
    assert raised, "Container should raise when REQUIRE_REDIS=true and REDIS_URL is missing"
