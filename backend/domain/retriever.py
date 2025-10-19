from __future__ import annotations

from backend.domain.retrieval_types import Document, Query, ScoredDocument
from backend.infra.vecstores.faiss_store import FAISSVectorStore


class Retriever:
    def __init__(self, store: FAISSVectorStore | None = None) -> None:
        self.store = store or FAISSVectorStore()

    def index(self, docs: list[Document]) -> int:
        return self.store.index(docs)

    def query(self, q: Query) -> list[ScoredDocument]:
        return self.store.search(q)
