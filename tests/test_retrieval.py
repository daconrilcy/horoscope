"""
Tests pour la récupération de documents.

Ce module teste les fonctionnalités de recherche vectorielle et de récupération de documents dans
l'application.
"""

from backend.domain.retrieval_types import Document, Query
from backend.domain.retriever import Retriever
from backend.infra.vecstores.faiss_store import FAISSVectorStore
from tests.fakes import FakeEmbeddings

# Constantes pour éviter les erreurs PLR2004 (Magic values)
EXPECTED_COUNT_2 = 2


def test_retrieval_deterministic(monkeypatch):
    """Teste que la récupération de documents est déterministe."""
    store = FAISSVectorStore()
    store.embedder = FakeEmbeddings()
    store.index([Document(id="a", text="alpha"), Document(id="b", text="beta")])
    res = store.search(Query(text="aaa", k=1))
    assert len(res) == 1


def test_retriever_init_default() -> None:
    """Teste l'initialisation du Retriever avec le store par défaut."""
    retriever = Retriever()
    assert isinstance(retriever.store, FAISSVectorStore)


def test_retriever_init_custom_store() -> None:
    """Teste l'initialisation du Retriever avec un store personnalisé."""
    custom_store = FAISSVectorStore()
    retriever = Retriever(store=custom_store)
    assert retriever.store is custom_store


def test_retriever_index() -> None:
    """Teste l'indexation de documents via Retriever."""
    retriever = Retriever()
    retriever.store.embedder = FakeEmbeddings()

    docs = [
        Document(id="doc1", text="Premier document"),
        Document(id="doc2", text="Deuxième document"),
    ]

    count = retriever.index(docs)
    assert count  == EXPECTED_COUNT_2


def test_retriever_query() -> None:
    """Teste la recherche de documents via Retriever."""
    retriever = Retriever()
    retriever.store.embedder = FakeEmbeddings()

    # Indexer des documents
    docs = [
        Document(id="doc1", text="Document sur l'astrologie"),
        Document(id="doc2", text="Document sur les étoiles"),
    ]
    retriever.index(docs)

    # Rechercher
    query = Query(text="astrologie", k=2)
    results = retriever.query(query)

    assert len(results)  == EXPECTED_COUNT_2
    assert all(isinstance(result.doc, Document) for result in results)
    assert all(hasattr(result, 'score') for result in results)


def test_retriever_query_empty() -> None:
    """Teste la recherche avec un store vide."""
    retriever = Retriever()
    retriever.store.embedder = FakeEmbeddings()

    query = Query(text="recherche", k=5)
    results = retriever.query(query)

    assert len(results) == 0


def test_retriever_index_empty_list() -> None:
    """Teste l'indexation d'une liste vide."""
    retriever = Retriever()
    retriever.store.embedder = FakeEmbeddings()

    count = retriever.index([])
    assert count == 0
