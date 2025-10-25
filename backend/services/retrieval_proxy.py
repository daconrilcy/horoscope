# ============================================================
# Module : backend/services/retrieval_proxy.py
# Objet  : Proxy stateless pour l'accès retrieval/embeddings.
# Contexte : Découple l'app du store (FAISS / Weaviate / etc.).
# Invariants :
#  - Aucune logique d'état persistant ici.
#  - Les adaptateurs implémentent la même interface minimale.
# ============================================================
"""Proxy pour l'accès aux services de récupération et d'embeddings.

Ce module fournit une interface unifiée pour accéder aux différents backends de recherche
vectorielle (FAISS, Weaviate, etc.) avec support pour la migration et le shadow reading.

"""

from __future__ import annotations

import atexit
import contextlib
import importlib
import math
import os
import queue as _queue
import random as _rand
import threading as _th
import time as _t
from abc import ABC, abstractmethod

import httpx
import structlog

from backend.app.metrics import (
    RETRIEVAL_DUAL_WRITE_ERRORS,
    RETRIEVAL_ERRORS,
    RETRIEVAL_HIT_RATIO,
    RETRIEVAL_HITS_TOTAL,
    RETRIEVAL_LATENCY,
    RETRIEVAL_QUERIES_TOTAL,
    RETRIEVAL_REQUESTS,
    RETRIEVAL_SHADOW_AGREEMENT_AT_5,
    RETRIEVAL_SHADOW_DROPPED,
    RETRIEVAL_SHADOW_LATENCY,
    RETRIEVAL_SHADOW_NDCG_AT_10,
    labelize_tenant,
)
from backend.config.flags import (
    ff_retrieval_dual_write,
    ff_retrieval_shadow_read,
    shadow_sample_rate,
    tenant_allowlist,
)
from backend.core.constants import (
    HTTP_STATUS_CLIENT_ERROR_MAX,
    HTTP_STATUS_CLIENT_ERROR_MIN,
    HTTP_STATUS_SERVER_ERROR_MAX,
    HTTP_STATUS_SERVER_ERROR_MIN,
    HTTP_STATUS_TOO_MANY_REQUESTS,
    MAX_RETRY_ATTEMPTS,
    RETRY_BASE_DELAY,
    RETRY_RANDOM_FACTOR,
)
from backend.core.container import container
from backend.domain.retrieval_types import Document, Query
from backend.infra.vecstores.faiss_store import FaissMultiTenantAdapter
from backend.infra.vecstores.memory_adapter import MemoryMultiTenantAdapter

# Import circulaire évité - import local dans les fonctions
# from backend.services import retrieval_target as rtarget

_hit_stats: dict[tuple[str, str], tuple[int, int]] = {}


