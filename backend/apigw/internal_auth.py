"""
Signature HMAC pour les headers internes.

Ce module implémente la vérification cryptographique des headers internes pour sécuriser le trafic
entre services.
"""

import hashlib
import hmac
import logging
import time

from fastapi import Request

from backend.core.settings import get_settings

# Constants
MAX_TIMESTAMP_SKEW_SECONDS = 300  # 5 minutes

log = logging.getLogger(__name__)


class InternalAuthVerifier:
    """Vérificateur de signature HMAC pour les headers internes."""

    def __init__(self) -> None:
        """Initialize HMAC verifier with settings."""
        self.settings = get_settings()
        self._nonce_cache: dict[str, float] = {}
        self._nonce_ttl = 600  # 10 minutes

    def verify_internal_auth(self, request: Request) -> bool:
        """
        Verify internal authentication header with HMAC signature.

        Headers expected:
        - X-Internal-Auth: HMAC signature
        - X-Auth-Version: Version of the auth scheme
        - X-Auth-Timestamp: Unix timestamp
        - X-Auth-Nonce: Unique nonce to prevent replay attacks

        Args:
            request: FastAPI request object

        Returns:
            True if signature is valid and not expired/replayed
        """
        auth_header = request.headers.get("X-Internal-Auth")
        version = request.headers.get("X-Auth-Version")
        timestamp_str = request.headers.get("X-Auth-Timestamp")
        nonce = request.headers.get("X-Auth-Nonce")

        if not all([auth_header, version, timestamp_str, nonce]):
            return False

        try:
            timestamp = int(timestamp_str)
        except ValueError:
            log.warning(
                "Invalid timestamp in internal auth",
                extra={
                    "timestamp": timestamp_str,
                    "trace_id": getattr(request.state, "trace_id", None),
                },
            )
            return False

        # Check timestamp skew (max 5 minutes)
        current_time = int(time.time())
        if abs(current_time - timestamp) > MAX_TIMESTAMP_SKEW_SECONDS:
            log.warning(
                "Timestamp skew too large",
                extra={
                    "timestamp": timestamp,
                    "current_time": current_time,
                    "skew": abs(current_time - timestamp),
                    "trace_id": getattr(request.state, "trace_id", None),
                },
            )
            return False

        # Check nonce replay
        if self._is_nonce_replayed(nonce):
            log.warning(
                "Nonce replay detected",
                extra={
                    "nonce": nonce,
                    "trace_id": getattr(request.state, "trace_id", None),
                },
            )
            return False

        # Verify HMAC signature
        expected_signature = self._generate_signature(
            version, timestamp, nonce, request.url.path, request.method
        )

        if not hmac.compare_digest(auth_header, expected_signature):
            log.warning(
                "Invalid HMAC signature",
                extra={
                    "provided": auth_header,
                    "expected": expected_signature,
                    "trace_id": getattr(request.state, "trace_id", None),
                },
            )
            return False

        # Cache nonce to prevent replay
        self._cache_nonce(nonce)

        log.debug(
            "Internal auth verified",
            extra={
                "version": version,
                "timestamp": timestamp,
                "nonce": nonce,
                "trace_id": getattr(request.state, "trace_id", None),
            },
        )

        return True

    def _generate_signature(
        self, version: str, timestamp: int, nonce: str, path: str, method: str
    ) -> str:
        """Generate HMAC signature for internal auth."""
        # Get secret key based on version
        secret_key = self._get_secret_key(version)
        if not secret_key:
            return ""

        # Create message to sign
        message = f"{version}:{timestamp}:{nonce}:{method}:{path}"

        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            secret_key.encode(), message.encode(), hashlib.sha256
        ).hexdigest()

        return signature

    def _get_secret_key(self, version: str) -> str | None:
        """Get secret key for given version."""
        if version == "v1":
            return getattr(self.settings, "INTERNAL_AUTH_KEY", None)
        elif version == "v2":
            return getattr(self.settings, "INTERNAL_AUTH_KEY_V2", None)
        else:
            return None

    def _is_nonce_replayed(self, nonce: str) -> bool:
        """Check if nonce has been used recently."""
        return nonce in self._nonce_cache

    def _cache_nonce(self, nonce: str) -> None:
        """Cache nonce with current timestamp."""
        self._nonce_cache[nonce] = time.time()

        # Clean expired nonces
        current_time = time.time()
        expired_nonces = [
            n
            for n, t in self._nonce_cache.items()
            if current_time - t > self._nonce_ttl
        ]
        for expired_nonce in expired_nonces:
            del self._nonce_cache[expired_nonce]


# Global instance
internal_auth_verifier = InternalAuthVerifier()


def verify_internal_traffic(request: Request) -> bool:
    """
    Verify if request is from internal/trusted source.

    This function extends the basic internal traffic detection with cryptographic verification when
    HMAC headers are present.
    """
    # Check for HMAC-based internal auth first
    if request.headers.get("X-Internal-Auth"):
        return internal_auth_verifier.verify_internal_auth(request)

    # Fallback to basic checks
    return _is_internal_traffic_basic(request)


def _is_internal_traffic_basic(request: Request) -> bool:
    """
    Detect basic internal traffic (fallback).

    This can be extended based on your infrastructure:
    - Check source IP ranges
    - Check service mesh headers
    - Check mTLS certificates
    """
    # Check for service mesh headers
    service_mesh_header = request.headers.get("X-Service-Mesh")
    if service_mesh_header == "internal":
        return True

    # Check for internal network indicators
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # In a real implementation, you would check if IP is in internal range
        # This is a placeholder - implement based on your infrastructure
        pass

    return False
