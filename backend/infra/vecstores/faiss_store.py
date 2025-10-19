"""
FAISS-backed vector store (Faiss-only, no fallback).

Requires `faiss-cpu` and `numpy` to be installed. Uses inner-product
similarity (IndexFlatIP) for retrieval.
"""

import faiss  # type: ignore
import numpy as np  # type: ignore

from backend.core.container import container
from backend.domain.retrieval_types import Document, Query, ScoredDocument
from backend.infra.embeddings.local_embedder import LocalEmbedder
from backend.infra.embeddings.openai_embedder import OpenAIEmbedder
from backend.infra.vecstores.base import VectorStore


class FAISSVectorStore(VectorStore):
    def __init__(self) -> None:
        # choose embedder according to settings
        try:
            if getattr(container.settings, "OPENAI_API_KEY", None):
                self.embedder = OpenAIEmbedder()
            else:
                self.embedder = LocalEmbedder(
                    getattr(
                        container.settings,
                        "LOCAL_EMBEDDINGS_MODEL",
                        "all-MiniLM-L6-v2",
                    )
                )
        except Exception:
            # default to local model name if settings missing
            self.embedder = LocalEmbedder("all-MiniLM-L6-v2")

        self.index_ip: faiss.IndexFlatIP | None = None
        self.docs: list[Document] = []

    def _ensure_index(self, dim: int) -> None:
        if self.index_ip is None:
            self.index_ip = faiss.IndexFlatIP(dim)

    def index(self, docs: list[Document]) -> int:
        if not docs:
            return 0
        texts = [d.text for d in docs]
        embeddings = self.embedder.embed(texts)
        if not embeddings:
            return 0
        self._ensure_index(dim=len(embeddings[0]))
        xb = np.array(embeddings, dtype="float32")
        self.index_ip.add(xb)  # type: ignore[union-attr]
        self.docs.extend(docs)
        return len(docs)

    def search(self, q: Query) -> list[ScoredDocument]:
        if not self.docs or self.index_ip is None:
            return []
        k = max(1, min(q.k, len(self.docs)))
        query_vec = self.embedder.embed([q.text])[0]
        qx = np.array([query_vec], dtype="float32")
        distances, indices = self.index_ip.search(qx, k)  # type: ignore[union-attr]
        results: list[ScoredDocument] = []
        for score, idx in zip(distances[0], indices[0], strict=True):
            if idx == -1:
                continue
            results.append(ScoredDocument(doc=self.docs[idx], score=float(score)))
        return results
