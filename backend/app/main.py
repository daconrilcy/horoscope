"""Point d'entrée FastAPI et assemblage de l'application.

Objectif du module
------------------
- Créer l'application FastAPI, configurer les middlewares et enregistrer les
  routes.
"""

from api.routes_charts import router as charts_router
from api.routes_health import router as health_router
from core.container import container
from core.logging import setup_logging
from fastapi import FastAPI
from middlewares.request_id import RequestIDMiddleware
from middlewares.timing import TimingMiddleware


def create_app() -> FastAPI:
    """Assemble et retourne une instance configurée de l'application."""
    setup_logging()  # Configure structlog pour des logs lisibles et contextualisés
    settings = container.settings
    app = FastAPI(title=settings.APP_NAME, debug=settings.APP_DEBUG)
    # Middlewares transverses
    app.add_middleware(RequestIDMiddleware)  # Propage un X-Request-ID sur chaque requête
    app.add_middleware(TimingMiddleware)  # Expose le temps de traitement en en-tête
    # Enregistrement des routes
    app.include_router(health_router)
    app.include_router(charts_router)
    return app


app = create_app()
