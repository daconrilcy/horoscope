"""Configurer les timeouts et le backoff au gateway.

Ce module définit des timeouts cohérents et des stratégies de retry avec backoff ainsi qu'un
retry-budget par endpoint pour l'API Gateway, selon les spécifications PH4.1-12.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

from backend.apigw.errors import create_error_response
from backend.app.metrics import (
    APIGW_RETRY_ATTEMPTS_TOTAL,
    APIGW_RETRY_BUDGET_EXHAUSTED_TOTAL,
    normalize_route,
)
from backend.core.constants import HTTP_STATUS_SERVER_ERROR_MIN

log = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Stratégies de retry disponibles."""

    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"


@dataclass
class TimeoutConfig:
    """Configuration des timeouts par endpoint."""

    # Timeouts en secondes
    read_timeout: float = 3.0
    write_timeout: float = 5.0
    connect_timeout: float = 2.0
    total_timeout: float = 10.0

    # Configuration des retries
    max_retries: int = 3
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    base_delay: float = 0.1
    max_delay: float = 5.0
    jitter: bool = True

    # Budget de retry (pourcentage du timeout total)
    retry_budget_percent: float = 0.3


@dataclass
class RetryBudget:
    """Budget de retry pour un endpoint."""

    total_budget: float
    used_budget: float = 0.0
    last_reset: float = 0.0

    def can_retry(self, estimated_delay: float) -> bool:
        """Vérifie si on peut faire un retry avec le budget restant."""
        return self.used_budget + estimated_delay <= self.total_budget

    def consume_budget(self, delay: float) -> None:
        """Consomme du budget pour un retry."""
        self.used_budget += delay

    def reset_if_needed(self, reset_interval: float = 60.0) -> None:
        """Remet à zéro le budget si nécessaire."""
        current_time = time.time()
        if current_time - self.last_reset > reset_interval:
            self.used_budget = 0.0
            self.last_reset = current_time


# Configuration des timeouts par endpoint
ENDPOINT_TIMEOUTS = {
    "/v1/chat/answer": TimeoutConfig(
        read_timeout=5.0,
        write_timeout=8.0,
        total_timeout=15.0,
        max_retries=2,
        retry_budget_percent=0.2,
    ),
    "/v1/retrieval/search": TimeoutConfig(
        read_timeout=3.0,
        write_timeout=5.0,
        total_timeout=10.0,
        max_retries=3,
        retry_budget_percent=0.3,
    ),
    "/v1/horoscope": TimeoutConfig(
        read_timeout=2.0,
        write_timeout=3.0,
        total_timeout=8.0,
        max_retries=2,
        retry_budget_percent=0.25,
    ),
    "/health": TimeoutConfig(
        read_timeout=1.0,
        write_timeout=1.0,
        total_timeout=3.0,
        max_retries=1,
        retry_budget_percent=0.1,
    ),
}

# Budgets de retry globaux par endpoint
retry_budgets: dict[str, RetryBudget] = {}


def get_timeout_config(path: str) -> TimeoutConfig:
    """Récupère la configuration de timeout pour un endpoint."""
    # Normalize path for matching
    normalized_path = _normalize_path_for_timeout(path)

    # Check for exact match first
    if normalized_path in ENDPOINT_TIMEOUTS:
        return ENDPOINT_TIMEOUTS[normalized_path]

    # Check for prefix match
    for endpoint, config in ENDPOINT_TIMEOUTS.items():
        if normalized_path.startswith(endpoint):
            return config

    # Default configuration
    return TimeoutConfig()


def _normalize_path_for_timeout(path: str) -> str:
    """Normalise le chemin pour la correspondance des timeouts."""
    # Remove query parameters
    normalized = path.split("?")[0]

    # Ensure it starts with /
    if not normalized.startswith("/"):
        normalized = "/" + normalized

    return normalized


