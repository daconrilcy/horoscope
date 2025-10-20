# ============================================================
# Tests : tests/test_vault_client.py
# Objet  : Vault client lecture + fallback env via container.
# ============================================================

from __future__ import annotations

import os
from typing import Any

from backend.core.container import container
from backend.infra.secrets.vault_client import VaultClient


def test_vault_reads_mock_env(monkeypatch: Any) -> None:
    monkeypatch.setenv("VAULT_ENABLED", "true")
    monkeypatch.setenv("VAULT_MOCK_OPENAI_API_KEY", "sk-test-abc123")
    vc = VaultClient()
    val = vc.get_secret("OPENAI_API_KEY")
    assert val == "sk-test-abc123"


def test_container_fallback_env_when_vault_disabled(monkeypatch: Any) -> None:
    monkeypatch.delenv("VAULT_ENABLED", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-xyz999")
    val = container.resolve_secret("OPENAI_API_KEY")
    assert val == "sk-env-xyz999"

