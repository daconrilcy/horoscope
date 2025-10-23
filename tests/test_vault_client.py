"""Tests pour le client Vault avec lecture et fallback environnement.

Ce module teste le client Vault incluant la lecture des secrets depuis l'environnement mock et le
fallback vers les variables d'environnement.
"""

# ============================================================
# Tests : tests/test_vault_client.py
# Objet  : Vault client lecture + fallback env via container.
# ============================================================

from __future__ import annotations

from typing import Any

from backend.core.container import container
from backend.infra.secrets.vault_client import VaultClient


def test_vault_reads_mock_env(monkeypatch: Any) -> None:
    """Teste la lecture des secrets depuis l'environnement mock de Vault.

    Vérifie que le client Vault peut lire correctement les secrets configurés via les variables
    d'environnement mock.
    """
    monkeypatch.setenv("VAULT_ENABLED", "true")
    monkeypatch.setenv("VAULT_MOCK_OPENAI_API_KEY", "sk-test-abc123")
    vc = VaultClient()
    val = vc.get_secret("OPENAI_API_KEY")
    assert val == "sk-test-abc123"


def test_container_fallback_env_when_vault_disabled(monkeypatch: Any) -> None:
    """Teste le fallback vers l'environnement quand Vault est désactivé.

    Vérifie que le container utilise les variables d'environnement standard quand Vault est
    désactivé.
    """
    monkeypatch.delenv("VAULT_ENABLED", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-xyz999")
    val = container.resolve_secret("OPENAI_API_KEY")
    assert val == "sk-env-xyz999"
