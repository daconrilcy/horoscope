"""
Métriques Prometheus pour l'application.

Ce module définit toutes les métriques Prometheus utilisées pour le monitoring de l'application
astrologique.
"""

import time

from fastapi import APIRouter, Request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

metrics_router = APIRouter()

REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "route", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "Latency of HTTP requests", ["route"]
)

# Retrieval-specific metrics
RETRIEVAL_REQUESTS = Counter(
    "retrieval_requests_total",
    "Total retrieval operations",
    ["backend", "tenant"],
)
RETRIEVAL_ERRORS = Counter(
    "retrieval_errors_total",
    "Total retrieval errors",
    ["backend", "code", "tenant"],
)
RETRIEVAL_LATENCY = Histogram(
    "retrieval_latency_seconds",
    "Latency of retrieval operations",
    ["backend", "tenant"],
)

# Migration metrics (dual-write/shadow-read)
RETRIEVAL_DUAL_WRITE_ERRORS = Counter(
    "retrieval_dual_write_errors_total",
    "Total errors when writing to migration target during dual-write",
    ["target", "tenant"],
)
RETRIEVAL_DUAL_WRITE_SKIPPED = Counter(
    "retrieval_dual_write_skipped_total",
    "Dual-write operations skipped (e.g., circuit open)",
    ["reason"],
)
RETRIEVAL_DUAL_WRITE_OUTBOX_SIZE = Gauge(
    "retrieval_dual_write_outbox_size",
    "Current size of dual-write outbox",
)
RETRIEVAL_DUAL_WRITE_OUTBOX_DROPPED = Counter(
    "retrieval_dual_write_outbox_dropped_total",
    "Outbox items dropped due to capacity limits",
)
RETRIEVAL_SHADOW_AGREEMENT_AT_5 = Histogram(
    "retrieval_shadow_agreement_at_5",
    "Agreement@5 between primary and shadow backends",
    ["backend", "k", "sample"],
    buckets=[x / 20.0 for x in range(0, 21)],  # 0.0..1.0 step 0.05
)
RETRIEVAL_SHADOW_NDCG_AT_10 = Histogram(
    "retrieval_shadow_ndcg_at_10",
    "nDCG@10 between primary and shadow backends",
    ["backend", "k", "sample"],
    buckets=[x / 20.0 for x in range(0, 21)],
)
RETRIEVAL_SHADOW_LATENCY = Histogram(
    "retrieval_shadow_latency_seconds",
    "Latency of shadow-read requests to target backend",
    ["backend", "sample"],
    buckets=[0.05, 0.1, 0.2, 0.4, 0.8, 1.2, 2.0],
)
RETRIEVAL_SHADOW_DROPPED = Counter(
    "retrieval_shadow_dropped_total",
    "Shadow-read tasks dropped",
    ["reason"],
)

# Business/chat metrics
CHAT_REQUESTS = Counter(
    "chat_requests_total",
    "Total chat advise requests",
    ["tenant", "model"],
)
CHAT_LATENCY = Histogram(
    "chat_latency_seconds",
    "Latency of chat advise",
    ["tenant", "model"],
)
LLM_TOKENS_TOTAL = Counter(
    "llm_tokens_total",
    "Accumulated LLM tokens",
    ["tenant", "model"],
)

# LLM Guard metrics
LLM_GUARD_BLOCKS = Counter(
    "llm_guard_block_total",
    "Total requests blocked by LLM Guard",
    ["rule"],
)
LLM_GUARD_WARN = Counter(
    "llm_guard_warn_total",
    "Total LLM Guard warnings (non-blocking)",
    ["rule"],
)
LLM_GUARD_PII_MASKED = Counter(
    "llm_guard_pii_masked_total",
    "Total PII masking operations performed on outputs",
    ["kind"],
)

# Retrieval hit ratio (gauge maintained by service code)
RETRIEVAL_HIT_RATIO = Gauge(
    "retrieval_hit_ratio",
    "Ratio of retrieval queries that returned at least one hit",
    ["backend", "tenant"],
)

