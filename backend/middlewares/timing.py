import time
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class TimingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, header_name: str = "X-Process-Time-ms") -> None:
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request, call_next: Callable):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - start) * 1000)
        response.headers[self.header_name] = str(duration_ms)
        return response


"""
Middleware Starlette pour mesurer le temps de traitement des requêtes.

Ajoute l'en-tête `X-Process-Time-ms` avec la durée en millisecondes.
"""
