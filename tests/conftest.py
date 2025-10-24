"""Configuration de test pour pytest avec gestion des chemins.

Ce module configure pytest pour résoudre les imports backend en ajoutant la racine du projet au
sys.path pour les tests.
"""

import os
import sys
from unittest.mock import Mock, patch

import pytest

# Ensure project root is on sys.path so that
# imports like `from backend...` resolve.
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture(autouse=True)
def mock_redis_connection():
    """Mock Redis connections pour éviter les erreurs de connexion dans les tests."""
    with patch("redis.Redis") as mock_redis:
        # Mock Redis connection to avoid ConnectionError
        mock_redis_instance = Mock()
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.get.return_value = None
        mock_redis_instance.set.return_value = True
        mock_redis_instance.delete.return_value = 1
        mock_redis_instance.exists.return_value = False
        mock_redis_instance.expire.return_value = True
        mock_redis_instance.incr.return_value = 1
        mock_redis_instance.zadd.return_value = 1
        mock_redis_instance.zremrangebyscore.return_value = 0
        mock_redis_instance.zcard.return_value = 0
        mock_redis_instance.zrange.return_value = []
        mock_redis_instance.zrangebyscore.return_value = []
        # Additional Redis commands for repositories
        mock_redis_instance.hget.return_value = None
        mock_redis_instance.hset.return_value = 1
        mock_redis_instance.hgetall.return_value = {}
        mock_redis_instance.hdel.return_value = 1
        mock_redis_instance.hkeys.return_value = []
        mock_redis_instance.hvals.return_value = []
        mock_redis_instance.hlen.return_value = 0
        mock_redis_instance.hincrby.return_value = 1
        mock_redis_instance.hincrbyfloat.return_value = 1.0
        mock_redis_instance.hmget.return_value = []
        mock_redis_instance.hmset.return_value = True
        mock_redis_instance.hscan.return_value = (0, {})
        mock_redis_instance.hscan_iter.return_value = []
        mock_redis_instance.hexists.return_value = False
        mock_redis_instance.hstrlen.return_value = 0
        mock_redis.return_value = mock_redis_instance
        yield mock_redis_instance


