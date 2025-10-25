"""Middleware pour les métriques HTTP server spécifiques à l'API Gateway.

Ce module implémente un middleware pour collecter les métriques http_server_requests_seconds_bucket
et http_server_requests_total selon les spécifications PH4.1-10.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

from backend.app.metrics import (
    HTTP_SERVER_REQUESTS_SECONDS,
    HTTP_SERVER_REQUESTS_TOTAL,
    normalize_route,
)

log = logging.getLogger(__name__)


class HTTPServerMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware pour collecter les métriques HTTP server spécifiques."""

    async def dispatch(self, request: Request, call_next: Any) -> StarletteResponse:
        """Collect HTTP server metrics for each request."""
        start_time = time.perf_counter()

        try:
            # Process request
            response = await call_next(request)
            status = str(response.status_code)
        except Exception:
            # Handle exceptions and still record metrics
            status = "500"  # Internal server error
            response = None

        # Calculate duration
        duration = time.perf_counter() - start_time

        # Normalize route and get status
        route = normalize_route(request.url.path)
        method = request.method

        # Record metrics
        HTTP_SERVER_REQUESTS_SECONDS.labels(
            route=route,
            method=method,
            status=status,
        ).observe(duration)

        HTTP_SERVER_REQUESTS_TOTAL.labels(
            route=route,
            method=method,
            status=status,
        ).inc()

        # Re-raise exception if it occurred
        if response is None:
            raise Exception("Request failed")

        return response
