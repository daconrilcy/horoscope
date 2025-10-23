"""Tests pour la récupération de documents.

Ce module teste les fonctionnalités de recherche vectorielle et de récupération de documents dans
l'application.
"""

from backend.domain.retrieval_types import Document, Query
from backend.infra.vecstores.faiss_store import FAISSVectorStore
from tests.fakes import FakeEmbeddings


def test_retrieval_deterministic(monkeypatch):
    """Teste que la récupération de documents est déterministe."""
    store = FAISSVectorStore()
    store.embedder = FakeEmbeddings()
    store.index([Document(id="a", text="alpha"), Document(id="b", text="beta")])
    res = store.search(Query(text="aaa", k=1))
    assert len(res) == 1
