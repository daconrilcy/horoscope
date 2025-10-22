from __future__ import annotations

import hashlib
import logging
import time
import uuid
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

log = logging.getLogger(__name__)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Middleware for handling idempotency keys on POST requests."""

    def __init__(self, app: Any, store: IdempotencyStore | None = None) -> None:
        super().__init__(app)
        self.store = store or InMemoryIdempotencyStore()

    async def dispatch(self, request: Request, call_next: Any) -> StarletteResponse:
        """Process request with idempotency key handling."""
        # Only handle POST requests
        if request.method != "POST":
            return await call_next(request)

        # Extract idempotency key from headers
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return await call_next(request)

        # Generate request hash for idempotency
        request_hash = self._generate_request_hash(request)

        # Check if we have a cached response
        cached_response = await self.store.get(idempotency_key, request_hash)
        if cached_response:
            log.info(
                "Returning cached idempotent response",
                extra={
                    "idempotency_key": idempotency_key,
                    "request_hash": request_hash,
                    "trace_id": getattr(request.state, "trace_id", None),
                },
            )
            return self._create_response_from_cache(cached_response)

        # Process the request
        response = await call_next(request)

        # Cache successful responses (2xx status codes)
        if 200 <= response.status_code < 300:
            await self.store.set(
                idempotency_key,
                request_hash,
                {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response.body.decode() if response.body else None,
                    "timestamp": time.time(),
                },
            )

            log.info(
                "Cached idempotent response",
                extra={
                    "idempotency_key": idempotency_key,
                    "request_hash": request_hash,
                    "status_code": response.status_code,
                    "trace_id": getattr(request.state, "trace_id", None),
                },
            )

        return response

    def _generate_request_hash(self, request: Request) -> str:
        """Generate a hash for the request to ensure idempotency."""
        # Include URL, method, and body in the hash
        content = f"{request.method}:{request.url.path}:{request.url.query}"

        # Add body if present
        if hasattr(request, "_body"):
            body = request._body
        else:
            body = b""
        content += f":{body.decode()}"

        return hashlib.sha256(content.encode()).hexdigest()

    def _create_response_from_cache(self, cached_data: dict[str, Any]) -> StarletteResponse:
        """Create a response from cached data."""
        response = StarletteResponse(
            content=cached_data.get("body", ""),
            status_code=cached_data.get("status_code", 200),
        )

        # Restore headers
        headers = cached_data.get("headers", {})
        for key, value in headers.items():
            response.headers[key] = value

        return response


class IdempotencyStore:
    """Abstract base class for idempotency key storage."""

    async def get(self, key: str, request_hash: str) -> dict[str, Any] | None:
        """Get cached response for idempotency key and request hash."""
        raise NotImplementedError

    async def set(self, key: str, request_hash: str, response_data: dict[str, Any]) -> None:
        """Cache response data for idempotency key and request hash."""
        raise NotImplementedError


class InMemoryIdempotencyStore(IdempotencyStore):
    """In-memory implementation of idempotency store."""

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._cache: dict[str, dict[str, Any]] = {}
        self._ttl_seconds = ttl_seconds

    async def get(self, key: str, request_hash: str) -> dict[str, Any] | None:
        """Get cached response from memory."""
        cache_key = f"{key}:{request_hash}"
        cached_data = self._cache.get(cache_key)

        if not cached_data:
            return None

        # Check TTL
        if time.time() - cached_data.get("timestamp", 0) > self._ttl_seconds:
            del self._cache[cache_key]
            return None

        return cached_data

    async def set(self, key: str, request_hash: str, response_data: dict[str, Any]) -> None:
        """Cache response data in memory."""
        cache_key = f"{key}:{request_hash}"
        self._cache[cache_key] = response_data


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Middleware for generating and propagating trace IDs."""

    async def dispatch(self, request: Request, call_next: Any) -> StarletteResponse:
        """Add trace ID to request state."""
        # Extract or generate trace ID
        trace_id = request.headers.get("X-Trace-ID")
        if not trace_id:
            trace_id = str(uuid.uuid4())

        # Add to request state
        request.state.trace_id = trace_id

        # Process request
        response = await call_next(request)

        # Add trace ID to response headers
        response.headers["X-Trace-ID"] = trace_id

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured request logging."""

    async def dispatch(self, request: Request, call_next: Any) -> StarletteResponse:
        """Log request and response with structured data."""
        start_time = time.time()

        # Extract trace ID
        trace_id = getattr(request.state, "trace_id", None)

        # Log request
        log.info(
            "Request started",
            extra={
                "method": request.method,
                "url": str(request.url),
                "trace_id": trace_id,
                "user_agent": request.headers.get("user-agent"),
                "content_length": request.headers.get("content-length"),
            },
        )

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time

        # Log response
        log.info(
            "Request completed",
            extra={
                "method": request.method,
                "url": str(request.url),
                "status_code": response.status_code,
                "duration": duration,
                "trace_id": trace_id,
            },
        )

        return response


class APIVersionMiddleware(BaseHTTPMiddleware):
    """Middleware for API versioning enforcement."""

    def __init__(self, app: Any, required_version: str = "v1") -> None:
        super().__init__(app)
        self.required_version = required_version

    async def dispatch(self, request: Request, call_next: Any) -> StarletteResponse:
        """Enforce API versioning."""
        path = request.url.path

        # Skip version check for health checks and docs
        if path.startswith(("/health", "/docs", "/openapi.json", "/redoc")):
            return await call_next(request)

        # Check if path starts with version
        if not path.startswith(f"/{self.required_version}/"):
            from backend.apigw.errors import create_error_response

            return create_error_response(
                status_code=400,
                code="INVALID_API_VERSION",
                message=f"API version must be {self.required_version}",
                trace_id=getattr(request.state, "trace_id", None),
            )

        return await call_next(request)
