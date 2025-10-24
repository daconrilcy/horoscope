"""Tests unitaires pour le rate limiting et quotas par tenant.

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
from backend.app.metrics import normalize_route

# Constantes pour les tests
HTTP_OK = 200
HTTP_TOO_MANY_REQUESTS = 429
DEFAULT_REQUESTS_PER_MINUTE = 60
DEFAULT_REQUESTS_PER_HOUR = 1000
DEFAULT_BURST_LIMIT = 10
DEFAULT_WINDOW_SIZE = 60
TEST_RESET_TIME = 1234567890.0
TEST_RETRY_AFTER = 30
TEST_REMAINING_REQUESTS = 59
TEST_QUOTA_LIMIT = 100
TEST_CHAT_QUOTA = 100
TEST_RETRIEVAL_QUOTA = 500


class TestSlidingWindowRateLimiter:
    """Tests pour SlidingWindowRateLimiter."""

    def test_rate_limit_allowed(self) -> None:
        """Test que les requêtes dans la limite sont autorisées."""
        config = RateLimitConfig(requests_per_minute=5)
        limiter = SlidingWindowRateLimiter(config)

        result = limiter.check_rate_limit("tenant1")
        assert result.allowed is True
        assert result.remaining == config.requests_per_minute - 1  # requests_per_minute - 1
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

    def setup_method(self) -> None:
        """Configure l'environnement de test."""
        # Mock extract_tenant_secure for all tests in this class
        self.extract_patcher = patch("backend.apigw.rate_limit.extract_tenant_secure")
        self.mock_extract = self.extract_patcher.start()
        self.mock_extract.return_value = ("default", "default", False)

    def teardown_method(self) -> None:
        """Cleanup test environment."""
        self.extract_patcher.stop()

    def create_mock_request(self, path: str = "/v1/test", method: str = "GET") -> Request:
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
        assert response.status_code == HTTP_OK

    @pytest.mark.asyncio
    async def test_health_endpoints_skipped(self) -> None:
        """Test que les endpoints de santé sont ignorés."""
        middleware = TenantRateLimitMiddleware(Mock())
        request = self.create_mock_request("/health")

        async def call_next(req: Request) -> Response:
            return Response("OK", status_code=200)

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == HTTP_OK

    @pytest.mark.asyncio
    async def test_rate_limit_headers_added(self) -> None:
        """Test que les headers de rate limit sont ajoutés."""
        middleware = TenantRateLimitMiddleware(Mock())
        request = self.create_mock_request()

        async def call_next(req: Request) -> Response:
            return Response("OK", status_code=200)

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == HTTP_OK
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_response(self) -> None:
        """Test la réponse 429 quand la limite est dépassée."""
        with patch("backend.apigw.rate_limit.redis_store") as mock_redis_store:
            # Mock Redis store to block second request
            mock_result1 = Mock()
            mock_result1.allowed = True
            mock_result1.remaining = 59
            mock_result1.reset_time = 1234567890.0
            mock_result1.retry_after = None

            mock_result2 = Mock()
            mock_result2.allowed = False
            mock_result2.remaining = 0
            mock_result2.reset_time = 1234567890.0
            mock_result2.retry_after = 30

            mock_redis_store.check_rate_limit.side_effect = [mock_result1, mock_result2]
            mock_redis_store.settings.RL_MAX_REQ_PER_WINDOW = 60

            middleware = TenantRateLimitMiddleware(Mock())

            # First request should succeed
            request1 = self.create_mock_request()

            async def call_next1(req: Request) -> Response:
                return Response("OK", status_code=200)

            response1 = await middleware.dispatch(request1, call_next1)
            assert response1.status_code == HTTP_OK

            # Second request should be blocked
            request2 = self.create_mock_request()

            async def call_next2(req: Request) -> Response:
                return Response("OK", status_code=200)

            response2 = await middleware.dispatch(request2, call_next2)
            assert response2.status_code == HTTP_TOO_MANY_REQUESTS
            assert "Retry-After" in response2.headers

    def test_tenant_extraction_from_header(self) -> None:
        """Test l'extraction du tenant depuis les headers."""
        # Override mock for this specific test
        self.mock_extract.return_value = ("test-tenant", "header", False)

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
        # Override mock for this specific test
        self.mock_extract.return_value = ("user-tenant", "jwt", False)

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

        assert manager.get_quota("tenant1", "requests") == TEST_QUOTA_LIMIT
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

    def setup_method(self) -> None:
        """Configure l'environnement de test."""
        # Mock extract_tenant_secure for all tests in this class
        self.extract_patcher = patch("backend.apigw.rate_limit.extract_tenant_secure")
        self.mock_extract = self.extract_patcher.start()
        self.mock_extract.return_value = ("default", "default", False)

    def teardown_method(self) -> None:
        """Cleanup test environment."""
        self.extract_patcher.stop()

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
        assert response.status_code == HTTP_OK

    @pytest.mark.asyncio
    async def test_health_endpoints_skipped(self) -> None:
        """Test que les endpoints de santé sont ignorés."""
        middleware = QuotaMiddleware(Mock())
        request = self.create_mock_request("/health")

        async def call_next(req: Request) -> Response:
            return Response("OK", status_code=200)

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == HTTP_OK

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
        assert response.status_code == HTTP_OK

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
        assert response.status_code == HTTP_OK


