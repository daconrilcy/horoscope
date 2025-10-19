# ============================================================
# Module : backend/infra/secrets/vault_client.py
# Objet  : Accès Vault (récup/rotation secrets) — squelette.
# ============================================================

from __future__ import annotations

import os


class VaultClient:
    """Client Vault minimal (squelette)."""

    def __init__(self) -> None:
        # TODO: initialiser connexion réelle (HVAC ou autre)
        self._url = os.getenv("VAULT_ADDR", "")
        self._token = os.getenv("VAULT_TOKEN", "")

    def get_secret(self, key: str) -> str:
        """Récupère un secret par clé (placeholder)."""
        _ = key
        return ""

    def rotate_openai_key(self) -> None:
        """Rotation de clé OpenAI (placeholder)."""
        return None