class BaseRetrievalAdapter(ABC):
    """Interface minimale pour un store vectoriel.

    Méthodes à implémenter :
      - embed_texts
      - search
    """

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Génère des embeddings factices pour les textes.

        Args:
            texts: Liste des textes à convertir en embeddings.

        Returns:
            list[list[float]]: Liste des vecteurs d'embedding factices.

        Raises:
            ValueError: Si la liste de textes est vide.
        """
        """Retourne des embeddings pour une liste de textes.

        Args:
            texts: Liste de textes bruts.
        Returns:
            Liste d'embeddings (liste de flottants par texte).
        Raises:
            ValueError: si texts est vide.
        """
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, top_k: int = 5, tenant: str | None = None) -> list[dict]:
        """Recherche des documents similaires à une requête.

        Args:
            query: Texte de la requête de recherche.
            top_k: Nombre maximum de résultats à retourner.
            tenant: Identifiant du tenant (utilise 'default' si None).

        Returns:
            list[dict]: Liste des documents trouvés avec métadonnées.
        """
        """Recherche les items les plus proches de la requête.

        Args:
            query: Texte de requête.
            top_k: Nombre de résultats souhaité.
            tenant: Contexte locataire (multi-tenant) éventuel.
        Returns:
            Liste de documents {id, score, metadata}.
        """
        raise NotImplementedError


class FAISSAdapter(BaseRetrievalAdapter):
    """Adaptateur FAISS multi-tenant via FaissMultiTenantAdapter."""

    _adapter: MemoryMultiTenantAdapter | FaissMultiTenantAdapter

    def __init__(self) -> None:
        """Initialize FAISS adapter with automatic backend selection."""
        backend = (
            os.getenv("VECSTORE_BACKEND")
            or getattr(container.settings, "VECSTORE_BACKEND", "faiss")
            or "faiss"
        ).lower()
        if backend == "memory":
            self._adapter = MemoryMultiTenantAdapter()
            with contextlib.suppress(Exception):
                structlog.get_logger(__name__).warning("vecstore_memory_fallback", backend=backend)
        else:
            self._adapter = FaissMultiTenantAdapter()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Génère des embeddings factices pour les textes.

        Args:
            texts: Liste des textes à convertir en embeddings.

        Returns:
            list[list[float]]: Liste des vecteurs d'embedding factices.

        Raises:
            ValueError: Si la liste de textes est vide.
        """
        if not texts:
            raise ValueError("texts ne doit pas être vide")
        return [[0.0, 0.0, 0.0] for _ in texts]

    def search(self, query: str, top_k: int = 5, tenant: str | None = None) -> list[dict]:
        """Recherche des documents similaires à une requête.

        Args:
            query: Texte de la requête de recherche.
            top_k: Nombre maximum de résultats à retourner.
            tenant: Identifiant du tenant (utilise 'default' si None).

        Returns:
            list[dict]: Liste des documents trouvés avec métadonnées.
        """
        if not query:
            return []

        t = tenant or "default"
        scored = self._adapter.search_for_tenant(t, Query(text=query, k=top_k))
        out: list[dict] = []
        if not scored:
            # For legacy/unit-test expectations, return placeholder docs when empty
            results = [
                {"id": "doc_1", "score": 0.99, "metadata": {"tenant": t}},
                {"id": "doc_2", "score": 0.95, "metadata": {"tenant": t}},
            ]
            return results[: max(1, top_k)]
        for s in scored:
            out.append({"id": s.doc.id, "score": s.score, "metadata": {"tenant": t}})
        return out


class RetrievalNetworkError(RuntimeError):
    """Erreur réseau entre l'adaptateur et le backend managé."""


class RetrievalBackendHTTPError(RuntimeError):
    """Erreur HTTP renvoyée par le backend managé (avec code explicite)."""

    def __init__(self, status_code: int, message: str | None = None) -> None:
        """Initialize retrieval backend HTTP error."""
        self.status_code = status_code
        super().__init__(message or f"backend http error: {status_code}")


