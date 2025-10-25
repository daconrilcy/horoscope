# ============================================================
# Module : backend/apigw/versioning.py
# Objet  : Gestion du versioning API /v1 et politique de dépréciation.
# Notes  : Force /v1, avertit routes legacy, sunset date configurée.
# ============================================================
"""Gestion du versioning API et politique de dépréciation.

Ce module fournit les fonctionnalités pour:
- Forcer le préfixe /v1 sur toutes les routes API
- Détecter et avertir les accès aux routes legacy
- Gérer la politique de dépréciation avec dates de sunset
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Request, Response
from prometheus_client import Counter
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

from backend.core.constants import HTTP_STATUS_MOVED_PERMANENTLY, HTTP_STATUS_PERMANENT_REDIRECT

log = structlog.get_logger(__name__)

# Configuration de la politique de dépréciation
SUNSET_DATE = "2025-12-31"  # Date de fin de support des routes legacy
DEPRECATION_DATE = "2025-10-24"  # Date de début de dépréciation

# Conversion des dates pour les headers RFC
SUNSET_DATETIME = datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC)
DEPRECATION_DATETIME = datetime(2025, 10, 24, 0, 0, 0, tzinfo=UTC)

# Formats pour les headers RFC
SUNSET_HTTP_DATE = SUNSET_DATETIME.strftime("%a, %d %b %Y %H:%M:%S GMT")
DEPRECATION_UNIX_TIME = f"@{int(DEPRECATION_DATETIME.timestamp())}"

# Métriques Prometheus pour l'observabilité
LEGACY_HITS_TOTAL = Counter(
    "apigw_legacy_hits_total", "Total number of hits on legacy routes", ["route", "method"]
)

REDIRECTS_TOTAL = Counter(
    "apigw_redirects_total", "Total number of redirects sent for legacy routes", ["route", "status"]
)


def create_versioned_router(prefix: str, tags: list[str] | None = None) -> APIRouter:
    """Crée un router avec le préfixe /v1 obligatoire.

    Args:
        prefix: Le préfixe de route (ex: "/auth", "/horoscope")
        tags: Tags FastAPI pour la documentation

    Returns:
        APIRouter configuré avec le préfixe /v1
    """
    full_prefix = f"/v1{prefix}"
    return APIRouter(prefix=full_prefix, tags=tags)


class LegacyDeprecationMiddleware(BaseHTTPMiddleware):
    """Middleware pour intercepter les routes legacy et retourner des warnings de dépréciation."""

    def __init__(self, app) -> None:
        """Initialise le middleware de dépréciation."""
        super().__init__(app)
        self.legacy_routes = {
            "/auth": "/v1/auth",
            "/horoscope": "/v1/horoscope",
            "/chat": "/v1/chat",
        }
        self.system_routes = ["/health", "/metrics", "/docs", "/openapi.json", "/redoc"]

    async def dispatch(self, request: Request, call_next) -> Response:
        """Dispatch les requêtes et intercepte les routes legacy."""
        path = request.url.path

        # Bypass pour les routes système
        if any(path.startswith(route) for route in self.system_routes):
            return await call_next(request)

        # Bypass pour OPTIONS/HEAD (CORS et monitoring)
        if request.method in ["OPTIONS", "HEAD"]:
            return await call_next(request)

        # Vérifier si c'est une route legacy
        for legacy_prefix, v1_prefix in self.legacy_routes.items():
            if path.startswith(legacy_prefix):
                return self._create_deprecation_response(request, legacy_prefix, v1_prefix)

        # Si ce n'est pas une route legacy, continuer normalement
        return await call_next(request)

    def _create_deprecation_response(
        self, request: Request, legacy_prefix: str, v1_prefix: str
    ) -> Response:
        """Crée une réponse de dépréciation pour une route legacy."""
        log.info(f"Legacy middleware intercepting: {legacy_prefix}")

        # Construire la nouvelle URL
        new_path = request.url.path.replace(legacy_prefix, v1_prefix, 1)
        if request.query_params:
            new_path += f"?{request.query_params}"

        # Incrémenter les métriques Prometheus
        LEGACY_HITS_TOTAL.labels(route=legacy_prefix, method=request.method).inc()

        # Log du warning
        log.warning(
            "legacy_route_access",
            legacy_path=request.url.path,
            new_path=new_path,
            client_ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent", "unknown"),
        )

        # Construire le message d'avertissement
        warning_message = (
            f"Cette route est dépréciée et sera supprimée le {SUNSET_DATE}. Utilisez {new_path}"
        )

        # Choisir le code de statut selon la méthode HTTP (RFC conform)
        # GET/HEAD → 301, POST/PUT/PATCH/DELETE → 308
        if request.method in ["GET", "HEAD"]:
            status_code = HTTP_STATUS_MOVED_PERMANENTLY
        else:
            status_code = HTTP_STATUS_PERMANENT_REDIRECT

        # Incrémenter la métrique de redirection
        REDIRECTS_TOTAL.labels(route=legacy_prefix, status=str(status_code)).inc()

        # Retourner une réponse avec warning et suggestion de redirection

        content = {
            "code": "DEPRECATED_ROUTE",
            "message": warning_message,
            "trace_id": getattr(request.state, "trace_id", "unknown"),
            "deprecation": {
                "sunset_date": SUNSET_DATE,
                "new_path": new_path,
                "warning": "Cette route sera supprimée le " + SUNSET_DATE,
            },
        }

        headers = {
            "Location": new_path,
            "Deprecation": DEPRECATION_UNIX_TIME,  # RFC 9745 : Unix time avec @
            "Sunset": SUNSET_HTTP_DATE,  # RFC 8594 : HTTP-date format
            "Link": (
                f'<{new_path}>; rel="successor-version", '
                f'<https://docs.astro.com/api/versioning>; rel="deprecation"'
            ),
            "Warning": f'299 - "Deprecated API. Use {new_path}"',
            "Content-Type": "application/json",
            "Cache-Control": "public, max-age=86400",  # Cache 24h pour réduire la charge
        }

        response = StarletteResponse(
            content=json.dumps(content), status_code=status_code, headers=headers
        )

        log.info(f"Returning deprecation response with status {response.status_code}")
        return response


def create_legacy_openapi_routes() -> APIRouter:
    """Crée des routes legacy marquées deprecated: true pour OpenAPI.

    Ces routes ne sont jamais appelées (interceptées par le middleware),
    mais permettent de documenter les routes legacy dans OpenAPI.

    Returns:
        APIRouter avec les routes legacy dépréciées
    """
    router = APIRouter()

    # Route legacy /auth/login (dépréciée)
    @router.post("/auth/login", deprecated=True, summary="[DEPRECATED] Legacy auth login")
    async def legacy_auth_login():
        """Route legacy dépréciée - utilisez /v1/auth/login."""
        pass

    # Route legacy /horoscope/natal (dépréciée)
    @router.post("/horoscope/natal", deprecated=True, summary="[DEPRECATED] Legacy horoscope natal")
    async def legacy_horoscope_natal():
        """Route legacy dépréciée - utilisez /v1/horoscope/natal."""
        pass

    # Route legacy /chat/advise (dépréciée)
    @router.post("/chat/advise", deprecated=True, summary="[DEPRECATED] Legacy chat advise")
    async def legacy_chat_advise():
        """Route legacy dépréciée - utilisez /v1/chat/advise."""
        pass

    return router


def add_versioning_middleware(app) -> None:
    """Ajoute le système de versioning à l'application FastAPI.

    Args:
        app: Instance FastAPI à configurer
    """
    # Ajouter le middleware de dépréciation des routes legacy
    # Le middleware doit être ajouté en premier pour intercepter les requêtes
    app.add_middleware(LegacyDeprecationMiddleware)

    # Ajouter les routes legacy pour OpenAPI (marquées deprecated: true)
    legacy_router = create_legacy_openapi_routes()
    app.include_router(legacy_router)
