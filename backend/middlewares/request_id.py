"""Middleware qui attache un identifiant de requête (X-Request-ID)."""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Garantit qu'un X-Request-ID est présent et propagé dans la réponse."""

    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get(HEADER) or str(uuid.uuid4())
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers[HEADER] = req_id
        return response
