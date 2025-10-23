"""
Tests unitaires pour le rate limiting et quotas par tenant.

Ce module teste les fonctionnalités de rate limiting, quotas et gestion des erreurs 429 avec header
Retry-After.
"""

import time
from unittest.mock import Mock, patch

import pytest
from fastapi import Request
from starlette.responses import Response

from backend.apigw.rate_limit import (
    QuotaManager,
    QuotaMiddleware,
    RateLimitConfig,
    RateLimitResult,
    SlidingWindowRateLimiter,
    TenantRateLimitMiddleware,
)


class TestSlidingWindowRateLimiter:
    """Tests pour SlidingWindowRateLimiter."""

    def test_rate_limit_allowed(self) -> None:
        """Test que les requêtes dans la limite sont autorisées."""
        config = RateLimitConfig(requests_per_minute=5)
        limiter = SlidingWindowRateLimiter(config)

        result = limiter.check_rate_limit("tenant1")
        assert result.allowed is True
        assert result.remaining == 4  # requests_per_minute - 1
        assert result.retry_after is None

    def test_rate_limit_exceeded(self) -> None:
        """Test que les requêtes au-delà de la limite sont refusées."""
        config = RateLimitConfig(requests_per_minute=2)
        limiter = SlidingWindowRateLimiter(config)

        # First two requests should be allowed
        result1 = limiter.check_rate_limit("tenant1")
        assert result1.allowed is True

        result2 = limiter.check_rate_limit("tenant1")
        assert result2.allowed is True

        # Third request should be blocked
        result3 = limiter.check_rate_limit("tenant1")
        assert result3.allowed is False
        assert result3.remaining == 0
        assert result3.retry_after is not None

    def test_rate_limit_reset_after_window(self) -> None:
        """Test que la limite se remet après la fenêtre."""
        config = RateLimitConfig(requests_per_minute=1, window_size_seconds=1)
        limiter = SlidingWindowRateLimiter(config)

        # First request allowed
        result1 = limiter.check_rate_limit("tenant1")
        assert result1.allowed is True

        # Second request blocked
        result2 = limiter.check_rate_limit("tenant1")
        assert result2.allowed is False

        # Wait for window to reset
        time.sleep(1.1)

        # Request should be allowed again
        result3 = limiter.check_rate_limit("tenant1")
        assert result3.allowed is True

    def test_rate_limit_exceeded_no_requests_in_window(self) -> None:
        """Test rate limit exceeded when no requests in window."""
        config = RateLimitConfig(requests_per_minute=1)
        limiter = SlidingWindowRateLimiter(config)

        # Make one request to fill the limit
        result1 = limiter.check_rate_limit("tenant1")
        assert result1.allowed is True

        # Second request should be blocked
        result2 = limiter.check_rate_limit("tenant1")
        assert result2.allowed is False
        assert result2.retry_after is not None
        assert result2.retry_after >= config.window_size_seconds - 1  # Allow for timing

    def test_rate_limit_exceeded_empty_window(self) -> None:
        """Test rate limit exceeded when window is empty but limit reached."""
        config = RateLimitConfig(requests_per_minute=1)
        limiter = SlidingWindowRateLimiter(config)

        # Make one request to fill the limit
        result1 = limiter.check_rate_limit("tenant1")
        assert result1.allowed is True

        # Manually set the window to have reached the limit but be empty
        # This simulates the case where the window was cleared but limit was reached
        limiter._windows["tenant1"] = []

        # Force the limit check to think we're at the limit
        # We need to simulate the condition where current_requests >= limit
        # but the window is empty
        limiter._windows["tenant1"] = [time.time() - 2]  # Old request

        # Second request should be blocked
        result2 = limiter.check_rate_limit("tenant1")
        assert result2.allowed is False
        assert result2.retry_after is not None

    def test_different_tenants_independent(self) -> None:
        """Test que les limites sont indépendantes par tenant."""
        config = RateLimitConfig(requests_per_minute=1)
        limiter = SlidingWindowRateLimiter(config)

        # Both tenants should be able to make one request
        result1 = limiter.check_rate_limit("tenant1")
        result2 = limiter.check_rate_limit("tenant2")

        assert result1.allowed is True
        assert result2.allowed is True

        # Both should be blocked on second request
        result3 = limiter.check_rate_limit("tenant1")
        result4 = limiter.check_rate_limit("tenant2")

        assert result3.allowed is False
        assert result4.allowed is False


