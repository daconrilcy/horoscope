# ============================================================
# Tests : tests/test_retrieval_proxy_unit.py
# Objet  : Couvrir des chemins de base de RetrievalProxy/Adapters.
# ============================================================

from __future__ import annotations

import os

from backend.services.retrieval_proxy import RetrievalProxy, WeaviateAdapter, FAISSAdapter
from backend.services.retrieval_proxy import PineconeAdapter, ElasticVectorAdapter


def test_proxy_default_faiss() -> None:
    # Sans env, fallback FAISS
    os.environ.pop("RETRIEVAL_BACKEND", None)
    proxy = RetrievalProxy()
    res = proxy.search("q", top_k=1)
    assert isinstance(res, list)
    assert len(res) == 1


def test_faiss_adapter_limits() -> None:
    a = FAISSAdapter()
    res = a.search("hello", top_k=1)
    assert len(res) == 1
    res2 = a.search("hello", top_k=10)
    assert len(res2) <= 10


def test_weaviate_embed_and_empty_search() -> None:
    # Pas d'URL -> search retourne [] et embed renvoie un placeholder
    os.environ["WEAVIATE_URL"] = ""
    a = WeaviateAdapter()
    vecs = a.embed_texts(["a", "b"])
    assert len(vecs) == 2 and len(vecs[0]) == 3
    res = a.search("hello", top_k=3)
    assert res == []


def test_weaviate_embed_raises_on_empty() -> None:
    a = WeaviateAdapter()
    try:
        a.embed_texts([])
    except ValueError:
        pass
    else:  # pragma: no cover - should not happen
        assert False


def test_proxy_selects_other_adapters() -> None:
    os.environ["RETRIEVAL_BACKEND"] = "pinecone"
    p = RetrievalProxy()
    assert isinstance(p._adapter, PineconeAdapter)  # type: ignore[attr-defined]
    os.environ["RETRIEVAL_BACKEND"] = "elastic"
    e = RetrievalProxy()
    assert isinstance(e._adapter, ElasticVectorAdapter)  # type: ignore[attr-defined]


def test_other_adapters_behaviour() -> None:
    # Pinecone/Elastic: search with empty query -> [] ; embed returns 3-dim placeholder
    p = PineconeAdapter()
    e = ElasticVectorAdapter()
    assert p.search("") == []
    assert e.search("") == []
    assert len(p.embed_texts(["x"])) == 1
    assert len(e.embed_texts(["x"])) == 1
