from __future__ import annotations

from pathlib import Path

import importlib


def test_settings_reads_env_file(tmp_path: Path, monkeypatch) -> None:
    # Prepare a temp .env file overriding guard settings
    env = tmp_path / ".env.custom"
    env.write_text("LLM_GUARD_ENABLE=false\nLLM_GUARD_MAX_INPUT_LEN=7\n", encoding="utf-8")
    monkeypatch.setenv("ENV_FILE", str(env))

    # Reload settings module to pick up new ENV_FILE
    settings_mod = importlib.import_module("backend.core.settings")
    importlib.reload(settings_mod)
    get_settings = getattr(settings_mod, "get_settings")

    s = get_settings()
    assert s.LLM_GUARD_ENABLE is False
    assert s.LLM_GUARD_MAX_INPUT_LEN == 7
