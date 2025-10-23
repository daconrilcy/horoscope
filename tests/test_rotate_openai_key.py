"""
Tests pour la rotation des clés OpenAI.

Ce module teste le processus de rotation des clés OpenAI avec vérification que les secrets ne sont
pas exposés dans les logs d'audit.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from glob import glob
from pathlib import Path
from typing import Any


def test_rotation_audit_does_not_log_secret(monkeypatch: Any, tmp_path: Path) -> None:
    """
    Teste que l'audit de rotation ne log pas les secrets.

    Vérifie que lors de la rotation des clés OpenAI, les secrets ne sont pas exposés dans les logs
    d'audit générés.
    """
    # Arrange: ensure artifacts dir is clean
    artifacts_dir = Path.cwd() / "artifacts" / "secrets"
    if artifacts_dir.exists():
        shutil.rmtree(artifacts_dir)

    # Vault enabled with a mock secret (value must never appear in logs)
    monkeypatch.setenv("VAULT_ENABLED", "true")
    monkeypatch.setenv("VAULT_MOCK_OPENAI_API_KEY", "dummy")

    key_id = "key-2025-10"

    # Act: run rotation via subprocess
    result = subprocess.run(
        [sys.executable, "-m", "backend.scripts.rotate_openai_key", "--key-id", key_id],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Assert: a rotation log file exists under artifacts/secrets
    files = glob(str(artifacts_dir / "rotation_*.log"))
    assert files, "rotation log file was not created"

    # Read latest file and validate contents
    latest = max(files, key=os.path.getmtime)
    content = Path(latest).read_text(encoding="utf-8")
    assert key_id in content
    # Ensure the mock secret value never appears
    assert "dummy" not in content