@pytest.fixture(autouse=True)
def mock_redis_repositories():
    """Mock Redis repositories pour éviter les erreurs de connexion."""
    with (
        patch("backend.infra.repositories.RedisUserRepo") as mock_user_repo,
        patch("backend.infra.repositories.RedisChartRepo") as mock_chart_repo,
    ):
        # Mock RedisUserRepo
        mock_user_repo_instance = Mock()
        mock_user_repo_instance.get_by_email.return_value = None
        mock_user_repo_instance.create.return_value = "user_id"
        mock_user_repo_instance.get.return_value = None
        mock_user_repo_instance.update.return_value = None
        mock_user_repo_instance.delete.return_value = None
        mock_user_repo_instance.client = Mock()
        mock_user_repo_instance.client.hget.return_value = None
        mock_user_repo_instance.client.hset.return_value = 1
        mock_user_repo_instance.client.hgetall.return_value = {}
        mock_user_repo_instance.client.hdel.return_value = 1
        mock_user_repo_instance.client.hkeys.return_value = []
        mock_user_repo_instance.client.hvals.return_value = []
        mock_user_repo_instance.client.hlen.return_value = 0
        mock_user_repo_instance.client.hincrby.return_value = 1
        mock_user_repo_instance.client.hincrbyfloat.return_value = 1.0
        mock_user_repo_instance.client.hmget.return_value = []
        mock_user_repo_instance.client.hmset.return_value = True
        mock_user_repo_instance.client.hscan.return_value = (0, {})
        mock_user_repo_instance.client.hscan_iter.return_value = []
        mock_user_repo_instance.client.hexists.return_value = False
        mock_user_repo_instance.client.hstrlen.return_value = 0
        mock_user_repo_instance.client.get.return_value = None
        mock_user_repo_instance.client.set.return_value = True
        mock_user_repo_instance.client.setex.return_value = True
        mock_user_repo_instance.client.delete.return_value = 1
        mock_user_repo_instance.client.exists.return_value = False
        mock_user_repo_instance.client.expire.return_value = True
        mock_user_repo_instance.client.incr.return_value = 1
        mock_user_repo_instance.client.zadd.return_value = 1
        mock_user_repo_instance.client.zremrangebyscore.return_value = 0
        mock_user_repo_instance.client.zcard.return_value = 0
        mock_user_repo_instance.client.zrange.return_value = []
        mock_user_repo_instance.client.zrangebyscore.return_value = []
        mock_user_repo.return_value = mock_user_repo_instance

        # Mock RedisChartRepo
        mock_chart_repo_instance = Mock()
        mock_chart_repo_instance.get.return_value = None
        mock_chart_repo_instance.create.return_value = "chart_id"
        mock_chart_repo_instance.update.return_value = None
        mock_chart_repo_instance.delete.return_value = None
        mock_chart_repo_instance.client = Mock()
        mock_chart_repo_instance.client.hget.return_value = None
        mock_chart_repo_instance.client.hset.return_value = 1
        mock_chart_repo_instance.client.hgetall.return_value = {}
        mock_chart_repo_instance.client.hdel.return_value = 1
        mock_chart_repo_instance.client.hkeys.return_value = []
        mock_chart_repo_instance.client.hvals.return_value = []
        mock_chart_repo_instance.client.hlen.return_value = 0
        mock_chart_repo_instance.client.hincrby.return_value = 1
        mock_chart_repo_instance.client.hincrbyfloat.return_value = 1.0
        mock_chart_repo_instance.client.hmget.return_value = []
        mock_chart_repo_instance.client.hmset.return_value = True
        mock_chart_repo_instance.client.hscan.return_value = (0, {})
        mock_chart_repo_instance.client.hscan_iter.return_value = []
        mock_chart_repo_instance.client.hexists.return_value = False
        mock_chart_repo_instance.client.hstrlen.return_value = 0
        mock_chart_repo_instance.client.get.return_value = None
        mock_chart_repo_instance.client.set.return_value = True
        mock_chart_repo_instance.client.setex.return_value = True
        mock_chart_repo_instance.client.delete.return_value = 1
        mock_chart_repo_instance.client.exists.return_value = False
        mock_chart_repo_instance.client.expire.return_value = True
        mock_chart_repo_instance.client.incr.return_value = 1
        mock_chart_repo_instance.client.zadd.return_value = 1
        mock_chart_repo_instance.client.zremrangebyscore.return_value = 0
        mock_chart_repo_instance.client.zcard.return_value = 0
        mock_chart_repo_instance.client.zrange.return_value = []
        mock_chart_repo_instance.client.zrangebyscore.return_value = []
        mock_chart_repo.return_value = mock_chart_repo_instance

        yield mock_user_repo_instance, mock_chart_repo_instance


@pytest.fixture(autouse=True)
def mock_container():
    """Mock le container global pour éviter les erreurs de connexion Redis."""
    with patch("backend.core.container.container") as mock_container:
        # Mock settings
        mock_settings = Mock()
        mock_settings.APP_NAME = "test_app"
        mock_settings.APP_DEBUG = True
        mock_settings.REDIS_URL = "redis://localhost:6379/0"
        mock_settings.REQUIRE_REDIS = False
        mock_settings.ASTRO_SEED = 42
        mock_container.settings = mock_settings

        # Mock repositories
        mock_user_repo = Mock()
        mock_user_repo.get_by_email.return_value = None
        mock_user_repo.create.return_value = "user_id"
        mock_user_repo.get.return_value = None
        mock_user_repo.update.return_value = None
        mock_user_repo.delete.return_value = None
        mock_container.user_repo = mock_user_repo

        mock_chart_repo = Mock()
        mock_chart_repo.get.return_value = None
        mock_chart_repo.save.return_value = {"id": "test_chart_id", "data": "test_data"}
        mock_chart_repo.create.return_value = "chart_id"
        mock_chart_repo.update.return_value = None
        mock_chart_repo.delete.return_value = None
        mock_container.chart_repo = mock_chart_repo

        # Mock other components
        mock_container.content_repo = Mock()
        mock_container.astro = Mock()
        mock_container.vault = Mock()
        mock_container.storage_backend = "memory"

        yield mock_container


@pytest.fixture(autouse=True)
def mock_redis_store():
    """Mock Redis store pour éviter les erreurs de connexion."""
    with patch("backend.apigw.redis_store.redis_store") as mock_store:
        # Mock Redis store methods
        mock_result = Mock()
        mock_result.allowed = True
        mock_result.remaining = 59
        mock_result.reset_time = 1234567890.0
        mock_result.retry_after = None

        mock_store.check_rate_limit.return_value = mock_result
        mock_store.settings.RL_MAX_REQ_PER_WINDOW = 60
        yield mock_store