class TestTenantRateLimitMiddleware:
    """Tests pour TenantRateLimitMiddleware."""

    def create_mock_request(
        self, path: str = "/v1/test", method: str = "GET"
    ) -> Request:
        """Create a mock request for testing."""
        request = Mock(spec=Request)
        request.url.path = path
        request.method = method
        request.headers = {}
        request.state = Mock()
        request.state.trace_id = "test-trace-id"
        request.state.user = None  # Ensure no user state by default
        return request

    @pytest.mark.asyncio
    async def test_middleware_disabled(self) -> None:
        """Test que le middleware désactivé laisse passer les requêtes."""
        middleware = TenantRateLimitMiddleware(Mock(), enabled=False)
        request = self.create_mock_request()

        async def call_next(req: Request) -> Response:
            return Response("OK", status_code=200)

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_endpoints_skipped(self) -> None:
        """Test que les endpoints de santé sont ignorés."""
        middleware = TenantRateLimitMiddleware(Mock())
        request = self.create_mock_request("/health")

        async def call_next(req: Request) -> Response:
            return Response("OK", status_code=200)

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_rate_limit_headers_added(self) -> None:
        """Test que les headers de rate limit sont ajoutés."""
        config = RateLimitConfig(requests_per_minute=10)
        middleware = TenantRateLimitMiddleware(Mock(), config=config)
        request = self.create_mock_request()

        async def call_next(req: Request) -> Response:
            return Response("OK", status_code=200)

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_response(self) -> None:
        """Test la réponse 429 quand la limite est dépassée."""
        config = RateLimitConfig(requests_per_minute=1)
        middleware = TenantRateLimitMiddleware(Mock(), config=config)

        # First request should succeed
        request1 = self.create_mock_request()

        async def call_next1(req: Request) -> Response:
            return Response("OK", status_code=200)

        response1 = await middleware.dispatch(request1, call_next1)
        assert response1.status_code == 200

        # Second request should be blocked
        request2 = self.create_mock_request()

        async def call_next2(req: Request) -> Response:
            return Response("OK", status_code=200)

        response2 = await middleware.dispatch(request2, call_next2)
        assert response2.status_code == 429
        assert "Retry-After" in response2.headers

    def test_tenant_extraction_from_header(self) -> None:
        """Test l'extraction du tenant depuis les headers."""
        middleware = TenantRateLimitMiddleware(Mock())
        request = self.create_mock_request()
        request.headers = {"X-Tenant-ID": "test-tenant"}
        request.state.user = None  # Ensure no user state

        tenant = middleware._extract_tenant(request)
        assert tenant == "test-tenant"

    def test_tenant_extraction_default(self) -> None:
        """Test l'extraction du tenant par défaut."""
        middleware = TenantRateLimitMiddleware(Mock())
        request = self.create_mock_request()
        request.state.user = None  # Ensure no user state

        tenant = middleware._extract_tenant(request)
        assert tenant == "default"

    def test_tenant_extraction_from_jwt(self) -> None:
        """Test extraction du tenant depuis JWT."""
        middleware = TenantRateLimitMiddleware(Mock())
        request = self.create_mock_request()
        request.headers = {"Authorization": "Bearer fake-jwt-token"}
        request.state.user = None

        tenant = middleware._extract_tenant(request)
        assert tenant == "default"  # Should fallback to default for fake JWT

    def test_tenant_extraction_from_user_state(self) -> None:
        """Test extraction du tenant depuis l'état utilisateur."""
        middleware = TenantRateLimitMiddleware(Mock())
        request = self.create_mock_request()
        request.state.user = Mock()
        request.state.user.tenant = "user-tenant"

        tenant = middleware._extract_tenant(request)
        assert tenant == "user-tenant"


class TestQuotaManager:
    """Tests pour QuotaManager."""

    def test_set_and_get_quota(self) -> None:
        """Test la définition et récupération des quotas."""
        manager = QuotaManager()
        manager.set_quota("tenant1", "requests", 100)

        assert manager.get_quota("tenant1", "requests") == 100
        assert manager.get_quota("tenant1", "unknown") == 0

    def test_check_quota(self) -> None:
        """Test la vérification des quotas."""
        manager = QuotaManager()
        manager.set_quota("tenant1", "requests", 10)

        assert manager.check_quota("tenant1", "requests", 5) is True
        assert manager.check_quota("tenant1", "requests", 10) is True
        assert manager.check_quota("tenant1", "requests", 15) is False

    def test_unlimited_quota(self) -> None:
        """Test que les quotas non définis sont illimités."""
        manager = QuotaManager()

        assert manager.check_quota("tenant1", "requests", 1000) is True