class TestRateLimitConfig:
    """Tests pour RateLimitConfig."""

    def test_default_config(self) -> None:
        """Test la configuration par défaut."""
        config = RateLimitConfig()
        assert config.requests_per_minute == DEFAULT_REQUESTS_PER_MINUTE
        assert config.requests_per_hour == DEFAULT_REQUESTS_PER_HOUR
        assert config.burst_limit == DEFAULT_BURST_LIMIT
        assert config.window_size_seconds == DEFAULT_WINDOW_SIZE

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
        assert result.reset_time == TEST_RESET_TIME
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
        assert result.reset_time == TEST_RESET_TIME
        assert result.retry_after == TEST_RETRY_AFTER


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

        assert (
            test_manager.get_quota("default", "requests_per_minute") == DEFAULT_REQUESTS_PER_MINUTE
        )
        assert test_manager.get_quota("default", "requests_per_hour") == DEFAULT_REQUESTS_PER_HOUR
        assert test_manager.get_quota("default", "chat_requests_per_hour") == TEST_CHAT_QUOTA
        assert (
            test_manager.get_quota("default", "retrieval_requests_per_hour") == TEST_RETRIEVAL_QUOTA
        )


class TestRouteNormalization:
    """Tests pour la normalisation des routes."""

    def test_normalize_route_with_id(self) -> None:
        """Test normalisation avec ID numérique."""
        assert normalize_route("/v1/chat/123") == "/v1/chat/{id}"
        assert normalize_route("/v1/chat/456") == "/v1/chat/{id}"

    def test_normalize_route_with_uuid(self) -> None:
        """Test normalisation avec UUID."""
        uuid_path = "/v1/chat/550e8400-e29b-41d4-a716-446655440000"
        assert normalize_route(uuid_path) == "/v1/chat/{id}"

    def test_normalize_route_with_query_params(self) -> None:
        """Test normalisation avec paramètres de requête."""
        assert normalize_route("/v1/chat/123?foo=bar&baz=qux") == "/v1/chat/{id}"

    def test_normalize_route_without_slash(self) -> None:
        """Test normalisation sans slash initial."""
        assert normalize_route("v1/chat/123") == "/v1/chat/{id}"

    def test_normalize_route_no_params(self) -> None:
        """Test normalisation sans paramètres."""
        assert normalize_route("/v1/health") == "/v1/health"
        assert normalize_route("/metrics") == "/metrics"

    def test_normalize_route_multiple_ids(self) -> None:
        """Test normalisation avec plusieurs IDs."""
        assert normalize_route("/v1/chat/123/message/456") == "/v1/chat/{id}/message/{id}"


