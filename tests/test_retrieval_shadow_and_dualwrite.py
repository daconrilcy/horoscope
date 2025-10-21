from __future__ import annotations

import os
import time
from typing import Any

from backend.app import metrics as m
from backend.services import retrieval_target as rtarget
from backend.core.container import container
from backend.services.retrieval_proxy import RetrievalProxy


def test_dual_write_errors_metric_on_failure(monkeypatch: Any) -> None:
    # Enable dual-write and force target write to raise
    monkeypatch.setenv("FF_RETRIEVAL_DUAL_WRITE", "true")
    called: dict[str, int] = {"n": 0}

    def _boom(doc: dict, tenant: str | None = None) -> None:  # type: ignore[unused-argument]
        called["n"] += 1
        raise RuntimeError("target down")

    monkeypatch.setattr(rtarget, "write_to_target", _boom)
    # also fix target name for label stability
    monkeypatch.setenv("RETRIEVAL_TARGET_BACKEND", "weaviate")

    proxy = RetrievalProxy()
    proxy.ingest({"id": "x", "text": "hello"}, tenant="t1")

    # Ensure write attempted and error metric incremented
    assert called["n"] == 1
    # Access Prom client internal value for assertion
    val = m.RETRIEVAL_DUAL_WRITE_ERRORS.labels("weaviate", "t1")._value.get()  # type: ignore[attr-defined]
    assert float(val) >= 1.0


def test_shadow_read_emits_metrics(monkeypatch: Any) -> None:
    # Enable shadow-read; target adapter returns a controlled result set
    monkeypatch.setenv("FF_RETRIEVAL_SHADOW_READ", "true")
    monkeypatch.setenv("RETRIEVAL_TARGET_BACKEND", "elastic")
    # Ensure tenant label is not collapsed by whitelist
    try:
        monkeypatch.setattr(container.settings, "ALLOWED_TENANTS", [], raising=False)
    except Exception:
        pass

    class _FakeAdapter:
        def embed_texts(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover - unused
            return [[0.0] * 3 for _ in texts]

        def search(self, query: str, top_k: int = 5, tenant: str | None = None) -> list[dict]:
            # Return overlapping ids to get non-zero agreement and ndcg
            return [
                {"id": "doc_1", "score": 0.5, "metadata": {"tenant": tenant or "default"}},
                {"id": "shadow_only", "score": 0.4, "metadata": {"tenant": tenant or "default"}},
            ][:top_k]

    monkeypatch.setattr(rtarget, "get_target_adapter", lambda: _FakeAdapter())

    proxy = RetrievalProxy()
    # Force primary adapter to return stable ids
    class _Primary:
        def embed_texts(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover - unused
            return [[0.0] * 3 for _ in texts]

        def search(self, query: str, top_k: int = 5, tenant: str | None = None) -> list[dict]:
            return [
                {"id": "doc_1", "score": 0.99, "metadata": {"tenant": tenant or "default"}},
                {"id": "doc_2", "score": 0.95, "metadata": {"tenant": tenant or "default"}},
            ][:top_k]

    proxy._adapter = _Primary()  # type: ignore[attr-defined]
    res = proxy.search(query="q", top_k=5, tenant="bench")
    assert isinstance(res, list)
    # Allow shadow thread to run (poll up to 1s)
    a = 0.0
    n = 0.0
    # Try both 'bench' and potential 'unknown' label depending on whitelist
    for _ in range(20):
        a = float(m.RETRIEVAL_SHADOW_AGREEMENT_AT_5.labels("elastic", "bench")._value.get())  # type: ignore[attr-defined]
        n = float(m.RETRIEVAL_SHADOW_NDCG_AT_10.labels("elastic", "bench")._value.get())  # type: ignore[attr-defined]
        if a == 0.0 and n == 0.0:
            a = float(m.RETRIEVAL_SHADOW_AGREEMENT_AT_5.labels("elastic", "unknown")._value.get())  # type: ignore[attr-defined]
            n = float(m.RETRIEVAL_SHADOW_NDCG_AT_10.labels("elastic", "unknown")._value.get())  # type: ignore[attr-defined]
        if a > 0.0 or n > 0.0:
            break
        time.sleep(0.05)
    assert float(a) > 0.0
    assert float(n) >= 0.0
