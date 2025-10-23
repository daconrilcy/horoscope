"""Script d'aide à la rotation manuelle des clés OpenAI.

Ce script facilite la rotation des clés OpenAI avec audit uniquement, sans afficher les valeurs
secrètes et en écrivant des traces d'audit.
"""

from __future__ import annotations

import argparse

from backend.infra.secrets.vault_client import VaultClient

"""Manual OpenAI key rotation helper (audit only).

Usage (PowerShell):
  python -m backend.scripts.rotate_openai_key --key-id NEW_KEY_ID

Notes:
- Does not print secret values.
- Writes an audit line with timestamp and key id into ./artifacts/secrets/rotation_*.log
"""


def main() -> None:
    """Point d'entrée principal pour la rotation des clés OpenAI.

    Enregistre une rotation de clé OpenAI à des fins d'audit sans jamais exposer la valeur du
    secret.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--key-id",
        required=True,
        help="Identifier of the new OpenAI key (no secret value)",
    )
    args = parser.parse_args()

    vc = VaultClient()
    vc.rotate_openai_key(args.key_id)


if __name__ == "__main__":  # pragma: no cover - script entry
    main()
