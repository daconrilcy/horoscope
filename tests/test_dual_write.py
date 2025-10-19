# ============================================================
# Tests : tests/test_dual_write.py
# Objet  : Vérifier la double écriture et les métriques d'erreur.
# ============================================================

from __future__ import annotations

import os
from typing import Any

from backend.app.metrics import RETRIEVAL_DUAL_WRITE_ERRORS
from backend.domain.retrieval_types import Document
from backend.services.dual_write_ingestor import DualWriteIngestor


def test_dual_write_attempts_and_errors(monkeypatch: Any) -> None:
    # Activer dual-write avec backend weaviate
    monkeypatch.setenv("RETRIEVAL_BACKEND", "weaviate")
    monkeypatch.setenv("WEAVIATE_URL", "https://example.weaviate.local")

    ingestor = DualWriteIngestor("weaviate")

    calls: list[dict[str, Any]] = []

    class _Resp:
        def __init__(self, code: int) -> None:
            self.status_code = code

    import httpx

    _orig_post = httpx.Client.post

    def _fake_post(self, url: str, json: dict[str, Any], **kwargs: Any):  # type: ignore[no-redef]
        calls.append(json)
        # Simuler une erreur 500 sur un doc sur deux
        if len(calls) % 2 == 0:
            return _Resp(500)
        return _Resp(200)

    monkeypatch.setattr("httpx.Client.post", _fake_post)

    docs = [Document(id=f"d{i}", text=f"t{i}") for i in range(6)]
    before = RETRIEVAL_DUAL_WRITE_ERRORS.labels("weaviate")._value.get()
    res = ingestor.ingest(docs, tenant="t1")
    after = RETRIEVAL_DUAL_WRITE_ERRORS.labels("weaviate")._value.get()

    # FAISS indexation retourne 6; cible a tenté 6 posts, 3 ont échoué
    assert res["faiss"] == 6
    assert res["target"] == 3
    assert len(calls) == 6
    assert after - before == 3