def calculate_retry_delay(
    attempt: int,
    config: TimeoutConfig,
    base_delay: float | None = None,
) -> float:
    """Calculate retry delay according to configured strategy."""
    if base_delay is None:
        base_delay = config.base_delay

    if config.retry_strategy == RetryStrategy.EXPONENTIAL:
        delay = base_delay * (2**attempt)
    elif config.retry_strategy == RetryStrategy.LINEAR:
        delay = base_delay * (attempt + 1)
    else:  # FIXED
        delay = base_delay

    # Apply jitter if enabled
    if config.jitter:
        jitter_factor = random.uniform(0.5, 1.5)
        delay *= jitter_factor

    # Cap at max delay
    delay = min(delay, config.max_delay)

    return delay


def get_retry_budget(path: str, config: TimeoutConfig) -> RetryBudget:
    """Retrieve or create the retry budget for an endpoint."""
    normalized_path = _normalize_path_for_timeout(path)

    if normalized_path not in retry_budgets:
        total_budget = config.total_timeout * config.retry_budget_percent
        retry_budgets[normalized_path] = RetryBudget(total_budget=total_budget)

    budget = retry_budgets[normalized_path]
    budget.reset_if_needed()
    return budget


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Middleware to apply consistent timeouts."""

    async def dispatch(self, request: Request, call_next: Any) -> StarletteResponse:
        """Apply configured timeouts for the endpoint."""
        path = request.url.path
        config = get_timeout_config(path)

        # Set timeout headers for client information
        response = await call_next(request)

        # Add timeout information headers
        response.headers["X-Timeout-Read"] = str(config.read_timeout)
        response.headers["X-Timeout-Total"] = str(config.total_timeout)
        response.headers["X-Max-Retries"] = str(config.max_retries)

        return response


class RetryMiddleware(BaseHTTPMiddleware):
    """Middleware to handle retries with backoff and budget."""

    async def dispatch(self, request: Request, call_next: Any) -> StarletteResponse:
        """Execute request with retries and backoff strategy."""
        path = request.url.path
        route_label = normalize_route(path)
        config = get_timeout_config(path)
        budget = get_retry_budget(path, config)

        last_exception = None

        for attempt in range(config.max_retries + 1):
            try:
                # Check if we can retry based on budget
                if attempt > 0:
                    estimated_delay = calculate_retry_delay(attempt - 1, config)
                    if not budget.can_retry(estimated_delay):
                        log.warning(
                            "Retry budget exhausted",
                            extra={
                                "path": path,
                                "attempt": attempt,
                                "budget_used": budget.used_budget,
                                "budget_total": budget.total_budget,
                                "trace_id": getattr(request.state, "trace_id", None),
                            },
                        )
                        # Track budget exhaustion
                        APIGW_RETRY_BUDGET_EXHAUSTED_TOTAL.labels(route=route_label).inc()
                        APIGW_RETRY_ATTEMPTS_TOTAL.labels(route=route_label, result="blocked").inc()
                        break

                    # Wait before retry
                    await asyncio.sleep(estimated_delay)
                    budget.consume_budget(estimated_delay)

                # Attempt the request
                response = await call_next(request)

                # If successful, return response
                if response.status_code < HTTP_STATUS_SERVER_ERROR_MIN:
                    return response

                # Server error - might retry
                last_exception = Exception(f"Server error: {response.status_code}")
                # Count allowed retry decision if we will attempt again
                if attempt < config.max_retries:
                    APIGW_RETRY_ATTEMPTS_TOTAL.labels(route=route_label, result="allowed").inc()

            except TimeoutError as e:
                last_exception = e
                log.warning(
                    "Request timeout",
                    extra={
                        "path": path,
                        "attempt": attempt,
                        "timeout": config.total_timeout,
                        "trace_id": getattr(request.state, "trace_id", None),
                    },
                )
                # Count allowed retry decision if we will attempt again
                if attempt < config.max_retries:
                    APIGW_RETRY_ATTEMPTS_TOTAL.labels(route=route_label, result="allowed").inc()

            except Exception as e:
                last_exception = e
                log.error(
                    "Request failed",
                    extra={
                        "path": path,
                        "attempt": attempt,
                        "error": str(e),
                        "trace_id": getattr(request.state, "trace_id", None),
                    },
                )
                # Non-timeout generic exceptions are not retried
                break

        # All retries exhausted
        log.error(
            "All retries exhausted",
            extra={
                "path": path,
                "max_retries": config.max_retries,
                "budget_used": budget.used_budget,
                "trace_id": getattr(request.state, "trace_id", None),
            },
        )

        return create_error_response(
            status_code=504,
            code="GATEWAY_TIMEOUT",
            message="Request timeout after retries",
            trace_id=getattr(request.state, "trace_id", None),
            details={
                "max_retries": config.max_retries,
                "budget_used": budget.used_budget,
                "last_error": str(last_exception) if last_exception else "Unknown",
            },
        )


@dataclass
class TimeoutConfigUpdate:
    """Configuration update for endpoint timeouts."""

    read_timeout: float | None = None
    write_timeout: float | None = None
    total_timeout: float | None = None
    max_retries: int | None = None
    retry_budget_percent: float | None = None


def configure_endpoint_timeout(
    path: str,
    *,  # Force keyword-only arguments
    config: TimeoutConfigUpdate | None = None,
) -> None:
    """Configure timeouts for a specific endpoint."""
    normalized_path = _normalize_path_for_timeout(path)

    if normalized_path in ENDPOINT_TIMEOUTS:
        endpoint_config = ENDPOINT_TIMEOUTS[normalized_path]
    else:
        endpoint_config = TimeoutConfig()

    if config is not None:
        if config.read_timeout is not None:
            endpoint_config.read_timeout = config.read_timeout
        if config.write_timeout is not None:
            endpoint_config.write_timeout = config.write_timeout
        if config.total_timeout is not None:
            endpoint_config.total_timeout = config.total_timeout
        if config.max_retries is not None:
            endpoint_config.max_retries = config.max_retries
        if config.retry_budget_percent is not None:
            endpoint_config.retry_budget_percent = config.retry_budget_percent

    ENDPOINT_TIMEOUTS[normalized_path] = endpoint_config

    # Update retry budget if it exists
    if normalized_path in retry_budgets:
        retry_budgets[normalized_path].total_budget = (
            endpoint_config.total_timeout * endpoint_config.retry_budget_percent
        )


def get_timeout_status() -> dict[str, Any]:
    """Get current status of timeout configurations and retry budgets."""
    status: dict[str, Any] = {
        "endpoints": {},
        "budgets": {},
    }

    for path, config in ENDPOINT_TIMEOUTS.items():
        status["endpoints"][path] = {
            "read_timeout": config.read_timeout,
            "write_timeout": config.write_timeout,
            "total_timeout": config.total_timeout,
            "max_retries": config.max_retries,
            "retry_budget_percent": config.retry_budget_percent,
        }

    for path, budget in retry_budgets.items():
        status["budgets"][path] = {
            "total_budget": budget.total_budget,
            "used_budget": budget.used_budget,
            "remaining_budget": budget.total_budget - budget.used_budget,
            "last_reset": budget.last_reset,
        }

    return status


def reset_timeout_configuration() -> None:
    """Reset timeout configuration to defaults (for testing)."""
    # Reset to original configuration
    ENDPOINT_TIMEOUTS.clear()
    ENDPOINT_TIMEOUTS.update(
        {
            "/v1/chat/answer": TimeoutConfig(
                read_timeout=5.0,
                write_timeout=8.0,
                total_timeout=15.0,
                max_retries=2,
                retry_budget_percent=0.2,
            ),
            "/v1/retrieval/search": TimeoutConfig(
                read_timeout=3.0,
                write_timeout=5.0,
                total_timeout=10.0,
                max_retries=3,
                retry_budget_percent=0.3,
            ),
            "/v1/horoscope": TimeoutConfig(
                read_timeout=2.0,
                write_timeout=3.0,
                total_timeout=8.0,
                max_retries=2,
                retry_budget_percent=0.25,
            ),
            "/health": TimeoutConfig(max_retries=0),  # No retries for health checks
        }
    )

    # Clear retry budgets
    retry_budgets.clear()