# Retrieval hit/queries as counters to compute ratio in PromQL (robust across workers)
RETRIEVAL_QUERIES_TOTAL = Counter(
    "retrieval_queries_total",
    "Total retrieval queries",
    ["backend", "tenant"],
)
RETRIEVAL_HITS_TOTAL = Counter(
    "retrieval_hits_total",
    "Total retrieval queries that returned at least one hit",
    ["backend", "tenant"],
)

# Token counting strategy info (for debugging)
TOKEN_COUNT_STRATEGY_INFO = Gauge(
    "token_count_strategy_info",
    "Active token counting strategy for this process",
    ["strategy"],
)


def _normalize_allowed(allowed: list[str] | str | None) -> list[str]:
    """Normalize allowed values from settings (list or CSV string)."""
    if not allowed:
        return []
    if isinstance(allowed, list):
        if len(allowed) == 1 and "," in (allowed[0] or ""):
            return [s.strip() for s in allowed[0].split(",") if s.strip()]
        return [str(x).strip() for x in allowed if str(x).strip()]
    # string
    return [s.strip() for s in str(allowed).split(",") if s.strip()]


def labelize_tenant(tenant: str | None, allowed: list[str] | str | None) -> str:
    """Project tenant label through a whitelist; otherwise 'unknown'."""
    vals = set(_normalize_allowed(allowed))
    if not vals:
        return tenant or "default"
    return (tenant or "").strip() if (tenant or "").strip() in vals else "unknown"


def labelize_model(model: str | None, allowed: list[str] | str | None) -> str:
    """Project model label through a whitelist; otherwise 'unknown'."""
    vals = set(_normalize_allowed(allowed))
    if not vals:
        return model or "unknown"
    return (model or "").strip() if (model or "").strip() in vals else "unknown"


# Security/quotas metrics
RATE_LIMIT_BLOCKS = Counter(
    "rate_limit_blocks_total",
    "Total requests blocked by rate limiting",
    ["tenant", "reason"],
)

LLM_COST_USD = Counter(
    "llm_cost_usd_total",
    "Accumulated LLM cost in USD",
    ["tenant", "model"],
)

# Vector store ops
VECSTORE_INDEX = Counter(
    "vecstore_index_total",
    "Total index operations",
    ["tenant", "backend"],
)
VECSTORE_SEARCH = Counter(
    "vecstore_search_total",
    "Total search operations",
    ["tenant", "backend"],
)
VECSTORE_PURGE = Counter(
    "vecstore_purge_total",
    "Total purge operations",
    ["tenant", "backend"],
)
VECSTORE_OP_LATENCY = Histogram(
    "vecstore_op_latency_seconds",
    "Latency of vecstore operations",
    ["op", "backend"],
)


@metrics_router.get("/metrics")
def metrics():
    """
    Expose les métriques Prometheus au format texte.

    Returns:
        Response: Réponse HTTP contenant les métriques au format Prometheus.
    """
    from starlette.responses import Response  # noqa: PLC0415

    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Optional: middleware timing


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    Middleware Prometheus pour mesurer les métriques HTTP.

    Collecte les métriques de comptage des requêtes et de latence par route pour l'exposition
    Prometheus.
    """

    async def dispatch(self, request: Request, call_next):
        """
        Traite une requête HTTP et collecte les métriques.

        Args:
            request: Requête HTTP entrante.
            call_next: Fonction pour appeler le middleware suivant.

        Returns:
            Response: Réponse HTTP avec métriques collectées.
        """
        start = time.perf_counter()
        response: Response = await call_next(request)
        route = request.scope.get("path", "unknown")
        REQUEST_COUNT.labels(request.method, route, str(response.status_code)).inc()
        REQUEST_LATENCY.labels(route).observe(time.perf_counter() - start)
        return response


"""
Exposition de métriques Prometheus et middleware de mesure.

Fournit `/metrics` et un middleware optionnel pour mesurer la latence
des requêtes HTTP par route.
"""
