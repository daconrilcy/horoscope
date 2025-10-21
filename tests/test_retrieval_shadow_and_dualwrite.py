from __future__ import annotations

import os
import time
from typing import Any

from backend.app import metrics as m
from backend.services import retrieval_target as rtarget
from backend.core.container import container
from backend.services.retrieval_proxy import RetrievalProxy, _reset_shadow_executor_for_tests


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
    monkeypatch.setenv("FF_RETRIEVAL_SHADOW_SAMPLE_RATE", "1.0")
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
    # Allow shadow worker to run (poll up to 1s). Check histogram count via labels (backend, k, sample)
    from prometheus_client import generate_latest

    ok = False
    for _ in range(20):
        scrape = generate_latest().decode("utf-8")
        if (
            "retrieval_shadow_agreement_at_5_count" in scrape
            and 'backend="elastic",k="2",sample="true"' in scrape
        ) and (
            "retrieval_shadow_ndcg_at_10_count" in scrape
            and 'backend="elastic",k="2",sample="true"' in scrape
        ):
            ok = True
            break
        time.sleep(0.05)
    assert ok


def test_shadow_sample_rate_and_queue_drop(monkeypatch: Any) -> None:
    _reset_shadow_executor_for_tests()
    monkeypatch.setenv("FF_RETRIEVAL_SHADOW_READ", "true")
    monkeypatch.setenv("RETRIEVAL_TARGET_BACKEND", "elastic")
    monkeypatch.setenv("RETRIEVAL_SHADOW_THREADS", "0")
    monkeypatch.setenv("RETRIEVAL_SHADOW_QUEUE_MAX", "1")
    monkeypatch.setenv("FF_RETRIEVAL_SHADOW_SAMPLE_RATE", "1.0")

    class _FakeAdapter:
        def search(self, query: str, top_k: int = 5, tenant: str | None = None) -> list[dict]:  # pragma: no cover - not used due to drop
            return []

    monkeypatch.setattr(rtarget, "get_target_adapter", lambda: _FakeAdapter())

    proxy = RetrievalProxy()
    proxy._adapter = type("P", (), {"search": lambda self, **kw: [{"id": "doc_1"}], "embed_texts": lambda self, t: []})()  # type: ignore
    from prometheus_client import generate_latest
    before_scrape = generate_latest().decode("utf-8")
    proxy.search(query="q", top_k=1, tenant="tq")
    proxy.search(query="q2", top_k=1, tenant="tq")
    time.sleep(0.05)
    after_scrape = generate_latest().decode("utf-8")
    assert after_scrape.count('retrieval_shadow_dropped_total{reason="queue_full"}') >= before_scrape.count('retrieval_shadow_dropped_total{reason="queue_full"}') + 1


def test_shadow_timeout_drops(monkeypatch: Any) -> None:
    _reset_shadow_executor_for_tests()
    monkeypatch.setenv("FF_RETRIEVAL_SHADOW_READ", "true")
    monkeypatch.setenv("RETRIEVAL_TARGET_BACKEND", "elastic")
    monkeypatch.setenv("FF_RETRIEVAL_SHADOW_SAMPLE_RATE", "1.0")
    monkeypatch.setenv("RETRIEVAL_SHADOW_TIMEOUT_MS", "1")

    class _SlowAdapter:
        def search(self, query: str, top_k: int = 5, tenant: str | None = None) -> list[dict]:
            time.sleep(0.02)
            return [{"id": "doc_slow"}]

    monkeypatch.setattr(rtarget, "get_target_adapter", lambda: _SlowAdapter())
    proxy = RetrievalProxy()
    proxy._adapter = type("P", (), {"search": lambda self, **kw: [{"id": "doc_1"}]})()  # type: ignore
    from prometheus_client import generate_latest
    before_scrape = generate_latest().decode("utf-8")
    proxy.search(query="q", top_k=1, tenant="tt")
    time.sleep(0.05)
    after_scrape = generate_latest().decode("utf-8")
    assert after_scrape.count('retrieval_shadow_dropped_total{reason="timeout"}') >= before_scrape.count('retrieval_shadow_dropped_total{reason="timeout"}') + 1
