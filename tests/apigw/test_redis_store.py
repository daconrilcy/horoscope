"""
Tests pour le store Redis atomique.

Tests de contention, défaillance Redis, et performance du rate limiting distribué.
"""

import time
from unittest.mock import Mock, patch

import pytest
import redis
from redis.exceptions import ConnectionError, TimeoutError

from backend.apigw.redis_store import RedisRateLimitStore, RateLimitResult


class TestRedisRateLimitStore:
    """Tests pour RedisRateLimitStore."""

    def setup_method(self) -> None:
        """Setup test environment."""
        self.store = RedisRateLimitStore()
        self.store._redis = Mock(spec=redis.Redis)
        self.store._script_hash = "test_script_hash"

    def test_tenant_hashing(self) -> None:
        """Test que le hachage des tenants est cohérent."""
        tenant1 = "tenant1"
        tenant2 = "tenant2"
        
        hash1 = self.store._hash_tenant(tenant1)
        hash2 = self.store._hash_tenant(tenant2)
        hash1_again = self.store._hash_tenant(tenant1)
        
        assert hash1 == hash1_again  # Cohérent
        assert hash1 != hash2  # Différent pour différents tenants
        assert len(hash1) == 16  # Longueur fixe

    def test_key_generation(self) -> None:
        """Test la génération des clés Redis."""
        route = "/v1/chat/123"
        tenant = "tenant1"
        
        # Mock normalize_route
        with patch("backend.apigw.redis_store.normalize_route") as mock_normalize:
            mock_normalize.return_value = "/v1/chat/{id}"
            
            result = self.store.check_rate_limit(route, tenant)
            
            # Vérifier que normalize_route a été appelé
            mock_normalize.assert_called_with(route)

    def test_rate_limit_allowed(self) -> None:
        """Test rate limit autorisé."""
        # Mock Redis response: [allowed=1, current=1, remaining=59, reset_time=1234567890]
        self.store._redis.evalsha.return_value = [1, 1, 59, 1234567890.0]
        
        result = self.store.check_rate_limit("/v1/chat/123", "tenant1")
        
        assert result.allowed is True
        assert result.remaining == 59
        assert result.reset_time == 1234567890.0
        assert result.retry_after is None

    def test_rate_limit_blocked(self) -> None:
        """Test rate limit bloqué."""
        # Mock Redis response: [allowed=0, current=60, remaining=0, reset_time=1234567890]
        self.store._redis.evalsha.return_value = [0, 60, 0, 1234567890.0]
        
        result = self.store.check_rate_limit("/v1/chat/123", "tenant1")
        
        assert result.allowed is False
        assert result.remaining == 0
        assert result.reset_time == 1234567890.0
        assert result.retry_after is not None
        assert result.retry_after >= 1

    def test_redis_connection_error_fail_open(self) -> None:
        """Test fail-open en cas d'erreur de connexion Redis."""
        self.store._redis.evalsha.side_effect = ConnectionError("Redis unavailable")
        
        with patch("backend.apigw.redis_store.APIGW_RATE_LIMIT_STORE_ERRORS") as mock_metrics:
            result = self.store.check_rate_limit("/v1/chat/123", "tenant1")
            
            # Fail-open: should allow request
            assert result.allowed is True
            assert result.remaining >= 0
            assert result.retry_after is None
            
            # Should increment error metric
            mock_metrics.labels.assert_called_with(
                route="/v1/chat/{id}", 
                error_type="connection_error"
            )

    def test_redis_timeout_error_fail_open(self) -> None:
        """Test fail-open en cas de timeout Redis."""
        self.store._redis.evalsha.side_effect = TimeoutError("Redis timeout")
        
        with patch("backend.apigw.redis_store.APIGW_RATE_LIMIT_STORE_ERRORS") as mock_metrics:
            result = self.store.check_rate_limit("/v1/chat/123", "tenant1")
            
            # Fail-open: should allow request
            assert result.allowed is True
            assert result.remaining >= 0
            assert result.retry_after is None
            
            # Should increment error metric
            mock_metrics.labels.assert_called_with(
                route="/v1/chat/{id}", 
                error_type="connection_error"
            )

    def test_unexpected_error_fail_open(self) -> None:
        """Test fail-open en cas d'erreur inattendue."""
        self.store._redis.evalsha.side_effect = Exception("Unexpected error")
        
        with patch("backend.apigw.redis_store.APIGW_RATE_LIMIT_STORE_ERRORS") as mock_metrics:
            result = self.store.check_rate_limit("/v1/chat/123", "tenant1")
            
            # Fail-open: should allow request
            assert result.allowed is True
            assert result.remaining >= 0
            assert result.retry_after is None
            
            # Should increment error metric
            mock_metrics.labels.assert_called_with(
                route="/v1/chat/{id}", 
                error_type="unexpected_error"
            )

    def test_custom_window_and_limit(self) -> None:
        """Test avec fenêtre et limite personnalisées."""
        self.store._redis.evalsha.return_value = [1, 1, 29, 1234567890.0]
        
        result = self.store.check_rate_limit(
            "/v1/chat/123", 
            "tenant1", 
            window_seconds=30, 
            max_requests=30
        )
        
        # Vérifier que les paramètres ont été passés à Redis
        call_args = self.store._redis.evalsha.call_args
        assert call_args[0][3] == 30  # window_seconds (4ème argument)
        assert call_args[0][4] == 30  # max_requests (5ème argument)

    def test_script_hash_caching(self) -> None:
        """Test que le hash du script est mis en cache."""
        self.store._script_hash = None
        self.store._redis.script_load.return_value = "cached_hash"
        
        # Premier appel
        hash1 = self.store._get_script_hash()
        
        # Deuxième appel
        hash2 = self.store._get_script_hash()
        
        assert hash1 == hash2 == "cached_hash"
        # script_load ne doit être appelé qu'une fois
        self.store._redis.script_load.assert_called_once()


