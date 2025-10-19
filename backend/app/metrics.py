import time

from fastapi import APIRouter, Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

metrics_router = APIRouter()

REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "route", "status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "Latency of HTTP requests", ["route"])

# Retrieval-specific metrics
RETRIEVAL_REQUESTS = Counter(
    "retrieval_requests_total",
    "Total retrieval operations",
    ["backend", "tenant"],
)
RETRIEVAL_ERRORS = Counter(
    "retrieval_errors_total",
    "Total retrieval errors",
    ["backend", "code"],
)
RETRIEVAL_LATENCY = Histogram(
    "retrieval_latency_seconds",
    "Latency of retrieval operations",
    ["backend"],
)


@metrics_router.get("/metrics")
def metrics():
    from starlette.responses import Response  # local import to avoid cycle

    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Optional: middleware timing


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
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
