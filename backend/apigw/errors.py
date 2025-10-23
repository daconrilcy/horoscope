"""Gestion standardisée des erreurs API avec enveloppes d'erreur.

Ce module fournit une gestion centralisée des erreurs avec des enveloppes standardisées, des codes
d'erreur cohérents et un support pour le tracing des requêtes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)


@dataclass
class ErrorEnvelope:
    """Standard error envelope for API responses."""

    code: str
    message: str
    trace_id: str | None = None
    details: dict[str, Any] | None = None


class APIError(HTTPException):
    """Custom API error with standard envelope."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        trace_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize an API error with standardized envelope."""
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message
        self.trace_id = trace_id
        self.details = details


def create_error_response(
    status_code: int,
    code: str,
    message: str,
    trace_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Create a standardized error response."""
    envelope = ErrorEnvelope(
        code=code,
        message=message,
        trace_id=trace_id,
        details=details,
    )

    return JSONResponse(
        status_code=status_code,
        content={
            "code": envelope.code,
            "message": envelope.message,
            "trace_id": envelope.trace_id,
            **({"details": envelope.details} if envelope.details else {}),
        },
    )


def extract_trace_id(request: Request) -> str | None:
    """Extract trace ID from request headers or generate one."""
    # Check for trace ID in headers
    trace_id = request.headers.get("X-Trace-ID")
    if trace_id:
        return trace_id

    # Check for trace ID in request state (set by middleware)
    if hasattr(request.state, "trace_id"):
        return request.state.trace_id

    return None


def handle_api_error(request: Request, exc: APIError) -> JSONResponse:
    """Handle APIError exceptions with standard envelope."""
    trace_id = extract_trace_id(request) or exc.trace_id

    log.error(
        "API error occurred",
        extra={
            "code": exc.code,
            "error_message": exc.message,
            "status_code": exc.status_code,
            "trace_id": trace_id,
            "details": exc.details,
        },
    )

    return create_error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        trace_id=trace_id,
        details=exc.details,
    )


def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTPException with standard envelope."""
    trace_id = extract_trace_id(request)

    # Map common HTTP status codes to error codes
    error_codes = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
        504: "GATEWAY_TIMEOUT",
    }

    code = error_codes.get(exc.status_code, "HTTP_ERROR")

    log.error(
        "HTTP exception occurred",
        extra={
            "code": code,
            "error_message": str(exc.detail),
            "status_code": exc.status_code,
            "trace_id": trace_id,
        },
    )

    return create_error_response(
        status_code=exc.status_code,
        code=code,
        message=str(exc.detail),
        trace_id=trace_id,
    )


def handle_generic_exception(request: Request, exc: Exception) -> JSONResponse:
    """Handle generic exceptions with standard envelope."""
    trace_id = extract_trace_id(request)

    log.error(
        "Unexpected error occurred",
        extra={
            "code": "INTERNAL_ERROR",
            "error_message": "An unexpected error occurred",
            "trace_id": trace_id,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
        },
        exc_info=True,
    )

    return create_error_response(
        status_code=500,
        code="INTERNAL_ERROR",
        message="An unexpected error occurred",
        trace_id=trace_id,
    )


# Common error codes
class ErrorCodes:
    """Standard error codes for the API."""

    # Client errors (4xx)
    BAD_REQUEST = "BAD_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    CONFLICT = "CONFLICT"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"

    # Server errors (5xx)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    BAD_GATEWAY = "BAD_GATEWAY"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    GATEWAY_TIMEOUT = "GATEWAY_TIMEOUT"

    # Business logic errors
    INVALID_TENANT = "INVALID_TENANT"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    IDEMPOTENCY_KEY_CONFLICT = "IDEMPOTENCY_KEY_CONFLICT"


# Convenience functions for common errors
def bad_request(
    message: str, trace_id: str | None = None, details: dict[str, Any] | None = None
) -> APIError:
    """Create a 400 Bad Request error."""
    return APIError(400, ErrorCodes.BAD_REQUEST, message, trace_id, details)


def unauthorized(message: str, trace_id: str | None = None) -> APIError:
    """Create a 401 Unauthorized error."""
    return APIError(401, ErrorCodes.UNAUTHORIZED, message, trace_id)


def forbidden(message: str, trace_id: str | None = None) -> APIError:
    """Create a 403 Forbidden error."""
    return APIError(403, ErrorCodes.FORBIDDEN, message, trace_id)


def not_found(message: str, trace_id: str | None = None) -> APIError:
    """Create a 404 Not Found error."""
    return APIError(404, ErrorCodes.NOT_FOUND, message, trace_id)


def conflict(
    message: str, trace_id: str | None = None, details: dict[str, Any] | None = None
) -> APIError:
    """Create a 409 Conflict error."""
    return APIError(409, ErrorCodes.CONFLICT, message, trace_id, details)


def rate_limited(
    message: str, trace_id: str | None = None, retry_after: int | None = None
) -> APIError:
    """Create a 429 Rate Limited error."""
    details = {"retry_after": retry_after} if retry_after else None
    return APIError(429, ErrorCodes.RATE_LIMITED, message, trace_id, details)


def internal_error(message: str, trace_id: str | None = None) -> APIError:
    """Create a 500 Internal Server Error."""
    return APIError(500, ErrorCodes.INTERNAL_ERROR, message, trace_id)
