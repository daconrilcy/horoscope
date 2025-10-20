# ============================================================
# Module : backend/services/dual_write_ingestor.py
# Objet  : Ingestion en double écriture (FAISS + cible managée).
# Contexte : Si RETRIEVAL_DUAL_WRITE=true, chaque document est tenté sur 2 backends.
#            Les erreurs d'un backend n'empêchent pas l'autre (best-effort).
# ============================================================

from __future__ import annotations

import os
from typing import Any

import httpx
import structlog

from backend.app.metrics import RETRIEVAL_DUAL_WRITE_ERRORS
from backend.domain.retrieval_types import Document
from backend.domain.retriever import Retriever


class ManagedTargetIngest:
    """Client d'ingestion vers la cible managée (Weaviate/Pinecone – Weaviate impl. minimale).

    Pour Weaviate, crée des objets via REST `/v1/objects` avec class `Document`.
    La présence du schéma est supposée côté cible (tests utilisent des mocks).
    """

    def __init__(self, backend: str) -> None:
        self.backend = backend
        self._log = structlog.get_logger(__name__).bind(
            component="managed_target_ingest", backend=backend
        )

        if backend == "weaviate":
            self.base_url = (os.getenv("WEAVIATE_URL") or "").rstrip("/")
            api_key = os.getenv("WEAVIATE_API_KEY") or ""
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            timeout = httpx.Timeout(connect=5.0, read=5.0, write=5.0, pool=5.0)
            limits = httpx.Limits(max_keepalive_connections=20, max_connections=50)
            self._client = httpx.Client(headers=headers, timeout=timeout, limits=limits)
        else:
            self.base_url = ""
            self._client = None  # type: ignore[assignment]

    def ingest(self, docs: list[Document], tenant: str | None = None) -> int:
        if not docs:
            return 0
        if self.backend == "weaviate":
            if not self.base_url:
                # Absence de config: rien à faire
                return 0
            url = f"{self.base_url}/v1/objects"
            done = 0
            for d in docs:
                payload: dict[str, Any] = {
                    "class": "Document",
                    "properties": {"id": d.id, "text": d.text, "tenant": tenant or "default"},
                }
                try:
                    resp = self._client.post(url, json=payload)
                    if resp.status_code >= 400:
                        RETRIEVAL_DUAL_WRITE_ERRORS.labels(self.backend).inc()
                        continue
                    done += 1
                except httpx.HTTPError:
                    RETRIEVAL_DUAL_WRITE_ERRORS.labels(self.backend).inc()
                    continue
            return done
        # Pinecone/Elastic: non implémenté (simulé via tests/mocks)
        return 0


class DualWriteIngestor:
    """Ingestor best-effort: FAISS + cible managée (si configurée)."""

    def __init__(self, backend: str) -> None:
        self.backend = backend
        self.faiss_retriever = Retriever()
        self.target = ManagedTargetIngest(backend)
        self._log = structlog.get_logger(__name__).bind(
            component="dual_write_ingestor", backend=backend
        )

    def ingest(self, docs: list[Document], tenant: str | None = None) -> dict[str, int]:
        if not docs:
            return {"faiss": 0, "target": 0}
        n_faiss = self.faiss_retriever.index(docs)
        n_target = self.target.ingest(docs, tenant=tenant)
        return {"faiss": n_faiss, "target": n_target}
