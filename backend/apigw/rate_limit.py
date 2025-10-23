"""
Rate limiting et quotas par tenant pour l'API Gateway.

Ce module implémente un système de rate limiting basé sur des fenêtres glissantes avec support des
quotas par tenant, métriques Prometheus et gestion des erreurs 429 avec Retry-After.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

from backend.apigw.errors import create_error_response
from backend.app.metrics import (
    APIGW_RATE_LIMIT_BLOCKS,
    APIGW_RATE_LIMIT_DECISIONS,
    APIGW_RATE_LIMIT_EVALUATION_TIME,
    APIGW_RATE_LIMIT_NEAR_LIMIT,
    normalize_route,
)
from backend.domain.tenancy import safe_tenant

log = logging.getLogger(__name__)

# Constants
NEAR_LIMIT_THRESHOLD = 0.1  # Alert when remaining/limit < 10%


@dataclass
class RateLimitConfig:
    """Configuration pour le rate limiting par tenant."""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10
    window_size_seconds: int = 60


@dataclass
class RateLimitResult:
    """Résultat d'une vérification de rate limit."""

    allowed: bool
    remaining: int
    reset_time: float
    retry_after: int | None = None


class SlidingWindowRateLimiter:
    """Rate limiter basé sur une fenêtre glissante."""

    def __init__(self, config: RateLimitConfig) -> None:
        """Initialize sliding window rate limiter."""
        self.config = config
        self._windows: dict[str, list[float]] = defaultdict(list)

    def _cleanup_old_requests(self, tenant: str, current_time: float) -> None:
        """Remove requests older than the window size."""
        cutoff_time = current_time - self.config.window_size_seconds
        self._windows[tenant] = [
            req_time for req_time in self._windows[tenant] if req_time > cutoff_time
        ]

    def check_rate_limit(self, tenant: str) -> RateLimitResult:
        """Check if request is allowed for tenant."""
        current_time = time.time()
        self._cleanup_old_requests(tenant, current_time)

        # Count current requests in window
        current_requests = len(self._windows[tenant])

        # Check if limit exceeded
        if current_requests >= self.config.requests_per_minute:
            # Calculate retry after
            if self._windows[tenant]:
                oldest_request = min(self._windows[tenant])
                retry_after = int(
                    self.config.window_size_seconds - (current_time - oldest_request)
                )
                retry_after = max(1, retry_after)
            else:
                retry_after = self.config.window_size_seconds

            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=current_time + retry_after,
                retry_after=retry_after,
            )

        # Add current request
        self._windows[tenant].append(current_time)

        # Calculate remaining requests
        remaining = self.config.requests_per_minute - current_requests - 1
        reset_time = current_time + self.config.window_size_seconds

        return RateLimitResult(
            allowed=True,
            remaining=max(0, remaining),
            reset_time=reset_time,
        )


class TenantRateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware pour appliquer le rate limiting par tenant."""

    def __init__(
        self,
        app: Any,
        config: RateLimitConfig | None = None,
        enabled: bool = True,
    ) -> None:
        """Initialize tenant rate limit middleware."""
        super().__init__(app)
        self.config = config or RateLimitConfig()
        self.enabled = enabled
        self.rate_limiter = SlidingWindowRateLimiter(self.config)

    async def dispatch(self, request: Request, call_next: Any) -> StarletteResponse:
        """Apply rate limiting to request."""
        if not self.enabled:
            return await call_next(request)

        # Skip rate limiting for health checks and metrics
        path = request.url.path
        if path.startswith(("/health", "/metrics", "/docs", "/openapi.json")):
            return await call_next(request)

        # Normalize route for metrics
        route = normalize_route(path)

        # Measure evaluation time
        start_time = time.perf_counter()

        try:
            # Extract tenant from request
            tenant = self._extract_tenant(request)

            # Check rate limit
            result = self.rate_limiter.check_rate_limit(tenant)

            if not result.allowed:
                # Log rate limit violation with tenant in logs (not metrics)
                log.warning(
                    "Rate limit exceeded",
                    extra={
                        "tenant": tenant,
                        "path": path,
                        "route": route,
                        "method": request.method,
                        "retry_after": result.retry_after,
                        "trace_id": getattr(request.state, "trace_id", None),
                    },
                )

                # Increment low-cardinality metrics
                APIGW_RATE_LIMIT_DECISIONS.labels(route=route, result="block").inc()
                APIGW_RATE_LIMIT_BLOCKS.labels(
                    route=route, reason="rate_exceeded"
                ).inc()

                # Return 429 with Retry-After header
                response = create_error_response(
                    status_code=429,
                    code="RATE_LIMITED",
                    message="Rate limit exceeded. Try again later.",
                    trace_id=getattr(request.state, "trace_id", None),
                    details={"retry_after": result.retry_after},
                )

                # Add Retry-After header
                if result.retry_after:
                    response.headers["Retry-After"] = str(result.retry_after)

                return response

            # Check if near limit (for pre-alerting)
            if result.remaining / self.config.requests_per_minute < NEAR_LIMIT_THRESHOLD:
                APIGW_RATE_LIMIT_NEAR_LIMIT.labels(route=route).inc()

            # Add rate limit headers to successful responses
            response = await call_next(request)

            # Add rate limit headers
            response.headers["X-RateLimit-Limit"] = str(self.config.requests_per_minute)
            response.headers["X-RateLimit-Remaining"] = str(result.remaining)
            response.headers["X-RateLimit-Reset"] = str(int(result.reset_time))

            # Increment allow metric
            APIGW_RATE_LIMIT_DECISIONS.labels(route=route, result="allow").inc()

            return response

        finally:
            # Record evaluation time
            evaluation_time = time.perf_counter() - start_time
            APIGW_RATE_LIMIT_EVALUATION_TIME.labels(route=route).observe(
                evaluation_time
            )

    def _extract_tenant(self, request: Request) -> str:
        """Extract tenant identifier from request."""
        # Try to get tenant from authenticated user context
        if hasattr(request.state, "user") and request.state.user:
            user_tenant = getattr(request.state.user, "tenant", None)
            if user_tenant:
                return safe_tenant(user_tenant)

        # Try to get tenant from headers (for trusted proxy scenarios)
        tenant_header = request.headers.get("X-Tenant-ID")
        if tenant_header:
            return safe_tenant(tenant_header)

        # Try to get tenant from Authorization header (JWT)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            # In a real implementation, you would decode the JWT here
            # For now, we'll use a simple extraction
            try:
                # This is a placeholder - in production, decode JWT properly
                # and extract tenant from claims
                return safe_tenant("default")
            except Exception:
                pass

        # Default tenant
        return safe_tenant("default")


class QuotaManager:
    """Gestionnaire de quotas pour différents types de ressources."""

    def __init__(self) -> None:
        """Initialize quota manager."""
        self._quotas: dict[str, dict[str, int]] = defaultdict(dict)

    def set_quota(self, tenant: str, resource: str, limit: int) -> None:
        """Set quota limit for tenant and resource."""
        self._quotas[tenant][resource] = limit

    def get_quota(self, tenant: str, resource: str) -> int:
        """Get quota limit for tenant and resource."""
        return self._quotas[tenant].get(resource, 0)

    def check_quota(self, tenant: str, resource: str, usage: int) -> bool:
        """Check if usage is within quota limits."""
        limit = self.get_quota(tenant, resource)
        return usage <= limit if limit > 0 else True


# Global quota manager instance
quota_manager = QuotaManager()


def configure_default_quotas() -> None:
    """Configure default quotas for tenants."""
    # Default quotas per tenant
    default_quotas = {
        "requests_per_minute": 60,
        "requests_per_hour": 1000,
        "chat_requests_per_hour": 100,
        "retrieval_requests_per_hour": 500,
    }

    # Apply to default tenant
    for resource, limit in default_quotas.items():
        quota_manager.set_quota("default", resource, limit)


# Initialize default quotas
configure_default_quotas()


class QuotaMiddleware(BaseHTTPMiddleware):
    """Middleware pour vérifier les quotas par tenant."""

    def __init__(self, app: Any, enabled: bool = True) -> None:
        """Initialize quota middleware."""
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next: Any) -> StarletteResponse:
        """Check quotas before processing request."""
        if not self.enabled:
            return await call_next(request)

        # Skip quota checks for health checks and metrics
        path = request.url.path
        if path.startswith(("/health", "/metrics", "/docs", "/openapi.json")):
            return await call_next(request)

        # Extract tenant
        tenant = self._extract_tenant(request)

        # Check specific quotas based on endpoint
        if path.startswith("/v1/chat/"):
            # Check chat quota
            if not self._check_endpoint_quota(tenant, "chat_requests_per_hour"):
                return self._create_quota_exceeded_response(
                    request, tenant, "chat requests"
                )

        elif path.startswith("/v1/retrieval/") and not self._check_endpoint_quota(
            tenant, "retrieval_requests_per_hour"
        ):
            return self._create_quota_exceeded_response(
                request, tenant, "retrieval requests"
            )

        return await call_next(request)

    def _extract_tenant(self, request: Request) -> str:
        """Extract tenant identifier from request."""
        # Same logic as RateLimitMiddleware
        if hasattr(request.state, "user") and request.state.user:
            user_tenant = getattr(request.state.user, "tenant", None)
            if user_tenant:
                return safe_tenant(user_tenant)

        tenant_header = request.headers.get("X-Tenant-ID")
        if tenant_header:
            return safe_tenant(tenant_header)

        return safe_tenant("default")

    def _check_endpoint_quota(self, tenant: str, resource: str) -> bool:
        """Check if tenant is within quota for specific resource."""
        # In a real implementation, you would track actual usage
        # For now, we'll use a simple check against the limit
        limit = quota_manager.get_quota(tenant, resource)
        # If limit is 0, no quota is set, so allow the request
        # If limit > 0, quota is set, so we would need to check actual usage
        return limit == 0

    def _create_quota_exceeded_response(
        self, request: Request, tenant: str, resource_type: str
    ) -> StarletteResponse:
        """Create quota exceeded response."""
        log.warning(
            "Quota exceeded",
            extra={
                "tenant": tenant,
                "resource_type": resource_type,
                "trace_id": getattr(request.state, "trace_id", None),
            },
        )

        # Increment metrics
        route = normalize_route(request.url.path)
        APIGW_RATE_LIMIT_DECISIONS.labels(route=route, result="block").inc()
        APIGW_RATE_LIMIT_BLOCKS.labels(route=route, reason="quota_exceeded").inc()

        response = create_error_response(
            status_code=429,
            code="QUOTA_EXCEEDED",
            message=f"Quota exceeded for {resource_type}",
            trace_id=getattr(request.state, "trace_id", None),
        )
        
        # Add Retry-After header (1 hour for quota exceeded)
        response.headers["Retry-After"] = "3600"  # 1 hour
        
        return response
