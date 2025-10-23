# ============================================================
# Tests : tests/test_retrieval_proxy_unit.py
# Objet  : Couvrir des chemins de base de RetrievalProxy/Adapters.
# ============================================================
"""
Tests unitaires pour le proxy de récupération.

Ce module teste les adaptateurs et le proxy de récupération avec différents backends et
configurations.
"""

from __future__ import annotations

import os

from backend.core.constants import (
    TEST_DEFAULT_TENANTS,
    TEST_DEFAULT_TOPK,
    TUPLE_LENGTH,
)
from backend.services.retrieval_proxy import (
    ElasticVectorAdapter,
    FAISSAdapter,
    PineconeAdapter,
    RetrievalProxy,
    WeaviateAdapter,
)


def test_proxy_default_faiss() -> None:
    """Teste que le proxy utilise FAISS par défaut."""
    # Sans env, fallback FAISS
    os.environ.pop("RETRIEVAL_BACKEND", None)
    proxy = RetrievalProxy()
    res = proxy.search("q", top_k=1)
    assert isinstance(res, list)
    assert len(res) == 1


def test_faiss_adapter_limits() -> None:
    """Teste les limites de l'adaptateur FAISS."""
    a = FAISSAdapter()
    res = a.search("hello", top_k=1)
    assert len(res) == 1
    res2 = a.search("hello", top_k=10)
    assert len(res2) <= TEST_DEFAULT_TOPK


def test_weaviate_embed_and_empty_search() -> None:
    """Teste Weaviate avec URL vide : search retourne [] et embed renvoie un placeholder."""
    # Pas d'URL -> search retourne [] et embed renvoie un placeholder
    os.environ["WEAVIATE_URL"] = ""
    a = WeaviateAdapter()
    vecs = a.embed_texts(["a", "b"])
    assert len(vecs) == TUPLE_LENGTH and len(vecs[0]) == TEST_DEFAULT_TENANTS
    res = a.search("hello", top_k=3)
    assert res == []


def test_weaviate_embed_raises_on_empty() -> None:
    """Teste que Weaviate lève une exception sur une liste vide."""
    a = WeaviateAdapter()
    try:
        a.embed_texts([])
    except ValueError:
        return
    raise AssertionError()


def test_proxy_selects_other_adapters() -> None:
    """Teste que le proxy sélectionne les autres adaptateurs correctement."""
    os.environ["RETRIEVAL_BACKEND"] = "pinecone"
    p = RetrievalProxy()
    assert isinstance(p._adapter, PineconeAdapter)  # type: ignore[attr-defined]
    os.environ["RETRIEVAL_BACKEND"] = "elastic"
    e = RetrievalProxy()
    assert isinstance(e._adapter, ElasticVectorAdapter)  # type: ignore[attr-defined]


def test_other_adapters_behaviour() -> None:
    """Teste le comportement des autres adaptateurs (Pinecone/Elastic)."""
    # Pinecone/Elastic: search with empty query -> [] ; embed returns 3-dim placeholder
    p = PineconeAdapter()
    e = ElasticVectorAdapter()
    assert p.search("") == []
    assert e.search("") == []
    assert len(p.embed_texts(["x"])) == 1
    assert len(e.embed_texts(["x"])) == 1
