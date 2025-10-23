"""Middleware Starlette pour ajouter et propager un identifiant de requête.

Ce module implémente un middleware qui ajoute l'en-tête X-Request-ID sur chaque réponse HTTP pour le
tracing et le debugging des requêtes.
"""

from collections.abc import Callable
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware pour ajouter et propager un identifiant de requête.

    Ajoute un identifiant unique à chaque requête HTTP pour faciliter le tracing et le debugging des
    requêtes dans les logs.
    """

    def __init__(self, app: ASGIApp, header_name: str = "X-Request-ID") -> None:
        """Initialise le middleware avec le nom d'en-tête spécifié.

        Args:
            app: Application ASGI à wrapper.
            header_name: Nom de l'en-tête HTTP pour l'ID de requête.
        """
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request, call_next: Callable):
        """Traite une requête en ajoutant un identifiant unique.

        Args:
            request: Requête HTTP entrante.
            call_next: Fonction pour appeler le middleware suivant.

        Returns:
            Response: Réponse HTTP avec en-tête X-Request-ID ajouté.
        """
        request_id = request.headers.get(self.header_name) or str(uuid4())
        response = await call_next(request)
        response.headers[self.header_name] = request_id
        return response