class TestQuotaMiddleware:
    """Tests pour QuotaMiddleware."""

    def create_mock_request(self, path: str = "/v1/test") -> Request:
        """Create a mock request for testing."""
        request = Mock(spec=Request)
        request.url.path = path
        request.headers = {}
        request.state = Mock()
        request.state.trace_id = "test-trace-id"
        request.state.user = None  # Ensure no user state by default
        return request

    @pytest.mark.asyncio
    async def test_middleware_disabled(self) -> None:
        """Test que le middleware désactivé laisse passer les requêtes."""
        middleware = QuotaMiddleware(Mock(), enabled=False)
        request = self.create_mock_request()

        async def call_next(req: Request) -> Response:
            return Response("OK", status_code=200)

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_endpoints_skipped(self) -> None:
        """Test que les endpoints de santé sont ignorés."""
        middleware = QuotaMiddleware(Mock())
        request = self.create_mock_request("/health")

        async def call_next(req: Request) -> Response:
            return Response("OK", status_code=200)

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @patch("backend.apigw.rate_limit.quota_manager")
    @pytest.mark.asyncio
    async def test_chat_quota_check(self, mock_quota_manager: Mock) -> None:
        """Test la vérification des quotas pour les endpoints chat."""
        mock_quota_manager.get_quota.return_value = 0  # No quota set
        middleware = QuotaMiddleware(Mock())
        request = self.create_mock_request("/v1/chat/answer")

        async def call_next(req: Request) -> Response:
            return Response("OK", status_code=200)

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @patch("backend.apigw.rate_limit.quota_manager")
    @pytest.mark.asyncio
    async def test_retrieval_quota_check(self, mock_quota_manager: Mock) -> None:
        """Test la vérification des quotas pour les endpoints retrieval."""
        mock_quota_manager.get_quota.return_value = 0  # No quota set
        middleware = QuotaMiddleware(Mock())
        request = self.create_mock_request("/v1/retrieval/search")

        async def call_next(req: Request) -> Response:
            return Response("OK", status_code=200)

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200


class TestRateLimitConfig:
    """Tests pour RateLimitConfig."""

    def test_default_config(self) -> None:
        """Test la configuration par défaut."""
        config = RateLimitConfig()
        assert config.requests_per_minute == 60
        assert config.requests_per_hour == 1000
        assert config.burst_limit == 10
        assert config.window_size_seconds == 60

    def test_custom_config(self) -> None:
        """Test la configuration personnalisée."""
        config = RateLimitConfig(
            requests_per_minute=30,
            requests_per_hour=500,
            burst_limit=5,
            window_size_seconds=30,
        )
        assert config.requests_per_minute == 30
        assert config.requests_per_hour == 500
        assert config.burst_limit == 5
        assert config.window_size_seconds == 30


class TestRateLimitResult:
    """Tests pour RateLimitResult."""

    def test_allowed_result(self) -> None:
        """Test un résultat autorisé."""
        result = RateLimitResult(
            allowed=True,
            remaining=5,
            reset_time=1234567890.0,
        )
        assert result.allowed is True
        assert result.remaining == 5
        assert result.reset_time == 1234567890.0
        assert result.retry_after is None

    def test_blocked_result(self) -> None:
        """Test un résultat bloqué."""
        result = RateLimitResult(
            allowed=False,
            remaining=0,
            reset_time=1234567890.0,
            retry_after=30,
        )
        assert result.allowed is False
        assert result.remaining == 0
        assert result.reset_time == 1234567890.0
        assert result.retry_after == 30


class TestDefaultQuotas:
    """Tests pour la configuration des quotas par défaut."""

    def test_configure_default_quotas(self) -> None:
        """Test la configuration des quotas par défaut."""
        # Create a fresh quota manager for testing
        test_manager = QuotaManager()

        # Set quotas manually to test the configuration
        test_manager.set_quota("default", "requests_per_minute", 60)
        test_manager.set_quota("default", "requests_per_hour", 1000)
        test_manager.set_quota("default", "chat_requests_per_hour", 100)
        test_manager.set_quota("default", "retrieval_requests_per_hour", 500)

        assert test_manager.get_quota("default", "requests_per_minute") == 60
        assert test_manager.get_quota("default", "requests_per_hour") == 1000
        assert test_manager.get_quota("default", "chat_requests_per_hour") == 100
        assert test_manager.get_quota("default", "retrieval_requests_per_hour") == 500


class TestIntegration:
    """Tests d'intégration pour le rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limit_with_metrics(self) -> None:
        """Test que les métriques sont émises lors des blocages."""
        with patch("backend.apigw.rate_limit.RATE_LIMIT_BLOCKS") as mock_metrics:
            config = RateLimitConfig(requests_per_minute=1)
            middleware = TenantRateLimitMiddleware(Mock(), config=config)

            # First request should succeed
            request1 = self.create_mock_request()

            async def call_next1(req: Request) -> Response:
                return Response("OK", status_code=200)

            await middleware.dispatch(request1, call_next1)
            mock_metrics.labels.assert_not_called()

            # Second request should be blocked and emit metrics
            request2 = self.create_mock_request()

            async def call_next2(req: Request) -> Response:
                return Response("OK", status_code=200)

            await middleware.dispatch(request2, call_next2)
            mock_metrics.labels.assert_called_once()

    def create_mock_request(self, path: str = "/v1/test") -> Request:
        """Create a mock request for testing."""
        request = Mock(spec=Request)
        request.url.path = path
        request.method = "GET"
        request.headers = {}
        request.state = Mock()
        request.state.trace_id = "test-trace-id"
        request.state.user = None  # Ensure no user state by default
        return request
