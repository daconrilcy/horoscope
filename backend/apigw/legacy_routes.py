"""Middleware pour la gestion des routes legacy avec redirection et warning.

Ce module implémente la gestion des routes dépréciées avec redirection vers les nouvelles versions
et ajout de headers d'avertissement de dépréciation.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

from backend.apigw.errors import create_error_response

log = logging.getLogger(__name__)

# Configuration des routes legacy
LEGACY_ROUTES = {
    "/v0/chat": {
        "target": "/v1/chat/answer",
        "deprecated_since": "2025-01-01",
        "sunset_date": "2026-04-01",
        "migration_guide": "https://api.example.com/docs/migration/v0-to-v1",
        "status": "deprecated",  # deprecated, sunset
    },
    "/v0/retrieval": {
        "target": "/v1/retrieval/search",
        "deprecated_since": "2025-01-01",
        "sunset_date": "2026-04-01",
        "migration_guide": "https://api.example.com/docs/migration/v0-to-v1",
        "status": "deprecated",
    },
    "/v0/horoscope": {
        "target": "/v1/horoscope",
        "deprecated_since": "2025-01-01",
        "sunset_date": "2026-04-01",
        "migration_guide": "https://api.example.com/docs/migration/v0-to-v1",
        "status": "deprecated",
    },
}


class LegacyRouteMiddleware(BaseHTTPMiddleware):
    """Middleware pour gérer les routes legacy avec redirection et warning."""

    def __init__(self, app: Any) -> None:
        """Initialize legacy route middleware."""
        super().__init__(app)
        self.legacy_routes = LEGACY_ROUTES

    async def dispatch(self, request: Request, call_next: Any) -> StarletteResponse:
        """Handle legacy routes with redirection and deprecation warnings."""
        path = request.url.path

        # Check if this is a legacy route
        legacy_config = self._find_legacy_route(path)
        if not legacy_config:
            return await call_next(request)

        # Check if route is sunset (past sunset date)
        if self._is_sunset(legacy_config):
            return self._create_sunset_response(request, legacy_config)

        # For deprecated routes, continue processing but add deprecation headers
        response = await call_next(request)
        return self._add_deprecation_headers(response, legacy_config, request)

    def _find_legacy_route(self, path: str) -> dict[str, str] | None:
        """Find legacy route configuration for the given path."""
        # Exact match first
        if path in self.legacy_routes:
            return self.legacy_routes[path]

        # Check for path prefixes
        for legacy_path, config in self.legacy_routes.items():
            if path.startswith(legacy_path):
                return config

        return None

    def _is_sunset(self, config: dict[str, str]) -> bool:
        """Check if the route is past its sunset date."""
        sunset_date = datetime.fromisoformat(config["sunset_date"])
        return datetime.now() >= sunset_date

    def _create_sunset_response(
        self, request: Request, config: dict[str, str]
    ) -> StarletteResponse:
        """Create a 410 Gone response for sunset routes."""
        log.warning(
            "Sunset route accessed",
            extra={
                "path": request.url.path,
                "sunset_date": config["sunset_date"],
                "trace_id": getattr(request.state, "trace_id", None),
            },
        )
        response = create_error_response(
            status_code=410,
            code="SUNSET_ENDPOINT",
            message=f"This endpoint has been removed. Please use {config['target']} instead.",
            trace_id=getattr(request.state, "trace_id", None),
            details={
                "removed_since": config["sunset_date"],
                "alternative_endpoint": config["target"],
                "migration_guide": config["migration_guide"],
            },
        )
        # Avoid Retry-After for 410; set short cache to prevent sticky caches across rollbacks
        response.headers["Cache-Control"] = "max-age=60, must-revalidate"
        # Optional CDN/edge cache control
        if os.getenv("APIGW_EDGE_SURROGATE", "0").strip() in {"1", "true", "yes", "on"}:
            response.headers["Surrogate-Control"] = "max-age=60"
        return response

    def _create_deprecated_response(
        self, request: Request, config: dict[str, str]
    ) -> StarletteResponse:
        """Create a response with deprecation headers and redirect."""
        log.info(
            "Deprecated route accessed",
            extra={
                "path": request.url.path,
                "target": config["target"],
                "sunset_date": config["sunset_date"],
                "trace_id": getattr(request.state, "trace_id", None),
            },
        )

        # Create error response with deprecation information
        response = create_error_response(
            status_code=200,  # Still functional but deprecated
            code="DEPRECATED_ENDPOINT",
            message=f"This endpoint is deprecated and will be removed on {config['sunset_date']}. "
            f"Please migrate to {config['target']}",
            trace_id=getattr(request.state, "trace_id", None),
            details={
                "deprecated_since": config["deprecated_since"],
                "sunset_date": config["sunset_date"],
                "migration_guide": config["migration_guide"],
                "alternative_endpoint": config["target"],
            },
        )

        # Add deprecation headers
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = config["sunset_date"]
        response.headers["Link"] = f'<{config["migration_guide"]}>; rel="deprecation"'

    def _add_deprecation_headers(
        self, response: StarletteResponse, config: dict[str, str], request: Request
    ) -> StarletteResponse:
        """Add deprecation headers to the response."""
        log.info(
            "Deprecated route accessed",
            extra={
                "path": request.url.path,
                "target": config["target"],
                "sunset_date": config["sunset_date"],
                "trace_id": getattr(request.state, "trace_id", None),
            },
        )

        # Add deprecation headers
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = config["sunset_date"]
        response.headers["Link"] = f'<{config["migration_guide"]}>; rel="deprecation"'

        return response


def get_deprecation_status(path: str) -> dict[str, str] | None:
    """Get deprecation status for a given path."""
    middleware = LegacyRouteMiddleware(None)
    return middleware._find_legacy_route(path)


def is_route_deprecated(path: str) -> bool:
    """Check if a route is deprecated."""
    return get_deprecation_status(path) is not None


def is_route_sunset(path: str) -> bool:
    """Check if a route is sunset (past its sunset date)."""
    config = get_deprecation_status(path)
    if not config:
        return False

    middleware = LegacyRouteMiddleware(None)
    return middleware._is_sunset(config)
