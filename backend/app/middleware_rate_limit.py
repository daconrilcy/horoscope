"""Per-tenant QPS rate limiting middleware.

Reads tenant from `X-Tenant` header (provided by an auth proxy). Do not trust
this header in production unless enforced via mTLS/auth proxy; otherwise derive
tenant from JWT/claims in the backend.

Limit is
configurable via env/settings `RATE_LIMIT_TENANT_QPS` (default=5).

On block, returns 429 and increments Prom counter
`rate_limit_blocks_total{tenant,reason}` with reason `qps`.
"""

from __future__ import annotations

import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from backend.app.metrics import RATE_LIMIT_BLOCKS
from backend.core.settings import get_settings


class _Limiter:
    def __init__(self, qps: int) -> None:
        self.qps = max(1, int(qps))
        # tenant -> (window_start_monotonic, count)
        self._buckets: dict[str, tuple[float, int]] = {}

    def allow(self, tenant: str) -> bool:
        now = time.perf_counter()
        start, count = self._buckets.get(tenant, (now, 0))
        # Rolling 1-second window based on monotonic clock to avoid boundary flakes
        if now - start >= 1.0:
            start, count = now, 0
        if count >= self.qps:
            self._buckets[tenant] = (start, count)
            return False
        self._buckets[tenant] = (start, count + 1)
        return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        settings = get_settings()
        qps = getattr(settings, "RATE_LIMIT_TENANT_QPS", 5) or 5
        self.limiter = _Limiter(qps=qps)

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        # Enforce only when tenant header is explicitly provided
        tenant = request.headers.get("X-Tenant")
        if not tenant:
            return await call_next(request)
        if request.url.path.startswith("/metrics"):
            return await call_next(request)
        # Optional exemption for /health via env flag
        if request.url.path.startswith("/health") and getattr(
            get_settings(), "RATE_LIMIT_EXEMPT_HEALTH", False
        ):
            return await call_next(request)
        # store for downstream usage if needed
        request.state.tenant = tenant
        # pick up dynamic qps from env for tests
        qps_now = (
            getattr(get_settings(), "RATE_LIMIT_TENANT_QPS", self.limiter.qps) or self.limiter.qps
        )
        self.limiter.qps = max(1, int(qps_now))
        if not self.limiter.allow(tenant):
            RATE_LIMIT_BLOCKS.labels(tenant=tenant, reason="qps").inc()
            return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
        return await call_next(request)
