# ============================================================
# Tests : tests/test_shadow_read.py
# Objet  : Vérifier le shadow-read et l'agreement@5.
# ============================================================

from __future__ import annotations

import importlib
from typing import Any

from backend.app.metrics import RETRIEVAL_AGREEMENT_AT_5


class _FakeLLM:
    def generate(self, messages: list[dict[str, Any]]) -> str:  # pragma: no cover - trivial
        return "ok"


def test_shadow_read_agreement(monkeypatch: Any) -> None:
    # Forcer RETRIEVAL_BACKEND weaviate et shadow 100%
    monkeypatch.setenv("RETRIEVAL_BACKEND", "weaviate")
    monkeypatch.setenv("RETRIEVAL_SHADOW_READ", "true")
    monkeypatch.setenv("RETRIEVAL_SHADOW_READ_PCT", "1.0")
    monkeypatch.setenv("WEAVIATE_URL", "https://example.weaviate.local")

    # Monkeypatch orchestrator to avoid real FAISS/LLM work
    import backend.domain.chat_orchestrator as mod

    # primary results: ids a,b,c,d,e
    class _S:
        def __init__(self, id_: str) -> None:
            self.doc = type("D", (), {"id": id_, "text": id_})

    def _fake_query(self, q):  # type: ignore[no-redef]
        return [_S(x) for x in ["a", "b", "c", "d", "e"]]

    # shadow returns a,c,x,y,z → agreement 2/5 = 0.4
    def _fake_search(self, query: str, top_k: int = 5, tenant: str | None = None):  # type: ignore[no-redef]
        return [{"id": x} for x in ["a", "c", "x", "y", "z"]]

    monkeypatch.setattr("backend.domain.retriever.Retriever.query", _fake_query)
    monkeypatch.setattr("backend.services.retrieval_proxy.RetrievalProxy.search", _fake_search)

    importlib.reload(mod)
    orch = mod.ChatOrchestrator(llm=_FakeLLM())

    # Call and verify gauge value updated
    orch.advise(chart={"chart": {}}, today={"eao": 0.5}, question="hello")
    val = RETRIEVAL_AGREEMENT_AT_5.labels("weaviate")._value.get()
    assert 0.39 < val < 0.41

