from backend.domain.retrieval_types import Document, Query
from backend.infra.vecstores.faiss_store import FAISSVectorStore
from backend.tests.fakes import FakeEmbeddings


def test_retrieval_deterministic(monkeypatch):
    store = FAISSVectorStore()
    store.embedder = FakeEmbeddings()
    store.index([Document(id="a", text="alpha"), Document(id="b", text="beta")])
    res = store.search(Query(text="aaa", k=1))
    assert len(res) == 1