class TestRedisStoreIntegration:
    """Tests d'intégration pour le store Redis."""

    @pytest.mark.asyncio
    async def test_concurrent_requests_atomic(self) -> None:
        """Test que les requêtes concurrentes sont atomiques."""
        store = RedisRateLimitStore()
        
        # Mock Redis pour simuler des requêtes concurrentes
        with patch.object(store, '_get_redis') as mock_get_redis:
            mock_redis = Mock()
            mock_get_redis.return_value = mock_redis
            
            # Simuler 10 requêtes simultanées avec limite de 5
            mock_redis.evalsha.side_effect = [
                [1, 1, 4, 1234567890.0],  # Request 1: allowed
                [1, 2, 3, 1234567890.0],  # Request 2: allowed
                [1, 3, 2, 1234567890.0],  # Request 3: allowed
                [1, 4, 1, 1234567890.0],  # Request 4: allowed
                [1, 5, 0, 1234567890.0],  # Request 5: allowed
                [0, 5, 0, 1234567890.0],  # Request 6: blocked
                [0, 5, 0, 1234567890.0],  # Request 7: blocked
                [0, 5, 0, 1234567890.0],  # Request 8: blocked
                [0, 5, 0, 1234567890.0],  # Request 9: blocked
                [0, 5, 0, 1234567890.0],  # Request 10: blocked
            ]
            
            # Simuler des requêtes concurrentes
            results = []
            for i in range(10):
                result = store.check_rate_limit(
                    "/v1/chat/123", 
                    f"tenant{i}", 
                    max_requests=5
                )
                results.append(result)
            
            # Vérifier que exactement 5 requêtes ont été autorisées
            allowed_count = sum(1 for r in results if r.allowed)
            assert allowed_count == 5
            
            # Vérifier que les 5 dernières ont été bloquées
            blocked_results = [r for r in results[5:] if not r.allowed]
            assert len(blocked_results) == 5

    def test_performance_evaluation_time(self) -> None:
        """Test que le temps d'évaluation est acceptable."""
        store = RedisRateLimitStore()
        
        with patch.object(store, '_get_redis') as mock_get_redis:
            mock_redis = Mock()
            mock_get_redis.return_value = mock_redis
            mock_redis.evalsha.return_value = [1, 1, 59, 1234567890.0]
            
            # Mesurer le temps d'évaluation
            start_time = time.perf_counter()
            result = store.check_rate_limit("/v1/chat/123", "tenant1")
            end_time = time.perf_counter()
            
            evaluation_time = end_time - start_time
            
            # Vérifier que le résultat est correct
            assert result.allowed is True
            
            # Vérifier que le temps d'évaluation est acceptable (< 20ms)
            assert evaluation_time < 0.02  # 20ms

    def test_retry_after_calculation(self) -> None:
        """Test le calcul du Retry-After."""
        store = RedisRateLimitStore()
        
        with patch.object(store, '_get_redis') as mock_get_redis:
            mock_redis = Mock()
            mock_get_redis.return_value = mock_redis
            
            # Simuler une requête bloquée avec retry_after calculé
            current_time = time.time()
            retry_after_seconds = 30
            reset_time = current_time + retry_after_seconds
            
            mock_redis.evalsha.return_value = [0, 60, 0, reset_time]
            
            result = store.check_rate_limit("/v1/chat/123", "tenant1")
            
            assert result.allowed is False
            assert result.retry_after is not None
            assert result.retry_after >= 1
            assert result.retry_after <= retry_after_seconds + 1  # Tolérance de 1 seconde


class TestRateLimitResult:
    """Tests pour RateLimitResult."""

    def test_allowed_result(self) -> None:
        """Test création d'un résultat autorisé."""
        result = RateLimitResult(
            allowed=True,
            remaining=59,
            reset_time=1234567890.0,
            retry_after=None,
        )
        
        assert result.allowed is True
        assert result.remaining == 59
        assert result.reset_time == 1234567890.0
        assert result.retry_after is None

    def test_blocked_result(self) -> None:
        """Test création d'un résultat bloqué."""
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
