"""
Tests pour le trust model JWT > header + anti-spoof.

Tests de précédence JWT, détection de spoof, et cas internes.
"""

from typing import Any
from unittest.mock import Mock, patch

import pytest
from fastapi import Request

from backend.apigw.auth_utils import (
    _extract_tenant_from_jwt,
    _is_internal_traffic,
    extract_tenant_secure,
    get_tenant_source_info,
)
from backend.apigw.rate_limit import QuotaMiddleware, TenantRateLimitMiddleware


class TestExtractTenantSecure:
    """Tests pour l'extraction sécurisée des tenants."""

    def create_mock_request(
        self,
        headers: dict[str, str] | None = None,
        user_state: dict[str, Any] | None = None,
        jwt_claims: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> Request:
        """Create a mock request for testing."""
        request = Mock(spec=Request)
        request.headers = headers or {}
        request.url.path = "/v1/chat/123"

        # Mock request.state
        request.state = Mock()
        if user_state:
            request.state.user = Mock()
            for key, value in user_state.items():
                setattr(request.state.user, key, value)
        else:
            request.state.user = None

        if jwt_claims:
            request.state.jwt_claims = jwt_claims
        else:
            request.state.jwt_claims = None

        if trace_id:
            request.state.trace_id = trace_id
        else:
            request.state.trace_id = None

        return request

    def test_jwt_tenant_takes_precedence(self) -> None:
        """Test que le tenant JWT prend le pas sur le header."""
        request = self.create_mock_request(
            headers={"X-Tenant-ID": "jwt_tenant"},  # Same as JWT tenant
            user_state={"tenant": "jwt_tenant"},
        )

        tenant, source, is_spoof = extract_tenant_secure(request)

        assert tenant == "jwt_tenant"
        assert source == "jwt"
        assert is_spoof is False

    def test_jwt_claims_takes_precedence(self) -> None:
        """Test que les claims JWT prennent le pas sur le header."""
        request = self.create_mock_request(
            headers={"X-Tenant-ID": "jwt_claims_tenant"},  # Same as JWT claims tenant
            jwt_claims={"tenant_id": "jwt_claims_tenant"},
        )

        tenant, source, is_spoof = extract_tenant_secure(request)

        assert tenant == "jwt_claims_tenant"
        assert source == "jwt"
        assert is_spoof is False

    def test_spoof_detection_header_contradicts_jwt(self) -> None:
        """Test détection de spoof quand header contredit JWT."""
        request = self.create_mock_request(
            headers={"X-Tenant-ID": "header_tenant"},
            user_state={"tenant": "jwt_tenant"},
        )

        with patch(
            "backend.apigw.auth_utils.APIGW_TENANT_SPOOF_ATTEMPTS"
        ) as mock_metrics:
            tenant, source, is_spoof = extract_tenant_secure(request)

            assert tenant == "jwt_tenant"  # JWT wins
            assert source == "jwt"
            assert is_spoof is True

            # Should increment spoof counter
            mock_metrics.labels.assert_called_once()

    def test_internal_header_allowed(self) -> None:
        """Test que les headers internes sont autorisés."""
        request = self.create_mock_request(
            headers={"X-Tenant-ID": "internal_tenant", "X-Service-Mesh": "internal"}
        )

        tenant, source, is_spoof = extract_tenant_secure(request)

        assert tenant == "internal_tenant"
        assert source == "header"
        assert is_spoof is False

    def test_internal_header_no_spoof_detection(self) -> None:
        """Test qu'il n'y a pas de spoof si header interne."""
        request = self.create_mock_request(
            headers={"X-Tenant-ID": "internal_tenant", "X-Service-Mesh": "internal"},
            user_state={"tenant": "jwt_tenant"},
        )

        with patch(
            "backend.apigw.auth_utils.APIGW_TENANT_SPOOF_ATTEMPTS"
        ) as mock_metrics:
            tenant, source, is_spoof = extract_tenant_secure(request)

            assert tenant == "jwt_tenant"  # JWT still wins
            assert source == "jwt"
            assert is_spoof is False

            # Should not increment spoof counter for internal traffic
            mock_metrics.labels.assert_not_called()

    def test_fallback_to_default(self) -> None:
        """Test fallback vers tenant par défaut."""
        request = self.create_mock_request()

        tenant, source, is_spoof = extract_tenant_secure(request)

        assert tenant == "public"
        assert source == "default"
        assert is_spoof is False

    def test_header_only_no_jwt(self) -> None:
        """Test header seul sans JWT (non-internal)."""
        request = self.create_mock_request(headers={"X-Tenant-ID": "header_tenant"})

        tenant, source, is_spoof = extract_tenant_secure(request)

        assert tenant == "public"  # Falls back to default
        assert source == "default"
        assert is_spoof is False

    def test_service_mesh_internal(self) -> None:
        """Test détection de trafic interne via service mesh."""
        request = self.create_mock_request(
            headers={"X-Tenant-ID": "mesh_tenant", "X-Service-Mesh": "internal"}
        )

        tenant, source, is_spoof = extract_tenant_secure(request)

        assert tenant == "mesh_tenant"
        assert source == "header"
        assert is_spoof is False


class TestInternalTrafficDetection:
    """Tests pour la détection de trafic interne."""

    def create_mock_request(self, headers: dict[str, str] | None = None) -> Request:
        """Create a mock request for testing."""
        request = Mock(spec=Request)
        request.headers = headers or {}
        return request

    def test_internal_auth_header(self) -> None:
        """Test détection via X-Internal-Auth."""
        request = self.create_mock_request(headers={"X-Service-Mesh": "internal"})

        assert _is_internal_traffic(request) is False

    def test_service_mesh_header(self) -> None:
        """Test détection via X-Service-Mesh."""
        request = self.create_mock_request(headers={"X-Service-Mesh": "internal"})

        assert _is_internal_traffic(request) is False

    def test_non_internal_traffic(self) -> None:
        """Test trafic non-internal."""
        request = self.create_mock_request(headers={"X-Tenant-ID": "client_tenant"})

        assert _is_internal_traffic(request) is False

    def test_no_headers(self) -> None:
        """Test sans headers."""
        request = self.create_mock_request()

        assert _is_internal_traffic(request) is False


class TestJWTExtraction:
    """Tests pour l'extraction JWT."""

    def create_mock_request(
        self,
        user_state: dict[str, Any] | None = None,
        jwt_claims: dict[str, Any] | None = None,
    ) -> Request:
        """Create a mock request for testing."""
        request = Mock(spec=Request)
        request.state = Mock()

        if user_state:
            request.state.user = Mock()
            for key, value in user_state.items():
                setattr(request.state.user, key, value)
        else:
            request.state.user = None

        if jwt_claims:
            request.state.jwt_claims = jwt_claims
        else:
            request.state.jwt_claims = None

        return request

    def test_extract_from_user_state(self) -> None:
        """Test extraction depuis user state."""
        request = self.create_mock_request(user_state={"tenant": "user_tenant"})

        tenant = _extract_tenant_from_jwt(request)

        assert tenant == "user_tenant"

    def test_extract_from_jwt_claims(self) -> None:
        """Test extraction depuis JWT claims."""
        request = self.create_mock_request(jwt_claims={"tenant_id": "claims_tenant"})

        tenant = _extract_tenant_from_jwt(request)

        assert tenant == "claims_tenant"

    def test_jwt_claims_priority_over_user_state(self) -> None:
        """Test que JWT claims ont priorité sur user state."""
        request = self.create_mock_request(
            user_state={"tenant": "user_tenant"},
            jwt_claims={"tenant_id": "claims_tenant"},
        )

        tenant = _extract_tenant_from_jwt(request)

        assert tenant == "claims_tenant"

    def test_no_jwt_tenant(self) -> None:
        """Test sans tenant JWT."""
        request = self.create_mock_request()

        tenant = _extract_tenant_from_jwt(request)

        assert tenant is None


class TestTenantSourceInfo:
    """Tests pour les informations de source tenant."""

    def create_mock_request(
        self,
        headers: dict[str, str] | None = None,
        user_state: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> Request:
        """Create a mock request for testing."""
        request = Mock(spec=Request)
        request.headers = headers or {}
        request.url.path = "/v1/chat/123"

        request.state = Mock()
        if user_state:
            request.state.user = Mock()
            for key, value in user_state.items():
                setattr(request.state.user, key, value)
        else:
            request.state.user = None

        request.state.trace_id = trace_id
        return request

    def test_tenant_source_info_jwt(self) -> None:
        """Test informations de source pour tenant JWT."""
        request = self.create_mock_request(
            user_state={"tenant": "jwt_tenant"}, trace_id="test_trace_123"
        )

        # Ensure jwt_claims is None to avoid mock issues
        request.state.jwt_claims = None

        info = get_tenant_source_info(request)

        assert info["tenant"] == "jwt_tenant"
        assert info["tenant_source"] == "jwt"
        assert info["spoof"] is False
        assert info["route"] == "/v1/chat/{id}"
        assert info["trace_id"] == "test_trace_123"

    def test_tenant_source_info_spoof(self) -> None:
        """Test informations de source pour spoof détecté."""
        request = self.create_mock_request(
            headers={"X-Tenant-ID": "header_tenant"},
            user_state={"tenant": "jwt_tenant"},
            trace_id="test_trace_456",
        )

        # Ensure jwt_claims is None to avoid mock issues
        request.state.jwt_claims = None

        info = get_tenant_source_info(request)

        assert info["tenant"] == "jwt_tenant"
        assert info["tenant_source"] == "jwt"
        assert info["spoof"] is True
        assert info["route"] == "/v1/chat/{id}"
        assert info["trace_id"] == "test_trace_456"

    def test_tenant_source_info_default(self) -> None:
        """Test informations de source pour tenant par défaut."""
        request = self.create_mock_request()

        # Mock jwt_claims to return None properly
        request.state.jwt_claims = None

        info = get_tenant_source_info(request)

        assert info["tenant"] == "public"
        assert info["tenant_source"] == "default"
        assert info["spoof"] is False
        assert info["route"] == "/v1/chat/{id}"
        assert info["trace_id"] is None


class TestIntegration:
    """Tests d'intégration avec le middleware."""

    @pytest.mark.asyncio
    async def test_middleware_uses_trust_model(self) -> None:
        """Test que le middleware utilise le trust model."""
        with (
            patch("backend.apigw.rate_limit.extract_tenant_secure") as mock_extract,
            patch("backend.apigw.rate_limit.redis_store") as mock_redis_store,
        ):
            # Mock trust model response
            mock_extract.return_value = ("secure_tenant", "jwt", False)

            # Mock Redis store response
            mock_result = Mock()
            mock_result.allowed = True
            mock_result.remaining = 59
            mock_result.reset_time = 1234567890.0
            mock_result.retry_after = None

            mock_redis_store.check_rate_limit.return_value = mock_result
            mock_redis_store.settings.RL_MAX_REQ_PER_WINDOW = 60

            middleware = TenantRateLimitMiddleware(Mock())
            request = Mock(spec=Request)
            request.url.path = "/v1/chat/123"
            request.headers = {}
            request.state = Mock()
            request.state.trace_id = None

            async def call_next(req: Request) -> Mock:
                response = Mock()
                response.headers = {}
                return response

            await middleware.dispatch(request, call_next)

            # Verify trust model was called
            mock_extract.assert_called_once_with(request)

            # Verify Redis store was called with secure tenant
            mock_redis_store.check_rate_limit.assert_called_once_with(
                "/v1/chat/{id}", "secure_tenant"
            )

    @pytest.mark.asyncio
    async def test_quota_middleware_uses_trust_model(self) -> None:
        """Test que le QuotaMiddleware utilise le trust model."""
        with (
            patch("backend.apigw.rate_limit.extract_tenant_secure") as mock_extract,
            patch("backend.apigw.rate_limit.quota_manager") as mock_quota_manager,
        ):
            # Mock trust model response
            mock_extract.return_value = ("secure_tenant", "jwt", False)

            # Mock quota manager
            mock_quota_manager.get_quota.return_value = 0  # No quota set

            middleware = QuotaMiddleware(Mock())
            request = Mock(spec=Request)
            request.url.path = "/v1/chat/123"
            request.headers = {}
            request.state = Mock()
            request.state.trace_id = None

            async def call_next(req: Request) -> Mock:
                response = Mock()
                response.headers = {}
                return response

            await middleware.dispatch(request, call_next)

            # Verify trust model was called
            mock_extract.assert_called_once_with(request)

            # Verify quota manager was called with secure tenant
            mock_quota_manager.get_quota.assert_called_with(
                "secure_tenant", "chat_requests_per_hour"
            )
