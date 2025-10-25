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
    APIGW_RETRY_BLOCKS_TOTAL,
    APIGW_RETRY_BUDGET_EXHAUSTED_TOTAL,
    normalize_route,
)
from backend.core.constants import HTTP_STATUS_SERVER_ERROR_MIN
from backend.core.container import container

log = logging.getLogger(__name__)


def _clamp_timeouts_from_settings(config: TimeoutConfig) -> None:
    """Clamp endpoint timeouts using max values from settings."""
    max_read = float(getattr(container.settings, "APIGW_READ_TIMEOUT_MAX_S", 15.0))
    max_total = float(getattr(container.settings, "APIGW_TOTAL_TIMEOUT_MAX_S", 30.0))
    config.read_timeout = min(config.read_timeout, max_read)
    config.total_timeout = min(config.total_timeout, max_total)


def _init_deadline_if_missing(request: Request, total_timeout: float) -> None:
    """Initialize a per-request deadline if not already present."""
    if not hasattr(request.state, "deadline_epoch"):
        request.state.deadline_epoch = time.perf_counter() + total_timeout


def _get_remaining_deadline(request: Request) -> float:
    """Compute remaining time until the request deadline."""
    now = time.perf_counter()
    return float(getattr(request.state, "deadline_epoch", now) - now)


def _should_retry_status(status_code: int) -> bool:
    """Return whether the HTTP status is retryable (strict whitelist)."""
    return status_code in (502, 503)


def _record_retry_block(route_label: str, reason: str) -> None:
    """Record a retry block reason in metrics with low cardinality labels."""
    APIGW_RETRY_BLOCKS_TOTAL.labels(route=route_label, reason=reason).inc()


async def _apply_backoff_or_block(ctx: AttemptCtx) -> bool:
    """Apply backoff if budget allows; record block if budget exhausted.

    Returns True if blocked (budget exhausted), False otherwise.
    """
    estimated_delay = calculate_retry_delay(ctx.attempt - 1, ctx.config)
    if not ctx.budget.can_retry(estimated_delay):
        APIGW_RETRY_BUDGET_EXHAUSTED_TOTAL.labels(route=ctx.route_label).inc()
        APIGW_RETRY_ATTEMPTS_TOTAL.labels(route=ctx.route_label, result="blocked").inc()
        _record_retry_block(ctx.route_label, "budget_exhausted")
        return True
    await asyncio.sleep(estimated_delay)
    ctx.budget.consume_budget(estimated_delay)
    return False


def _process_response(
    ctx: AttemptCtx, resp: StarletteResponse
) -> tuple[bool, Exception | None, StarletteResponse | None]:
    """Process response and update metrics (finished, last_exception, response)."""
    if resp.status_code < HTTP_STATUS_SERVER_ERROR_MIN:
        resp.headers["X-Retry-Count"] = str(ctx.attempts_done)
        return True, None, resp

    last_exc: Exception | None = Exception(f"Server error: {resp.status_code}")
    if not _should_retry_status(resp.status_code):
        APIGW_RETRY_ATTEMPTS_TOTAL.labels(route=ctx.route_label, result="blocked").inc()
        _record_retry_block(ctx.route_label, "non_retryable")
        return True, last_exc, None

    if ctx.attempt < ctx.config.max_retries:
        APIGW_RETRY_ATTEMPTS_TOTAL.labels(route=ctx.route_label, result="allowed").inc()
    ctx.attempts_done = ctx.attempt
    return False, last_exc, None


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
class AttemptCtx:
    """Context for a retry attempt."""

    route_label: str
    path: str
    config: TimeoutConfig
    budget: RetryBudget
    attempts_done: int
    attempt: int


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

        _clamp_timeouts_from_settings(config)
        _init_deadline_if_missing(request, config.total_timeout)

        last_exception: Exception | None = None
        ctx = AttemptCtx(
            route_label=route_label,
            path=path,
            config=config,
            budget=budget,
            attempts_done=0,
            attempt=0,
        )

        for attempt in range(config.max_retries + 1):
            ctx.attempt = attempt
            did_finish, last_exception, response = await self._attempt_once(request, call_next, ctx)
            if did_finish:
                return response or self._final_timeout_response(
                    request, config, budget, ctx.attempts_done, last_exception
                )

        return self._final_timeout_response(
            request,
            config,
            budget,
            ctx.attempts_done,
            last_exception,
        )

    async def _attempt_once(
        self,
        request: Request,
        call_next: Any,
        ctx: AttemptCtx,
    ) -> tuple[bool, Exception | None, StarletteResponse | None]:
        """Execute a single attempt; return (finished, last_exc, response)."""
        finished = False
        response: StarletteResponse | None = None
        last_exception: Exception | None = None

        if _get_remaining_deadline(request) <= 0:
            APIGW_RETRY_ATTEMPTS_TOTAL.labels(route=ctx.route_label, result="blocked").inc()
            _record_retry_block(ctx.route_label, "deadline_exceeded")
            finished = True
        else:
            try:
                if ctx.attempt > 0 and await _apply_backoff_or_block(ctx):
                    finished = True

                if not finished:
                    resp = await call_next(request)
                    finished, last_exception, response = _process_response(ctx, resp)

            except TimeoutError as e:
                last_exception = e
                if ctx.attempt < ctx.config.max_retries:
                    APIGW_RETRY_ATTEMPTS_TOTAL.labels(route=ctx.route_label, result="allowed").inc()
                ctx.attempts_done = ctx.attempt
            except Exception as e:
                APIGW_RETRY_ATTEMPTS_TOTAL.labels(route=ctx.route_label, result="blocked").inc()
                _record_retry_block(ctx.route_label, "non_retryable")
                last_exception = e
                finished = True

        return finished, last_exception, response

    def _final_timeout_response(
        self,
        request: Request,
        config: TimeoutConfig,
        budget: RetryBudget,
        attempts_done: int,
        last_exception: Exception | None,
    ) -> StarletteResponse:
        log.error(
            "All retries exhausted",
            extra={
                "path": request.url.path,
                "max_retries": config.max_retries,
                "budget_used": budget.used_budget,
                "trace_id": getattr(request.state, "trace_id", None),
            },
        )
        response = create_error_response(
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
        response.headers["X-Retry-Count"] = str(attempts_done)
        return response


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