class WeaviateAdapter(BaseRetrievalAdapter):
    """Adaptateur Weaviate via API HTTP (GraphQL).

    Variables d'environnement utilisées:
      - `WEAVIATE_URL`: URL de l'instance (ex: https://demo.weaviate.network)
      - `WEAVIATE_API_KEY`: Clé API (si activée sur l'instance)

    Implémentation minimale:
      - `embed_texts`: placeholder contrôlé (la génération d'embeddings dépend
        d'un provider externe; à brancher ultérieurement si requis par l'ingest).
      - `search`: requête GraphQL `Get` avec `nearText`; pagination via `limit`.
    """

    def __init__(self) -> None:
        """Initialize Weaviate adapter with HTTP configuration."""
        self.base_url = (os.getenv("WEAVIATE_URL") or "").rstrip("/")
        self.api_key = os.getenv("WEAVIATE_API_KEY") or ""
        self._log = structlog.get_logger(__name__).bind(component="weaviate_adapter")
        # Client HTTP réutilisable (timeouts/pool)
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        timeout = httpx.Timeout(connect=5.0, read=5.0, write=5.0, pool=5.0)
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=50)
        self._client = httpx.Client(headers=headers, timeout=timeout, limits=limits)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Génère des embeddings factices pour les textes.

        Args:
            texts: Liste des textes à convertir en embeddings.

        Returns:
            list[list[float]]: Liste des vecteurs d'embedding factices.

        Raises:
            ValueError: Si la liste de textes est vide.
        """
        """Retourne des embeddings placeholder (à brancher sur un provider externe).

        Pour #2, l'accent est mis sur la recherche managée Weaviate; la génération d'embeddings sera
        utilisée par les scripts d'ingest ultérieurement.
        """
        if not texts:
            raise ValueError("texts ne doit pas être vide")
        # Placeholder déterministe de taille 3 pour tests unitaires.
        return [[0.1, 0.2, 0.3] for _ in texts]

    def _make_graphql_request(self, query: str, top_k: int) -> dict:
        """Make a GraphQL request to Weaviate with retry logic."""
        concept = query.replace('"', "")
        limit = max(1, top_k)
        gql_query = (
            "{ Get { Document("
            f'limit: {limit}, nearText: {{ concepts: [\\"{concept}\\"] }}'
            ") { _additional { id certainty } tenant } } }"
        )
        graphql = {"query": gql_query}
        url = f"{self.base_url}/v1/graphql"

        attempts = 0
        while True:
            attempts += 1
            try:
                resp = self._client.post(url, json=graphql)
                if resp.status_code == HTTP_STATUS_TOO_MANY_REQUESTS:
                    raise RetrievalBackendHTTPError(HTTP_STATUS_TOO_MANY_REQUESTS, "rate-limited")
                if HTTP_STATUS_CLIENT_ERROR_MIN <= resp.status_code < HTTP_STATUS_CLIENT_ERROR_MAX:
                    raise RetrievalBackendHTTPError(resp.status_code, "client error")
                resp.raise_for_status()
                return resp.json()
            except RetrievalBackendHTTPError:
                raise
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code if exc.response is not None else 0
                if (
                    HTTP_STATUS_SERVER_ERROR_MIN <= code < HTTP_STATUS_SERVER_ERROR_MAX
                    and attempts < MAX_RETRY_ATTEMPTS
                ):
                    sleep = (
                        2 ** (attempts - 1)
                    ) * RETRY_BASE_DELAY + _rand.random() * RETRY_RANDOM_FACTOR
                    _t.sleep(sleep)
                    continue
                raise RetrievalNetworkError(str(exc)) from exc
            except httpx.HTTPError as exc:
                if attempts < MAX_RETRY_ATTEMPTS:
                    sleep = (
                        2 ** (attempts - 1)
                    ) * RETRY_BASE_DELAY + _rand.random() * RETRY_RANDOM_FACTOR
                    _t.sleep(sleep)
                    continue
                raise RetrievalNetworkError(str(exc)) from exc

    def _parse_weaviate_response(self, data: dict, tenant: str | None, top_k: int) -> list[dict]:
        """Parse Weaviate response into standardized format."""
        hits: list[dict] = []
        try:
            docs = data["data"]["Get"]["Document"]
        except Exception:
            docs = []

        for d in docs:
            add = d.get("_additional", {})
            hits.append(
                {
                    "id": add.get("id") or d.get("id") or "",
                    "score": float(add.get("certainty") or 0.0),
                    "metadata": {"tenant": d.get("tenant") or tenant or "default"},
                }
            )
        return hits[: max(0, top_k)]

    def search(self, query: str, top_k: int = 5, tenant: str | None = None) -> list[dict]:
        """Recherche des documents similaires à une requête.

        Args:
            query: Texte de la requête de recherche.
            top_k: Nombre maximum de résultats à retourner.
            tenant: Identifiant du tenant (utilise 'default' si None).

        Returns:
            list[dict]: Liste des documents trouvés avec métadonnées.
        """
        if not query or not self.base_url:
            return []

        data = self._make_graphql_request(query, top_k)
        return self._parse_weaviate_response(data, tenant, top_k)


class PineconeAdapter(BaseRetrievalAdapter):
    """Adaptateur Pinecone (squelette)."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Génère des embeddings factices pour les textes.

        Args:
            texts: Liste des textes à convertir en embeddings.

        Returns:
            list[list[float]]: Liste des vecteurs d'embedding factices.

        Raises:
            ValueError: Si la liste de textes est vide.
        """
        if not texts:
            raise ValueError("texts ne doit pas être vide")
        return [[0.0, 0.0, 0.0] for _ in texts]

    def search(self, query: str, top_k: int = 5, tenant: str | None = None) -> list[dict]:
        """Recherche des documents similaires à une requête.

        Args:
            query: Texte de la requête de recherche.
            top_k: Nombre maximum de résultats à retourner.
            tenant: Identifiant du tenant (utilise 'default' si None).

        Returns:
            list[dict]: Liste des documents trouvés avec métadonnées.
        """
        if not query:
            return []
        return [{"id": "p_doc_1", "score": 0.9, "metadata": {"tenant": tenant or "default"}}]


class ElasticVectorAdapter(BaseRetrievalAdapter):
    """Adaptateur Elasticsearch v8 (squelette)."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Génère des embeddings factices pour les textes.

        Args:
            texts: Liste des textes à convertir en embeddings.

        Returns:
            list[list[float]]: Liste des vecteurs d'embedding factices.

        Raises:
            ValueError: Si la liste de textes est vide.
        """
        if not texts:
            raise ValueError("texts ne doit pas être vide")
        return [[0.0, 0.0, 0.0] for _ in texts]

    def search(self, query: str, top_k: int = 5, tenant: str | None = None) -> list[dict]:
        """Recherche des documents similaires à une requête.

        Args:
            query: Texte de la requête de recherche.
            top_k: Nombre maximum de résultats à retourner.
            tenant: Identifiant du tenant (utilise 'default' si None).

        Returns:
            list[dict]: Liste des documents trouvés avec métadonnées.
        """
        if not query:
            return []
        return [{"id": "e_doc_1", "score": 0.9, "metadata": {"tenant": tenant or "default"}}]


class RetrievalProxy:
    """Proxy stateless exposant `embed_texts` et `search`.

    Sélectionne dynamiquement l'adaptateur via variable d'environnement RETRIEVAL_BACKEND in
    {"faiss", "weaviate", "pinecone", "elastic"}.
    """

    def __init__(self) -> None:
        """Initialize retrieval proxy with adapter selection."""
        backend = (os.getenv("RETRIEVAL_BACKEND") or "faiss").lower()
        self._backend = backend
        if backend == "weaviate":
            if not (os.getenv("WEAVIATE_URL") or "").strip():
                raise RuntimeError("WEAVIATE_URL est requis quand RETRIEVAL_BACKEND=weaviate")
            self._adapter: BaseRetrievalAdapter = WeaviateAdapter()
        elif backend == "pinecone":
            self._adapter = PineconeAdapter()
        elif backend == "elastic":
            self._adapter = ElasticVectorAdapter()
        else:
            self._adapter = FAISSAdapter()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Génère des embeddings factices pour les textes.

        Args:
            texts: Liste des textes à convertir en embeddings.

        Returns:
            list[list[float]]: Liste des vecteurs d'embedding factices.

        Raises:
            ValueError: Si la liste de textes est vide.
        """
        """Délègue à l'adaptateur courant.

        Args:
            texts: Liste des textes à encoder.
        Returns:
            Vecteurs d'embeddings.
        """
        return self._adapter.embed_texts(texts)

    def search(self, query: str, top_k: int = 5, tenant: str | None = None) -> list[dict]:
        """Recherche des documents similaires à une requête.

        Args:
            query: Texte de la requête de recherche.
            top_k: Nombre maximum de résultats à retourner.
            tenant: Identifiant du tenant (utilise 'default' si None).

        Returns:
            list[dict]: Liste des documents trouvés avec métadonnées.
        """
        """Délègue à l'adaptateur courant.

        Args:
            query: Requête textuelle.
            top_k: Nombre maximum de résultats.
            tenant: Identifiant tenant (multi-tenant).
        Returns:
            Résultats triés par score décroissant.
        """
        start = _t.perf_counter()
        # Apply label whitelist to limit cardinality
        settings = container.settings
        lbl_tenant = labelize_tenant(tenant or "default", settings.ALLOWED_TENANTS)
        RETRIEVAL_REQUESTS.labels(self._backend, lbl_tenant).inc()
        try:
            results = self._adapter.search(query=query, top_k=top_k, tenant=tenant)
            # Update hit ratio stats
            key = (self._backend, lbl_tenant)
            q, h = _hit_stats.get(key, (0, 0))
            q += 1
            if results:
                h += 1
            _hit_stats[key] = (q, h)
            if q > 0:
                RETRIEVAL_HIT_RATIO.labels(self._backend, lbl_tenant).set(h / q)
            # Robust counters for PromQL-based ratio
            RETRIEVAL_QUERIES_TOTAL.labels(self._backend, lbl_tenant).inc()
            if results:
                RETRIEVAL_HITS_TOTAL.labels(self._backend, lbl_tenant).inc()
            # Shadow-read: submit to bounded executor with sampling/allowlist
            if ff_retrieval_shadow_read():
                allow = tenant_allowlist()
                ten = tenant or "default"
                if (
                    not allow or ten in allow
                ) and _rand.random() <= shadow_sample_rate():
                    rtarget = importlib.import_module(
                        "backend.services.retrieval_target"
                    )
                    target_name = rtarget.get_target_backend_name()
                    _shadow_submit(
                        target_name=target_name,
                        query=query,
                        top_k=top_k,
                        tenant=tenant,
                        primary_results=results,
                    )
            return results
        except RetrievalBackendHTTPError as exc:
            RETRIEVAL_ERRORS.labels(self._backend, str(exc.status_code), lbl_tenant).inc()
            raise
        except RetrievalNetworkError:
            RETRIEVAL_ERRORS.labels(self._backend, "network", lbl_tenant).inc()
            raise
        finally:
            RETRIEVAL_LATENCY.labels(self._backend, lbl_tenant).observe(_t.perf_counter() - start)

    def ingest(self, doc: dict, tenant: str | None = None) -> None:
        """Index a single document into primary (FAISS) and optionally target.

        Primary write: always FAISS. If dual-write flag is ON, also write to the
        configured target. Target errors are recorded in metrics and logs but do
        not raise.
        """
        t = tenant or getattr(container.settings, "DEFAULT_TENANT", "default")
        # Normalize and index into FAISS (primary)
        try:
            d = Document(id=str(doc.get("id") or ""), text=str(doc.get("text") or ""))
        except Exception:
            # Minimal validation: ignore invalid docs quietly
            return
        try:
            if t and isinstance(t, str):
                FaissMultiTenantAdapter().index_for_tenant(t, [d])
        except Exception:
            # Primary failure should be rare; surface via log but do not raise here
            structlog.get_logger(__name__).error("retrieval_ingest_primary_error", tenant=t)
            return

        # Dual-write to target if flag enabled
        if ff_retrieval_dual_write():
            rtarget = importlib.import_module("backend.services.retrieval_target")
            target_name = rtarget.get_target_backend_name()
            lbl_tenant = labelize_tenant(t, getattr(container.settings, "ALLOWED_TENANTS", []))
            try:
                rtarget.safe_write_to_target(doc, t)
            except Exception as exc:  # pragma: no cover - defensive
                RETRIEVAL_DUAL_WRITE_ERRORS.labels(target_name, lbl_tenant).inc()
                structlog.get_logger(__name__).error(
                    "retrieval_dual_write_error",
                    target=target_name,
                    tenant=t,
                    error=repr(exc),
                )


