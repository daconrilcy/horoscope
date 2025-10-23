"""Middleware Starlette pour mesurer le temps de traitement des requêtes.

Ce module implémente un middleware qui ajoute l'en-tête X-Process-Time- ms avec la durée de
traitement en millisecondes pour le monitoring des performances.
"""

import time
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class TimingMiddleware(BaseHTTPMiddleware):
    """Middleware pour mesurer le temps de traitement des requêtes.

    Mesure la durée de traitement de chaque requête HTTP et l'ajoute comme en-tête de réponse pour
    le monitoring des performances.
    """

    def __init__(self, app: ASGIApp, header_name: str = "X-Process-Time-ms") -> None:
        """Initialise le middleware avec le nom d'en-tête spécifié.

        Args:
            app: Application ASGI à wrapper.
            header_name: Nom de l'en-tête HTTP pour le temps de traitement.
        """
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request, call_next: Callable):
        """Traite une requête en mesurant son temps de traitement.

        Args:
            request: Requête HTTP entrante.
            call_next: Fonction pour appeler le middleware suivant.

        Returns:
            Response: Réponse HTTP avec en-tête de temps de traitement ajouté.
        """
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - start) * 1000)
        response.headers[self.header_name] = str(duration_ms)
        return response
