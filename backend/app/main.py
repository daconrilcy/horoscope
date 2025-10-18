"""
Application FastAPI: assemblage des middlewares, routes et paramètres.

Responsabilités du module:
- Initialiser le logging structuré
- Construire l'application FastAPI avec son titre/debug
- Ajouter les middlewares (request id, timing)
- Monter les routers (santé et horoscope)
"""

from api.routes_health import router as health_router
from api.routes_horoscope import router as horoscope_router
from core.container import container
from core.logging import setup_logging
from fastapi import FastAPI
from middlewares.request_id import RequestIDMiddleware
from middlewares.timing import TimingMiddleware


def create_app() -> FastAPI:
    """Construit et retourne l'application FastAPI prête à l'usage.

    Étapes:
    - Configure le logging structuré (structlog)
    - Lit les paramètres d'exécution
    - Ajoute les middlewares utiles au debug/traçabilité
    - Publie les routes de santé et d'horoscope
    """
    setup_logging()
    settings = container.settings
    app = FastAPI(title=settings.APP_NAME, debug=settings.APP_DEBUG)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(TimingMiddleware)
    app.include_router(health_router)
    app.include_router(horoscope_router)
    return app


app = create_app()
