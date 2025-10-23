"""
Tests pour la vérification HMAC des headers internes.

Tests de signature HMAC, vérification timestamp, et prévention replay.
"""

import time
from unittest.mock import Mock, patch

from fastapi import Request

from backend.apigw.auth_utils import extract_tenant_secure
from backend.apigw.internal_auth import (
    InternalAuthVerifier,
    verify_internal_traffic,
)


class TestInternalAuthVerifier:
    """Tests pour le vérificateur HMAC."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.verifier = InternalAuthVerifier()
        # Mock settings for testing
        self.verifier.settings = Mock()
        self.verifier.settings.INTERNAL_AUTH_KEY = "test-secret-key"
        self.verifier.settings.INTERNAL_AUTH_KEY_V2 = "test-secret-key-v2"

    def create_mock_request(
        self,
        headers: dict[str, str] | None = None,
        path: str = "/v1/test",
        method: str = "GET",
    ) -> Request:
        """Create a mock request for testing."""
        request = Mock(spec=Request)
        request.headers = headers or {}
        request.url.path = path
        request.method = method
        request.state = Mock()
        request.state.trace_id = "test-trace-123"
        return request

    def test_verify_internal_auth_valid(self) -> None:
        """Test verification with valid HMAC signature."""
        timestamp = int(time.time())
        nonce = "test-nonce-123"
        path = "/v1/test"
        method = "GET"

        # Generate valid signature
        signature = self.verifier._generate_signature(
            "v1", timestamp, nonce, path, method
        )

        request = self.create_mock_request(
            headers={
                "X-Internal-Auth": signature,
                "X-Auth-Version": "v1",
                "X-Auth-Timestamp": str(timestamp),
                "X-Auth-Nonce": nonce,
            },
            path=path,
            method=method,
        )

        result = self.verifier.verify_internal_auth(request)
        assert result is True

    def test_verify_internal_auth_invalid_signature(self) -> None:
        """Test verification with invalid HMAC signature."""
        timestamp = int(time.time())
        nonce = "test-nonce-123"

        request = self.create_mock_request(
            headers={
                "X-Internal-Auth": "invalid-signature",
                "X-Auth-Version": "v1",
                "X-Auth-Timestamp": str(timestamp),
                "X-Auth-Nonce": nonce,
            }
        )

        result = self.verifier.verify_internal_auth(request)
        assert result is False

    def test_verify_internal_auth_missing_headers(self) -> None:
        """Test verification with missing headers."""
        request = self.create_mock_request(
            headers={
                "X-Internal-Auth": "some-signature",
                # Missing other required headers
            }
        )

        result = self.verifier.verify_internal_auth(request)
        assert result is False

    def test_verify_internal_auth_timestamp_skew(self) -> None:
        """Test verification with timestamp skew."""
        # Use timestamp 10 minutes in the past
        timestamp = int(time.time()) - 600
        nonce = "test-nonce-123"

        signature = self.verifier._generate_signature(
            "v1", timestamp, nonce, "/v1/test", "GET"
        )

        request = self.create_mock_request(
            headers={
                "X-Internal-Auth": signature,
                "X-Auth-Version": "v1",
                "X-Auth-Timestamp": str(timestamp),
                "X-Auth-Nonce": nonce,
            }
        )

        result = self.verifier.verify_internal_auth(request)
        assert result is False

    def test_verify_internal_auth_nonce_replay(self) -> None:
        """Test verification with replayed nonce."""
        timestamp = int(time.time())
        nonce = "test-nonce-replay"

        # First use - should succeed
        signature = self.verifier._generate_signature(
            "v1", timestamp, nonce, "/v1/test", "GET"
        )

        request1 = self.create_mock_request(
            headers={
                "X-Internal-Auth": signature,
                "X-Auth-Version": "v1",
                "X-Auth-Timestamp": str(timestamp),
                "X-Auth-Nonce": nonce,
            }
        )

        result1 = self.verifier.verify_internal_auth(request1)
        assert result1 is True

        # Second use with same nonce - should fail
        request2 = self.create_mock_request(
            headers={
                "X-Internal-Auth": signature,
                "X-Auth-Version": "v1",
                "X-Auth-Timestamp": str(timestamp),
                "X-Auth-Nonce": nonce,
            }
        )

        result2 = self.verifier.verify_internal_auth(request2)
        assert result2 is False

    def test_verify_internal_auth_version_v2(self) -> None:
        """Test verification with version v2."""
        timestamp = int(time.time())
        nonce = "test-nonce-v2"

        signature = self.verifier._generate_signature(
            "v2", timestamp, nonce, "/v1/test", "GET"
        )

        request = self.create_mock_request(
            headers={
                "X-Internal-Auth": signature,
                "X-Auth-Version": "v2",
                "X-Auth-Timestamp": str(timestamp),
                "X-Auth-Nonce": nonce,
            }
        )

        result = self.verifier.verify_internal_auth(request)
        assert result is True

    def test_verify_internal_auth_unknown_version(self) -> None:
        """Test verification with unknown version."""
        timestamp = int(time.time())
        nonce = "test-nonce-unknown"

        request = self.create_mock_request(
            headers={
                "X-Internal-Auth": "some-signature",
                "X-Auth-Version": "v3",  # Unknown version
                "X-Auth-Timestamp": str(timestamp),
                "X-Auth-Nonce": nonce,
            }
        )

        result = self.verifier.verify_internal_auth(request)
        assert result is False

    def test_generate_signature(self) -> None:
        """Test signature generation."""
        signature1 = self.verifier._generate_signature(
            "v1", 1234567890, "nonce1", "/v1/test", "GET"
        )
        signature2 = self.verifier._generate_signature(
            "v1", 1234567890, "nonce1", "/v1/test", "GET"
        )

        # Same inputs should produce same signature
        assert signature1 == signature2

        # Different inputs should produce different signatures
        signature3 = self.verifier._generate_signature(
            "v1",
            1234567891,
            "nonce1",
            "/v1/test",
            "GET",  # Different timestamp
        )
        assert signature1 != signature3

    def test_nonce_cache_cleanup(self) -> None:
        """Test nonce cache cleanup."""
        # Add expired nonce
        old_time = time.time() - 700  # 11 minutes ago
        self.verifier._nonce_cache["expired-nonce"] = old_time

        # Add current nonce
        current_time = time.time()
        self.verifier._nonce_cache["current-nonce"] = current_time

        # Cache new nonce (should trigger cleanup)
        self.verifier._cache_nonce("new-nonce")

        # Expired nonce should be removed
        assert "expired-nonce" not in self.verifier._nonce_cache
        # Current nonce should still be there
        assert "current-nonce" in self.verifier._nonce_cache
        # New nonce should be added
        assert "new-nonce" in self.verifier._nonce_cache


class TestVerifyInternalTraffic:
    """Tests pour la fonction de vérification globale."""

    def create_mock_request(
        self,
        headers: dict[str, str] | None = None,
        path: str = "/v1/test",
        method: str = "GET",
    ) -> Request:
        """Create a mock request for testing."""
        request = Mock(spec=Request)
        request.headers = headers or {}
        request.url.path = path
        request.method = method
        request.state = Mock()
        request.state.trace_id = "test-trace-123"
        return request

    @patch("backend.apigw.internal_auth.internal_auth_verifier")
    def test_verify_internal_traffic_with_hmac(self, mock_verifier: Mock) -> None:
        """Test verification with HMAC headers."""
        mock_verifier.verify_internal_auth.return_value = True

        request = self.create_mock_request(
            headers={
                "X-Internal-Auth": "some-signature",
                "X-Auth-Version": "v1",
                "X-Auth-Timestamp": str(int(time.time())),
                "X-Auth-Nonce": "test-nonce",
            }
        )

        result = verify_internal_traffic(request)

        assert result is True
        mock_verifier.verify_internal_auth.assert_called_once_with(request)

    @patch("backend.apigw.internal_auth.internal_auth_verifier")
    def test_verify_internal_traffic_without_hmac(self, mock_verifier: Mock) -> None:
        """Test verification without HMAC headers (fallback)."""
        request = self.create_mock_request(
            headers={
                "X-Service-Mesh": "internal",
            }
        )

        result = verify_internal_traffic(request)

        # Should not call HMAC verifier
        mock_verifier.verify_internal_auth.assert_not_called()
        # Should use basic fallback (returns True for service mesh)
        assert result is True

    @patch("backend.apigw.internal_auth.internal_auth_verifier")
    def test_verify_internal_traffic_hmac_failure(self, mock_verifier: Mock) -> None:
        """Test verification with HMAC verification failure."""
        mock_verifier.verify_internal_auth.return_value = False

        request = self.create_mock_request(
            headers={
                "X-Internal-Auth": "invalid-signature",
                "X-Auth-Version": "v1",
                "X-Auth-Timestamp": str(int(time.time())),
                "X-Auth-Nonce": "test-nonce",
            }
        )

        result = verify_internal_traffic(request)

        assert result is False
        mock_verifier.verify_internal_auth.assert_called_once_with(request)


class TestIntegration:
    """Tests d'intégration avec auth_utils."""

    @patch("backend.apigw.internal_auth.internal_auth_verifier")
    def test_auth_utils_uses_hmac_verification(self, mock_verifier: Mock) -> None:
        """Test que auth_utils utilise la vérification HMAC."""
        mock_verifier.verify_internal_auth.return_value = True

        request = Mock(spec=Request)
        request.url.path = "/v1/test"
        request.headers = {
            "X-Internal-Auth": "some-signature",
            "X-Auth-Version": "v1",
            "X-Auth-Timestamp": str(int(time.time())),
            "X-Auth-Nonce": "test-nonce",
            "X-Tenant-ID": "internal-tenant",
        }
        request.state = Mock()
        request.state.trace_id = "test-trace-123"
        request.state.user = None
        request.state.jwt_claims = None

        tenant, source, is_spoof = extract_tenant_secure(request)

        # Should call HMAC verification
        mock_verifier.verify_internal_auth.assert_called_once_with(request)

        # Should allow internal tenant
        assert tenant == "internal-tenant"
        assert source == "header"
        assert is_spoof is False
