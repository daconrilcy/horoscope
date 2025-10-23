"""
Client Vault pour la gestion des secrets avec fallback mock.

Ce module implémente un client Vault minimal avec support pour les mocks et l'audit des rotations de
clés pour les environnements de test.
"""

# ============================================================
# Module : backend/infra/secrets/vault_client.py
# Objet  : Accès Vault (récup/rotation secrets) avec fallback mock.
# ============================================================

from __future__ import annotations

import os
from datetime import datetime


class VaultClient:
    """
    Client Vault minimal avec fallback mock.

    - Ne journalise jamais de valeurs de secrets.
    - Peut utiliser des variables `VAULT_MOCK_<KEY>` pour simuler Vault en tests.
    """

    def __init__(self, enabled: bool | None = None) -> None:
        """Initialize Vault client with optional configuration."""
        self._url = os.getenv("VAULT_ADDR", "")
        self._token = os.getenv("VAULT_TOKEN", "")
        if enabled is None:
            env_val = (os.getenv("VAULT_ENABLED") or "").strip().lower()
            self._enabled = env_val in {"1", "true", "yes"}
        else:
            self._enabled = bool(enabled)

    @property
    def enabled(self) -> bool:  # pragma: no cover - trivial
        """
        Indique si le client Vault est activé.

        Returns:
            bool: True si Vault est activé, False sinon.
        """
        return self._enabled

    def get_secret(self, key: str) -> str:
        """
        Récupère un secret par clé.

        Ordre:
        1) si Vault désactivé → "".
        2) mock `VAULT_MOCK_<KEY>` (tests/dev).
        3) (placeholder) un backend réel peut être branché ici.
        """
        if not self._enabled:
            return ""
        # Mock pour tests: VAULT_MOCK_OPENAI_API_KEY, VAULT_MOCK_WEAVIATE_API_KEY, etc.
        mock_name = f"VAULT_MOCK_{key}"
        mock_val = os.getenv(mock_name)
        if mock_val:
            return mock_val
        # Point d'extension: implémentation via hvac
        # Ne pas logguer `key` et surtout pas sa valeur
        return ""

    def rotate_openai_key(self, new_key_id: str) -> None:
        """
        Rotation de clé OpenAI (audit only, sans divulguer la valeur).

        Écrit une trace d'audit (timestamp, key id) dans `artifacts/secrets/rotation_*.log`. La
        valeur n'est jamais logguée.
        """
        ts = datetime.utcnow().isoformat() + "Z"
        line = f"{ts} rotated_openai_key id={new_key_id}\n"
        # Audit file path (relative). En prod, préférer un système d'audit dédié.
        base_dir = os.path.join(os.getcwd(), "artifacts", "secrets")
        try:
            os.makedirs(base_dir, exist_ok=True)
            # filename per day to keep it simple
            day = ts.split("T")[0]
            fname = f"rotation_{day}.log"
            with open(os.path.join(base_dir, fname), "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            # Ne pas échouer sur l'audit, mais ne jamais afficher la valeur.
            pass