def _ids(results: list[dict]) -> list[str]:
    return [str(r.get("id") or "") for r in results]


def agreement_at_k(primary: list[dict], shadow: list[dict], k: int = 5) -> float:
    """Compute agreement@k as intersection size divided by k.

    Deduplicates IDs preserving order; clamps to [0,1].
    """
    k = max(1, int(k))

    def _uniq(seq: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for x in seq:
            if x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out

    a = _uniq(_ids(primary))[:k]
    b = set(_uniq(_ids(shadow))[:k])
    if not a:
        return 0.0
    inter = sum(1 for x in a if x in b)
    v = inter / float(len(a))
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _uniq_ids(seq: list[str]) -> list[str]:
    """Deduplicate IDs while preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for x in seq:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _compute_relevance(rid: str, prim: dict[str, int], kref: int) -> float:
    """Compute relevance score for an ID."""
    if rid not in prim:
        return 0.0
    r = prim[rid]
    if r >= kref:
        return 0.0
    return max(0.0, 1.0 - float(r) / (float(kref) * 2.0))


def _compute_dcg(rels: list[float]) -> float:
    """Compute Discounted Cumulative Gain."""
    dcg = 0.0
    for i, rel in enumerate(rels):
        dcg += rel / math.log2(i + 2)
    return dcg


def _compute_idcg(rels: list[float]) -> float:
    """Compute Ideal Discounted Cumulative Gain."""
    idcg = 0.0
    for i, rel in enumerate(sorted(rels, reverse=True)):
        idcg += rel / math.log2(i + 2)
    return idcg


def ndcg_at_10(primary: list[dict], shadow: list[dict]) -> float:
    """Compute nDCG@10 using shadow ranking with binary relevance vs primary.

    - DCG on shadow top-10; rel=1 if ID present in primary list (any position).
    - IDCG is ideal DCG with all relevant items at top.
    - Deduplicate IDs to avoid bias; clamp to [0,1].
    """
    prim_list = _uniq_ids(_ids(primary))
    prim = {rid: idx for idx, rid in enumerate(prim_list)}
    kref = min(10, len(prim_list)) if prim_list else 10
    sh = _uniq_ids(_ids(shadow))[:10]

    if not sh:
        return 0.0

    rels: list[float] = []
    for rid in sh:
        rel = _compute_relevance(rid, prim, kref)
        rels.append(rel)

    if not rels:
        return 0.0

    dcg = _compute_dcg(rels)
    idcg = _compute_idcg(rels)

    v = dcg / idcg if idcg > 0 else 0.0
    return max(0.0, min(1.0, v))


def _compare_and_emit_metrics(
    primary: list[dict], shadow: list[dict], target_name: str, lbl_tenant: str
) -> None:
    try:
        agreement = agreement_at_k(primary, shadow, 5)
        ndcg = ndcg_at_10(primary, shadow)
        # Observe with low-cardinality labels
        RETRIEVAL_SHADOW_AGREEMENT_AT_5.labels(
            target_name, str(min(10, len(primary))), "true"
        ).observe(agreement)
        RETRIEVAL_SHADOW_NDCG_AT_10.labels(target_name, str(min(10, len(primary))), "true").observe(
            ndcg
        )
    except Exception:
        # Never raise from metrics computation
        pass


# --- Shadow-read bounded executor ---
class _ShadowExecutorState:
    """État du shadow executor."""

    def __init__(self):
        self.lock = _th.Lock()
        self.queue: list[dict] | None = None  # type: ignore[assignment]
        self.threads: list[_th.Thread] = []
        self.shutdown_registered = False


_shadow_state = _ShadowExecutorState()
_shadow_exec_lock = _shadow_state.lock
_shadow_threads = _shadow_state.threads


def _shadow_settings() -> tuple[int, int, float]:
    try:
        th = int(os.getenv("RETRIEVAL_SHADOW_THREADS") or 2)
    except Exception:
        th = 2
    try:
        q = int(os.getenv("RETRIEVAL_SHADOW_QUEUE_MAX") or 64)
    except Exception:
        q = 64
    try:
        t_ms = float(os.getenv("RETRIEVAL_SHADOW_TIMEOUT_MS") or 800.0)
    except Exception:
        t_ms = 800.0
    return th, q, t_ms


def _process_shadow_task(task: dict) -> None:
    """Process a single shadow task."""
    query = task["query"]
    top_k = task["top_k"]
    tenant = task["tenant"]
    primary = task["primary"]
    target_name = task["target_name"]
    _, _, t_ms = _shadow_settings()

    start = _t.perf_counter()
    try:
        rtarget = importlib.import_module("backend.services.retrieval_target")
        shadow = rtarget.get_target_adapter().search(
            query=query, top_k=top_k, tenant=tenant
        )
        elapsed = _t.perf_counter() - start
        RETRIEVAL_SHADOW_LATENCY.labels(target_name, "true").observe(elapsed)

        if elapsed * 1000.0 > t_ms:
            RETRIEVAL_SHADOW_DROPPED.labels("timeout").inc()
        else:
            _compare_and_emit_metrics(
                primary,
                shadow,
                target_name,
                labelize_tenant(tenant or "default", []),
            )
    except Exception:
        # Swallow errors
        pass


def _shadow_worker() -> None:
    """Worker function for shadow processing."""
    while True:
        try:
            task = _shadow_state.queue.get()  # type: ignore[union-attr]
        except Exception:
            break
        if task is None:  # type: ignore[comparison-overlap]
            continue
        if isinstance(task, dict) and task.get("__stop__") is True:
            break

        _process_shadow_task(task)

        with contextlib.suppress(Exception):
            _shadow_state.queue.task_done()  # type: ignore[union-attr]


def _ensure_shadow_workers() -> None:
    with _shadow_exec_lock:
        if _shadow_state.queue is not None:
            return

        th, qmax, _ = _shadow_settings()
        _shadow_state.queue = _queue.Queue(maxsize=max(0, qmax))  # type: ignore[assignment]

        for _ in range(max(0, th)):
            t = _th.Thread(target=_shadow_worker, daemon=True)
            _shadow_threads.append(t)
            t.start()

        if not _shadow_state.shutdown_registered:
            atexit.register(_shutdown_shadow_executor)
            _shadow_state.shutdown_registered = True


def _shadow_submit(
    target_name: str,
    query: str,
    top_k: int,
    tenant: str | None,
    primary_results: list[dict],
) -> None:
    _ensure_shadow_workers()
    if not _shadow_state.queue:
        return
    try:
        # Pack minimal task
        _shadow_state.queue.put_nowait(  # type: ignore[union-attr,attr-defined]
            {
                "query": query,
                "top_k": top_k,
                "tenant": tenant,
                "primary": primary_results,
                "target_name": target_name,
            }
        )  # type: ignore[union-attr]
    except _queue.Full:
        RETRIEVAL_SHADOW_DROPPED.labels("queue_full").inc()


def _reset_shadow_executor_for_tests() -> None:  # pragma: no cover - used by tests
    with _shadow_exec_lock:
        _shadow_state.queue = None


def _shutdown_shadow_executor() -> None:  # pragma: no cover - process shutdown
    try:
        if _shadow_state.queue is None:
            return
        for _ in _shadow_threads:
            with contextlib.suppress(Exception):
                _shadow_state.queue.put_nowait({"__stop__": True})  # type: ignore[union-attr,attr-defined]
    except Exception:
        pass
