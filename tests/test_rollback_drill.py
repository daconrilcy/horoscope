from __future__ import annotations

import json
from pathlib import Path

from scripts.rollback_retrieval import _update_env_lines


def test_update_env_lines_appends_and_overrides(tmp_path: Path) -> None:
    base = ["APP_ENV=dev\n", "# comment\n", "RETRIEVAL_BACKEND=weaviate\n"]
    updated = _update_env_lines(base)
    content = "".join(updated)
    assert "RETRIEVAL_BACKEND=faiss" in content
    assert "FF_RETRIEVAL_DUAL_WRITE=OFF" in content
    assert "FF_RETRIEVAL_SHADOW_READ=OFF" in content


def test_rollback_script_dry_run(tmp_path: Path) -> None:
    # Prepare a temp .env and run the script in dry-run mode
    envf = tmp_path / ".env"
    envf.write_text("RETRIEVAL_BACKEND=weaviate\n", encoding="utf-8")

    import subprocess, sys

    cmd = [
        sys.executable,
        "scripts/rollback_retrieval.py",
        "--env-file",
        str(envf),
        "--dry-run",
        "--operator",
        "tester",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0

    log_path = Path("artifacts/rollback_drill_log.ndjson")
    assert log_path.exists()
    last = log_path.read_text(encoding="utf-8").strip().splitlines()[-1]
    obj = json.loads(last)
    assert obj.get("apply") is False and obj.get("operator") == "tester"

