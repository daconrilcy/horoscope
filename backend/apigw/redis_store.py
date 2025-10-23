"""Store Redis atomique pour le rate limiting distribué.

Ce module implémente un store Redis avec opérations atomiques pour le rate limiting en multi-pods,
utilisant des scripts Lua pour garantir la cohérence.
"""

import hashlib
import logging
import time
from dataclasses import dataclass

import redis
from redis.exceptions import ConnectionError, TimeoutError

from backend.app.metrics import APIGW_RATE_LIMIT_STORE_ERRORS, normalize_route
from backend.core.settings import get_settings

log = logging.getLogger(__name__)

# Script Lua pour fenêtre glissante atomique
SLIDING_WINDOW_SCRIPT = """
local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

-- Nettoyer les entrées expirées
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

-- Compter les requêtes dans la fenêtre
local current = redis.call('ZCARD', key)

if current < limit then
    -- Ajouter la requête actuelle
    redis.call('ZADD', key, now, now)
    redis.call('EXPIRE', key, window)

    return {1, current + 1, limit - current - 1, now + window}
else
    -- Trouver la plus ancienne requête pour calculer le retry_after
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = 0
    if #oldest > 0 then
        retry_after = math.ceil(window - (now - oldest[2]))
    end

    return {0, current, 0, now + retry_after}
end
"""


@dataclass
class RateLimitResult:
    """Résultat d'une vérification de rate limit."""

    allowed: bool
    remaining: int
    reset_time: float
    retry_after: int | None = None


class RedisRateLimitStore:
    """Store Redis atomique pour le rate limiting distribué."""

    def __init__(self) -> None:
        """Initialize Redis store with settings."""
        self.settings = get_settings()
        self._redis: redis.Redis | None = None
        self._script_hash: str | None = None

    def _get_redis(self) -> redis.Redis:
        """Get Redis connection with lazy initialization."""
        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    self.settings.REDIS_URL,
                    socket_connect_timeout=self.settings.RL_CONNECT_TIMEOUT_MS / 1000,
                    socket_timeout=self.settings.RL_READ_TIMEOUT_MS / 1000,
                    retry_on_timeout=True,
                    health_check_interval=30,
                )
                # Test connection
                self._redis.ping()
                log.info("Redis rate limit store connected")
            except (ConnectionError, TimeoutError) as e:
                log.error(
                    "Failed to connect to Redis rate limit store",
                    extra={"error": str(e)},
                )
                raise

        return self._redis

    def _get_script_hash(self) -> str:
        """Get Lua script hash for atomic operations."""
        if self._script_hash is None:
            redis_client = self._get_redis()
            self._script_hash = redis_client.script_load(SLIDING_WINDOW_SCRIPT)
        return self._script_hash

    def _hash_tenant(self, tenant: str) -> str:
        """Hash tenant for consistent key generation."""
        return hashlib.sha256(tenant.encode()).hexdigest()[:16]

    def check_rate_limit(
        self,
        route: str,
        tenant: str,
        window_seconds: int | None = None,
        max_requests: int | None = None,
    ) -> RateLimitResult:
        """Check rate limit atomically using Redis sliding window.

        Args:
            route: Normalized route path
            tenant: Tenant identifier
            window_seconds: Window size in seconds
            max_requests: Maximum requests per window

        Returns:
            RateLimitResult with decision and metadata
        """
        window_seconds = window_seconds or self.settings.RL_WINDOW_SECONDS
        max_requests = max_requests or self.settings.RL_MAX_REQ_PER_WINDOW

        # Normalize route for consistent keys
        normalized_route = normalize_route(route)
        tenant_hash = self._hash_tenant(tenant)

        # Redis key: rl:{route}:{tenant_hash}
        key = f"rl:{normalized_route}:{tenant_hash}"

        try:
            redis_client = self._get_redis()
            script_hash = self._get_script_hash()

            # Execute atomic sliding window script
            now = time.time()
            result = redis_client.evalsha(
                script_hash,
                1,  # numkeys
                key,
                window_seconds,
                max_requests,
                now,
            )

            # Parse result: [allowed, current_count, remaining, reset_time]
            allowed = bool(result[0])
            int(result[1])
            remaining = int(result[2])
            reset_time = float(result[3])

            retry_after = None
            if not allowed:
                retry_after = max(1, int(reset_time - now))

            return RateLimitResult(
                allowed=allowed,
                remaining=remaining,
                reset_time=reset_time,
                retry_after=retry_after,
            )

        except (ConnectionError, TimeoutError) as e:
            # Fail-open: allow request if Redis is unavailable
            log.warning(
                "Rate limit store unavailable, failing open",
                extra={
                    "route": normalized_route,
                    "tenant": tenant,
                    "error": str(e),
                    "trace_id": None,  # Will be set by caller
                },
            )

            # Increment error metric
            APIGW_RATE_LIMIT_STORE_ERRORS.labels(
                route=normalized_route, error_type="connection_error"
            ).inc()

            # Fail-open: allow the request
            return RateLimitResult(
                allowed=True,
                remaining=max_requests - 1,  # Assume one request used
                reset_time=time.time() + window_seconds,
                retry_after=None,
            )

        except Exception as e:
            # Unexpected error - fail open but log
            log.error(
                "Unexpected rate limit store error",
                extra={
                    "route": normalized_route,
                    "tenant": tenant,
                    "error": str(e),
                    "trace_id": None,
                },
            )

            APIGW_RATE_LIMIT_STORE_ERRORS.labels(
                route=normalized_route, error_type="unexpected_error"
            ).inc()

            return RateLimitResult(
                allowed=True,
                remaining=max_requests - 1,
                reset_time=time.time() + window_seconds,
                retry_after=None,
            )

    def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            self._redis.close()
            self._redis = None


# Global store instance
redis_store = RedisRateLimitStore()
