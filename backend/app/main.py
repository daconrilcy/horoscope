"""
Application principale FastAPI.

Ce module assemble tous les composants de l'application : middlewares,
routes, métriques et configuration de l'API astrologique.

Responsabilités du module:
- Initialiser le logging structuré
- Construire l'application FastAPI avec son titre/debug
- Ajouter les middlewares (request id, timing)
- Monter les routers (santé et horoscope)
"""

from __future__ import annotations

from fastapi import FastAPI

from backend.api.routes_auth import router as auth_router
from backend.api.routes_chat import router as chat_router
from backend.api.routes_health import router as health_router
from backend.api.routes_horoscope import router as horoscope_router
from backend.app.metrics import PrometheusMiddleware, metrics_router
from backend.app.middleware_rate_limit import RateLimitMiddleware
from backend.app.tracing import setup_tracing
from backend.core.container import container
from backend.core.logging import setup_logging
from backend.middlewares.request_id import RequestIDMiddleware
from backend.middlewares.timing import TimingMiddleware


def create_app() -> FastAPI:
    """
    Construit et retourne l'application FastAPI prête à l'usage.

    Étapes:
    - Configure le logging structuré (structlog)
    - Lit les paramètres d'exécution
    - Ajoute les middlewares utiles au debug/traçabilité
    - Publie les routes de santé et d'horoscope
    """
    setup_logging()
    setup_tracing()
    settings = container.settings
    app = FastAPI(title=settings.APP_NAME, debug=settings.APP_DEBUG)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(PrometheusMiddleware)
    app.add_middleware(TimingMiddleware)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(horoscope_router)
    app.include_router(chat_router)
    app.include_router(metrics_router)
    return app


app = create_app()
