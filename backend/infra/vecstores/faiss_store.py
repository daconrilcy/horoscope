"""
FAISS-backed vector store (Faiss-only, no fallback).

Requires `faiss-cpu` and `numpy` to be installed. Uses inner-product
similarity (IndexFlatIP) for retrieval.
"""

import getpass
import json
import os
import time

import faiss  # type: ignore
import numpy as np  # type: ignore

from backend.app.metrics import (
    VECSTORE_INDEX,
    VECSTORE_OP_LATENCY,
    VECSTORE_PURGE,
    VECSTORE_SEARCH,
)
from backend.core.container import container
from backend.domain.retrieval_types import Document, Query, ScoredDocument
from backend.domain.tenancy import safe_tenant
from backend.infra.embeddings.local_embedder import LocalEmbedder
from backend.infra.embeddings.openai_embedder import OpenAIEmbedder
from backend.infra.vecstores.base import VectorStore, VectorStoreProtocol


class FAISSVectorStore(VectorStore):
    """
    Store vectoriel FAISS pour l'indexation et la recherche.

    Implémente un store vectoriel utilisant FAISS avec support pour différents embedders (OpenAI ou
    local).
    """

    def __init__(self) -> None:
        """
        Initialise le store FAISS avec l'embedder approprié.

        Sélectionne automatiquement l'embedder selon la configuration (OpenAI si clé API disponible,
        sinon local).
        """
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
        """
        Indexe une liste de documents dans le store FAISS.

        Args:
            docs: Liste des documents à indexer.

        Returns:
            int: Nombre de documents indexés.
        """
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
        """
        Recherche des documents similaires dans le store FAISS.

        Args:
            q: Requête de recherche avec texte et nombre de résultats.

        Returns:
            list[ScoredDocument]: Liste des documents trouvés avec scores.
        """
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


class MultiTenantFAISS:
    """
    Simple multi-tenant wrapper around FAISSVectorStore.

    Maintains an isolated FAISSVectorStore per tenant, ensuring no cross-tenant visibility. Provides
    a purge method for RGPD (droit à l'oubli).
    """

    def __init__(self) -> None:
        """Initialize multi-tenant FAISS store."""
        self._stores: dict[str, FAISSVectorStore] = {}

    def _get(self, tenant: str) -> FAISSVectorStore:
        if tenant not in self._stores:
            self._stores[tenant] = FAISSVectorStore()
        return self._stores[tenant]

    def index_for_tenant(self, tenant: str, docs: list[Document]) -> int:
        """
        Indexe des documents pour un tenant spécifique.

        Args:
            tenant: Identifiant du tenant.
            docs: Liste des documents à indexer.

        Returns:
            int: Nombre de documents indexés.
        """
        return self._get(tenant).index(docs)

    def search_for_tenant(self, tenant: str, q: Query) -> list[ScoredDocument]:
        """
        Recherche des documents pour un tenant spécifique.

        Args:
            tenant: Identifiant du tenant.
            q: Requête de recherche.

        Returns:
            list[ScoredDocument]: Liste des documents trouvés avec scores.
        """
        return self._get(tenant).search(q)

    def purge_tenant(self, tenant: str) -> None:
        """
        Supprime toutes les données d'un tenant.

        Args:
            tenant: Identifiant du tenant à purger.
        """
        if tenant in self._stores:
            del self._stores[tenant]


