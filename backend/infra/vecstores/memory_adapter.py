"""In-memory multi-tenant vector store adapter.

Implements VectorStoreProtocol for environments without FAISS or when a
lightweight backend is required. Provides isolation per tenant and integrates
with vecstore metrics.
"""

from __future__ import annotations

import time

from backend.app.metrics import (
    VECSTORE_INDEX,
    VECSTORE_OP_LATENCY,
    VECSTORE_PURGE,
    VECSTORE_SEARCH,
)
from backend.domain.retrieval_types import Document, Query, ScoredDocument
from backend.domain.tenancy import safe_tenant
from backend.infra.vecstores.base import VectorStoreProtocol


class MemoryMultiTenantAdapter(VectorStoreProtocol):
    """In-memory adapter with per-tenant isolation and naïve search."""

    def __init__(self) -> None:
        self._docs: dict[str, list[Document]] = {}

    def index_for_tenant(self, tenant: str, docs: list[Document]) -> int:
        start = time.perf_counter()
        tenant = safe_tenant(tenant)
        self._docs.setdefault(tenant, []).extend(docs)
        VECSTORE_INDEX.labels(tenant=tenant, backend="memory").inc()
        VECSTORE_OP_LATENCY.labels(op="index", backend="memory").observe(
            time.perf_counter() - start
        )
        return len(docs)

    def search_for_tenant(self, tenant: str, q: Query) -> list[ScoredDocument]:
        start = time.perf_counter()
        tenant = safe_tenant(tenant)
        docs = self._docs.get(tenant, [])
        if not docs:
            VECSTORE_SEARCH.labels(tenant=tenant, backend="memory").inc()
            VECSTORE_OP_LATENCY.labels(op="search", backend="memory").observe(
                time.perf_counter() - start
            )
            return []
        # naïve score: substring presence → 1.0 else ignore; return top k
        scored: list[ScoredDocument] = []
        for d in docs:
            if q.text and q.text.lower() in d.text.lower():
                scored.append(ScoredDocument(doc=d, score=1.0))
        scored.sort(key=lambda s: s.score, reverse=True)
        VECSTORE_SEARCH.labels(tenant=tenant, backend="memory").inc()
        VECSTORE_OP_LATENCY.labels(op="search", backend="memory").observe(
            time.perf_counter() - start
        )
        return scored[: max(1, q.k)]

    def purge_tenant(self, tenant: str) -> None:
        tenant = safe_tenant(tenant)
        self._docs.pop(tenant, None)
        VECSTORE_PURGE.labels(tenant=tenant, backend="memory").inc()
