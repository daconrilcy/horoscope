from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from backend.domain.retrieval_types import Document, Query, ScoredDocument


class VectorStore(ABC):
    @abstractmethod
    def index(self, docs: list[Document]) -> int:  # returns number indexed
        raise NotImplementedError

    @abstractmethod
    def search(self, q: Query) -> list[ScoredDocument]:
        raise NotImplementedError


class VectorStoreProtocol(Protocol):
    def index_for_tenant(self, tenant: str, docs: list[Document]) -> int: ...
    def search_for_tenant(self, tenant: str, q: Query) -> list[ScoredDocument]: ...
    def purge_tenant(self, tenant: str) -> None: ...
