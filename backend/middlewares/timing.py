"""Middleware qui mesure le temps de traitement d'une requête."""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class TimingMiddleware(BaseHTTPMiddleware):
    """Ajoute un en-tête `X-Process-Time` indiquant la durée de traitement."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Process-Time"] = f"{(time.perf_counter() - start):.4f}s"
        return response
