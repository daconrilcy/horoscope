from __future__ import annotations

import json
import os
from pathlib import Path

from backend.infra.vecstores.faiss_store import FaissMultiTenantAdapter


def test_purge_audit_file(tmp_path, monkeypatch) -> None:
    audit_dir = tmp_path / "artifacts" / "audit"
    audit_dir.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PURGE_ACTOR", "tester")

    a = FaissMultiTenantAdapter(data_dir=str(tmp_path / "var" / "faiss"))
    # directly call audit via purge (no index needed)
    a.purge_tenant("tX")

    log = audit_dir / "tenant_purge.log"
    assert log.exists()
    line = log.read_text(encoding="utf-8").strip()
    rec = json.loads(line)
    assert rec.get("tenant") == "tx"  # normalized lower-case
    assert rec.get("actor") == "tester"
    assert rec.get("backend") == "faiss"
    assert rec.get("action") == "purge"
    assert rec.get("status") in {"success", "error"}
