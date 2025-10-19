
from __future__ import annotations

from backend.core.container import container
from backend.domain.retrieval_types import Document, Query, ScoredDocument
from backend.infra.embeddings.local_embedder import LocalEmbedder
from backend.infra.embeddings.openai_embedder import OpenAIEmbedder
from backend.infra.vecstores.base import VectorStore


class FAISSVectorStore(VectorStore):
    def __init__(self) -> None:
        # choose embedder according to settings when available
        try:
            if getattr(container.settings, 'OPENAI_API_KEY', None):
                self.embedder = OpenAIEmbedder()
            else:
                self.embedder = LocalEmbedder(getattr(container.settings, 'LOCAL_EMBEDDINGS_MODEL', 'mini'))  # noqa: E501
        except Exception:
            # fallback to local
            self.embedder = LocalEmbedder('mini')
        self._vecs: list[list[float]] = []
        self.docs: list[Document] = []

    def index(self, docs: list[Document]) -> int:
        texts = [d.text for d in docs]
        embs = self.embedder.embed(texts)
        self._vecs.extend(embs)
        self.docs.extend(docs)
        return len(docs)

    def search(self, q: Query) -> list[ScoredDocument]:
        qv = self.embedder.embed([q.text])[0]
        k = max(1, min(q.k, len(self.docs)))
        if not self._vecs:
            return []
        # simple L2 distance
        def l2(a: list[float], b: list[float]) -> float:
            return sum((x - y) * (x - y) for x, y in zip(a, b, strict=False)) ** 0.5

        scored = [(i, l2(vec, qv)) for i, vec in enumerate(self._vecs)]
        scored.sort(key=lambda t: t[1])
        top = scored[:k]
        return [ScoredDocument(doc=self.docs[i], score=float(-dist)) for i, dist in top]
