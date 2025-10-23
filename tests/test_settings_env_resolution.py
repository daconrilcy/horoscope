"""
Tests pour la résolution des variables d'environnement.

Ce module teste le chargement et la résolution des variables d'environnement à partir de fichiers
.env personnalisés dans les settings.
"""

from __future__ import annotations

import importlib
from pathlib import Path

from backend.core.constants import (
    TEST_METRICS_MAX_INPUT_LEN,
)


def test_settings_reads_env_file(tmp_path: Path, monkeypatch) -> None:
    """
    Teste que les settings lisent correctement les fichiers d'environnement.

    Vérifie que les variables d'environnement définies dans un fichier .env personnalisé sont
    correctement chargées et appliquées aux settings.
    """
    # Prepare a temp .env file overriding guard settings
    env = tmp_path / ".env.custom"
    env.write_text(
        "LLM_GUARD_ENABLE=false\nLLM_GUARD_MAX_INPUT_LEN=7\n", encoding="utf-8"
    )
    monkeypatch.setenv("ENV_FILE", str(env))

    # Reload settings module to pick up new ENV_FILE
    settings_mod = importlib.import_module("backend.core.settings")
    importlib.reload(settings_mod)
    get_settings = settings_mod.get_settings

    s = get_settings()
    assert s.LLM_GUARD_ENABLE is False
    assert s.LLM_GUARD_MAX_INPUT_LEN == TEST_METRICS_MAX_INPUT_LEN
