from __future__ import annotations

from abc import ABC, abstractmethod

from backend.domain.retrieval_types import Document, Query, ScoredDocument


class VectorStore(ABC):
    @abstractmethod
    def index(self, docs: list[Document]) -> int:  # returns number indexed
        raise NotImplementedError

    @abstractmethod
    def search(self, q: Query) -> list[ScoredDocument]:
        raise NotImplementedError