class FaissMultiTenantAdapter(VectorStoreProtocol):
    """
    FAISS multi-tenant adapter with optional persistence per tenant.

    Persistence layout: FAISS_DATA_DIR/<tenant>/{index.faiss, docs.json}
    Uses atomic rename for snapshots. Metrics are emitted for index/search/purge.
    """

    def __init__(self, data_dir: str | None = None) -> None:
        """Initialize FAISS multi-tenant adapter with optional persistence."""
        self._mt = MultiTenantFAISS()
        self._dir = data_dir or getattr(
            container.settings, "FAISS_DATA_DIR", "./var/faiss"
        )
        os.makedirs(self._dir, exist_ok=True)

    def _paths(self, tenant: str) -> tuple[str, str]:
        tdir = os.path.join(self._dir, tenant)
        os.makedirs(tdir, exist_ok=True)
        return os.path.join(tdir, "index.faiss"), os.path.join(tdir, "docs.json")

    def _save(self, tenant: str) -> None:
        try:
            idx_path, docs_path = self._paths(tenant)
            store = self._mt._get(tenant)
            if store.index_ip is None:
                return
            tmp_idx = idx_path + ".tmp"
            faiss.write_index(store.index_ip, tmp_idx)  # type: ignore[arg-type]
            os.replace(tmp_idx, idx_path)
            tmp_docs = docs_path + ".tmp"
            with open(tmp_docs, "w", encoding="utf-8") as f:
                json.dump([d.model_dump() for d in store.docs], f)
            os.replace(tmp_docs, docs_path)
        except Exception:
            # best effort; avoid crashing app on fs issues
            pass

    def _load(self, tenant: str) -> None:
        try:
            idx_path, docs_path = self._paths(tenant)
            if os.path.exists(idx_path):
                store = self._mt._get(tenant)
                store.index_ip = faiss.read_index(idx_path)
                if os.path.exists(docs_path):
                    with open(docs_path, encoding="utf-8") as f:
                        raw = json.load(f)
                    store.docs = [Document(**d) for d in raw]
        except Exception:
            pass

    def index_for_tenant(self, tenant: str, docs: list[Document]) -> int:
        """
        Indexe des documents pour un tenant spécifique.

        Args:
            tenant: Identifiant du tenant.
            docs: Liste des documents à indexer.

        Returns:
            int: Nombre de documents indexés.
        """
        start = time.perf_counter()
        tenant = safe_tenant(
            tenant, getattr(container.settings, "DEFAULT_TENANT", "default")
        )
        n = self._mt.index_for_tenant(tenant, docs)
        self._save(tenant)
        VECSTORE_INDEX.labels(tenant=tenant, backend="faiss").inc()
        VECSTORE_OP_LATENCY.labels(op="index", backend="faiss").observe(
            time.perf_counter() - start
        )
        return n

    def search_for_tenant(self, tenant: str, q: Query) -> list[ScoredDocument]:
        """
        Recherche des documents pour un tenant spécifique.

        Args:
            tenant: Identifiant du tenant.
            q: Requête de recherche.

        Returns:
            list[ScoredDocument]: Liste des documents trouvés avec scores.
        """
        start = time.perf_counter()
        tenant = safe_tenant(
            tenant, getattr(container.settings, "DEFAULT_TENANT", "default")
        )
        # lazy load on first search
        self._load(tenant)
        res = self._mt.search_for_tenant(tenant, q)
        VECSTORE_SEARCH.labels(tenant=tenant, backend="faiss").inc()
        VECSTORE_OP_LATENCY.labels(op="search", backend="faiss").observe(
            time.perf_counter() - start
        )
        return res

    def purge_tenant(self, tenant: str) -> None:
        """
        Supprime toutes les données d'un tenant.

        Args:
            tenant: Identifiant du tenant à purger.
        """
        start = time.perf_counter()
        status = "success"
        error: str | None = None
        tenant = safe_tenant(
            tenant, getattr(container.settings, "DEFAULT_TENANT", "default")
        )
        idx_path, docs_path = self._paths(tenant)
        try:
            self._mt.purge_tenant(tenant)
            if os.path.exists(idx_path):
                os.remove(idx_path)
            if os.path.exists(docs_path):
                os.remove(docs_path)
        except Exception as exc:  # pragma: no cover - defensive
            status = "error"
            error = repr(exc)
        finally:
            VECSTORE_PURGE.labels(tenant=tenant, backend="faiss").inc()
            VECSTORE_OP_LATENCY.labels(op="purge", backend="faiss").observe(
                time.perf_counter() - start
            )
            self._audit_purge(
                tenant=tenant, backend="faiss", status=status, error=error
            )

    def _audit_purge(
        self, tenant: str, backend: str, status: str, error: str | None
    ) -> None:
        try:
            actor = os.getenv("PURGE_ACTOR") or getpass.getuser() or "service"
        except Exception:  # pragma: no cover
            actor = "service"
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        rec = {
            "ts": ts,
            "tenant": tenant,
            "actor": actor,
            "action": "purge",
            "backend": backend,
            "status": status,
            "error": error,
        }
        # rotate if >10MB best-effort
        audit_dir = os.path.join("artifacts", "audit")
        os.makedirs(audit_dir, exist_ok=True)
        path = os.path.join(audit_dir, "tenant_purge.log")
        try:
            if os.path.exists(path) and os.path.getsize(path) > 10 * 1024 * 1024:
                os.replace(path, path + ".1")
        except Exception:
            pass
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
        except Exception:
            pass