class TestIntegration:
    """Tests d'intégration pour le rate limiting."""

    def setup_method(self) -> None:
        """Configure l'environnement de test."""
        # Mock extract_tenant_secure for all tests in this class
        self.extract_patcher = patch("backend.apigw.rate_limit.extract_tenant_secure")
        self.mock_extract = self.extract_patcher.start()
        self.mock_extract.return_value = ("default", "default", False)

    def teardown_method(self) -> None:
        """Cleanup test environment."""
        self.extract_patcher.stop()

    @pytest.mark.asyncio
    async def test_metrics_increment_correctly(self) -> None:
        """Test que les métriques s'incrémentent correctement."""
        with (
            patch("backend.apigw.rate_limit.redis_store") as mock_redis_store,
            patch("backend.apigw.rate_limit.APIGW_RATE_LIMIT_DECISIONS") as mock_decisions,
            patch("backend.apigw.rate_limit.APIGW_RATE_LIMIT_BLOCKS") as mock_blocks,
            patch("backend.apigw.rate_limit.APIGW_RATE_LIMIT_EVALUATION_TIME") as mock_eval_time,
        ):
            # Mock Redis store responses
            mock_result1 = Mock()
            mock_result1.allowed = True
            mock_result1.remaining = 59
            mock_result1.reset_time = 1234567890.0
            mock_result1.retry_after = None

            mock_result2 = Mock()
            mock_result2.allowed = False
            mock_result2.remaining = 0
            mock_result2.reset_time = 1234567890.0
            mock_result2.retry_after = 30

            mock_redis_store.check_rate_limit.side_effect = [mock_result1, mock_result2]
            mock_redis_store.settings.RL_MAX_REQ_PER_WINDOW = 60

            middleware = TenantRateLimitMiddleware(Mock())

            # First request - should allow
            request1 = self.create_mock_request("/v1/chat/123")

            async def call_next1(req: Request) -> Response:
                return Response("OK", status_code=200)

            await middleware.dispatch(request1, call_next1)

            # Check decisions metric
            mock_decisions.labels.assert_called_with(route="/v1/chat/{id}", result="allow")
            mock_decisions.labels().inc.assert_called_once()

            # Check evaluation time metric
            mock_eval_time.labels.assert_called_with(route="/v1/chat/{id}")
            mock_eval_time.labels().observe.assert_called_once()

            # Reset mocks
            mock_decisions.reset_mock()
            mock_blocks.reset_mock()
            mock_eval_time.reset_mock()

            # Second request - should block
            request2 = self.create_mock_request("/v1/chat/456")

            async def call_next2(req: Request) -> Response:
                return Response("OK", status_code=200)

            response = await middleware.dispatch(request2, call_next2)

            # Check block metrics
            mock_decisions.labels.assert_called_with(route="/v1/chat/{id}", result="block")
            mock_blocks.labels.assert_called_with(route="/v1/chat/{id}", reason="rate_exceeded")

            # Check response
            assert response.status_code == HTTP_TOO_MANY_REQUESTS
            assert "Retry-After" in response.headers
            retry_after = int(response.headers["Retry-After"])
            assert retry_after >= 1  # At least 1 second

    @pytest.mark.asyncio
    async def test_quota_metrics_increment(self) -> None:
        """Test que les métriques de quota s'incrémentent quand quota est dépassé."""
        with (
            patch("backend.apigw.rate_limit.quota_manager") as mock_quota_manager,
            patch("backend.apigw.rate_limit.APIGW_RATE_LIMIT_DECISIONS") as mock_decisions,
            patch("backend.apigw.rate_limit.APIGW_RATE_LIMIT_BLOCKS") as mock_blocks,
        ):
            # Mock quota exceeded for chat endpoint (non-zero means quota is set and exceeded)
            # Based on current logic: if limit != 0, then block
            mock_quota_manager.get_quota.return_value = 1  # Quota set but exceeded

            middleware = QuotaMiddleware(Mock())
            request = self.create_mock_request("/v1/chat/123")  # Chat endpoint

            async def call_next(req: Request) -> Response:
                return Response("OK", status_code=200)

            response = await middleware.dispatch(request, call_next)

            # Check metrics
            mock_decisions.labels.assert_called_with(route="/v1/chat/{id}", result="block")
            mock_blocks.labels.assert_called_with(route="/v1/chat/{id}", reason="quota_exceeded")

            # Check response
            assert response.status_code == HTTP_TOO_MANY_REQUESTS
            assert "Retry-After" in response.headers

    @pytest.mark.asyncio
    async def test_redis_store_integration(self) -> None:
        """Test intégration avec le store Redis."""
        with patch("backend.apigw.rate_limit.redis_store") as mock_redis_store:
            # Mock Redis store response
            mock_result = Mock()
            mock_result.allowed = True
            mock_result.remaining = 59
            mock_result.reset_time = 1234567890.0
            mock_result.retry_after = None

            mock_redis_store.check_rate_limit.return_value = mock_result
            mock_redis_store.settings.RL_MAX_REQ_PER_WINDOW = 60

            middleware = TenantRateLimitMiddleware(Mock())
            request = self.create_mock_request("/v1/chat/123")

            async def call_next(req: Request) -> Response:
                return Response("OK", status_code=200)

            response = await middleware.dispatch(request, call_next)

            # Vérifier que Redis store a été appelé
            mock_redis_store.check_rate_limit.assert_called_once_with("/v1/chat/{id}", "default")

            # Vérifier la réponse
            assert response.status_code == HTTP_OK
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert "X-RateLimit-Reset" in response.headers

    @pytest.mark.asyncio
    async def test_redis_store_blocked(self) -> None:
        """Test blocage via Redis store."""
        with patch("backend.apigw.rate_limit.redis_store") as mock_redis_store:
            # Mock Redis store response - blocked
            mock_result = Mock()
            mock_result.allowed = False
            mock_result.remaining = 0
            mock_result.reset_time = 1234567890.0
            mock_result.retry_after = 30

            mock_redis_store.check_rate_limit.return_value = mock_result

            middleware = TenantRateLimitMiddleware(Mock())
            request = self.create_mock_request("/v1/chat/123")

            async def call_next(req: Request) -> Response:
                return Response("OK", status_code=200)

            response = await middleware.dispatch(request, call_next)

            # Vérifier que la requête a été bloquée
            assert response.status_code == HTTP_TOO_MANY_REQUESTS
            assert "Retry-After" in response.headers
            assert response.headers["Retry-After"] == "30"

    @pytest.mark.asyncio
    async def test_redis_store_fail_open(self) -> None:
        """Test fail-open quand Redis est indisponible."""
        with patch("backend.apigw.rate_limit.redis_store") as mock_redis_store:
            # Mock Redis store fail-open
            mock_result = Mock()
            mock_result.allowed = True  # Fail-open allows request
            mock_result.remaining = 59
            mock_result.reset_time = 1234567890.0
            mock_result.retry_after = None

            mock_redis_store.check_rate_limit.return_value = mock_result
            mock_redis_store.settings.RL_MAX_REQ_PER_WINDOW = 60

            middleware = TenantRateLimitMiddleware(Mock())
            request = self.create_mock_request("/v1/chat/123")

            async def call_next(req: Request) -> Response:
                return Response("OK", status_code=200)

            response = await middleware.dispatch(request, call_next)

            # Vérifier que la requête a été autorisée (fail-open)
            assert response.status_code == HTTP_OK

    @pytest.mark.asyncio
    async def test_rate_limit_with_metrics(self) -> None:
        """Test que les métriques sont émises lors des blocages."""
        with (
            patch("backend.apigw.rate_limit.redis_store") as mock_redis_store,
            patch("backend.apigw.rate_limit.APIGW_RATE_LIMIT_DECISIONS") as mock_metrics,
        ):
            # Mock Redis store responses
            mock_result1 = Mock()
            mock_result1.allowed = True
            mock_result1.remaining = 59
            mock_result1.reset_time = 1234567890.0
            mock_result1.retry_after = None

            mock_result2 = Mock()
            mock_result2.allowed = False
            mock_result2.remaining = 0
            mock_result2.reset_time = 1234567890.0
            mock_result2.retry_after = 30

            mock_redis_store.check_rate_limit.side_effect = [mock_result1, mock_result2]
            mock_redis_store.settings.RL_MAX_REQ_PER_WINDOW = 60

            middleware = TenantRateLimitMiddleware(Mock())

            # First request should succeed
            request1 = self.create_mock_request()

            async def call_next1(req: Request) -> Response:
                return Response("OK", status_code=200)

            await middleware.dispatch(request1, call_next1)
            # First request should emit allow metric
            mock_metrics.labels.assert_called_with(route="/v1/test", result="allow")
            mock_metrics.labels().inc.assert_called_once()

            # Reset mock for second request
            mock_metrics.reset_mock()

            # Second request should be blocked and emit block metrics
            request2 = self.create_mock_request()

            async def call_next2(req: Request) -> Response:
                return Response("OK", status_code=200)

            await middleware.dispatch(request2, call_next2)
            # Should emit block metric
            mock_metrics.labels.assert_called_with(route="/v1/test", result="block")

    def create_mock_request(self, path: str = "/v1/test") -> Request:
        """Create a mock request for testing."""
        request = Mock(spec=Request)
        request.url.path = path
        request.method = "GET"
        request.headers = {}
        request.state = Mock()
        request.state.trace_id = "test-trace-id"
        request.state.user = None  # Ensure no user state by default
        request.state.jwt_claims = None  # Ensure jwt_claims is None by default
        return request
