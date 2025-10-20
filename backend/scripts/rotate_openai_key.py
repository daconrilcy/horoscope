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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--key-id", required=True, help="Identifier of the new OpenAI key (no secret value)"
    )
    args = parser.parse_args()

    vc = VaultClient()
    vc.rotate_openai_key(args.key_id)


if __name__ == "__main__":  # pragma: no cover - script entry
    main()
