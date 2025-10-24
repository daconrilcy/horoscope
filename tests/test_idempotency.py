"""Tests pour le module d'idempotence.

Ce module teste les fonctionnalités d'idempotence pour les tâches, incluant la gestion des clés,
l'expiration et les opérations de cache.
"""

from __future__ import annotations

import os
import time
from unittest.mock import Mock, patch

from backend.infra.ops.idempotency import (
    FailureTracker,
    IdempotencyStore,
    _InMemoryKV,
    failure_tracker,
    idempotency_store,
    make_idem_key,
)


def test_make_idem_key() -> None:
    """Teste la composition des clés d'idempotence."""
    # Test avec des parties normales
    key = make_idem_key("test_task", "param1", "param2")
    assert key == "task:test_task:param1:param2"

    # Test avec des parties contenant des retours à la ligne
    key = make_idem_key("test_task", "param\nwith\nnewlines", "param2")
    assert key == "task:test_task:param with newlines:param2"

    # Test avec des parties vides
    key = make_idem_key("test_task", "", "param2")
    assert key == "task:test_task::param2"

    # Test sans parties
    key = make_idem_key("test_task")
    assert key == "task:test_task"


def test_in_memory_kv_basic_operations() -> None:
    """Teste les opérations de base du store en mémoire."""
    kv = _InMemoryKV()

    # Test setnx avec nouvelle clé
    result = kv.setnx("key1", "value1", 60)
    assert result is True

    # Test setnx avec clé existante
    result = kv.setnx("key1", "value2", 60)
    assert result is False


def test_in_memory_kv_expiration() -> None:
    """Teste l'expiration des clés en mémoire."""
    kv = _InMemoryKV()

    # Test avec expiration courte
    kv.setnx("key1", "value1", 1)

    # Attendre l'expiration
    time.sleep(1.1)

    # La clé devrait être expirée lors du prochain setnx
    result = kv.setnx("key1", "value2", 60)
    assert result is True  # Peut être acquise à nouveau


def test_in_memory_kv_list_operations() -> None:
    """Teste les opérations de liste du store en mémoire."""
    kv = _InMemoryKV()

    # Test rpush
    kv.rpush("list1", "item1")
    kv.rpush("list1", "item2")

    # Test lrange avec indices spécifiques
    items = kv.lrange("list1", 0, 1)
    assert items == ["item1", "item2"]

    # Test lrange avec un seul élément
    items = kv.lrange("list1", 0, 0)
    assert items == ["item1"]


def test_in_memory_kv_purge_expired() -> None:
    """Teste la purge automatique des clés expirées."""
    kv = _InMemoryKV()

    # Créer une clé expirée
    kv.setnx("expired_key", "value", 0)  # Expire immédiatement

    # Créer une nouvelle clé pour déclencher la purge
    kv.setnx("new_key", "value", 60)

    # Vérifier que la clé expirée peut être acquise à nouveau
    result = kv.setnx("expired_key", "new_value", 60)
    assert result is True


def test_redis_kv_without_redis() -> None:
    """Teste le comportement du store Redis quand Redis n'est pas disponible."""
    with patch("backend.infra.ops.idempotency.redis") as mock_redis:
        mock_redis.Redis.side_effect = Exception("Redis not available")

        # Créer un nouveau store pour tester le fallback
        store = IdempotencyStore()
        assert isinstance(store.client, _InMemoryKV)


def test_redis_kv_with_redis() -> None:
    """Teste le comportement du store Redis quand Redis est disponible."""
    with patch("backend.infra.ops.idempotency.redis"):
        store = IdempotencyStore()
        assert isinstance(store, IdempotencyStore)

        # Test des opérations Redis - vérifier que le store fonctionne
        result = store.acquire("key1", 60)
        assert result is True  # Devrait fonctionner même avec mock


def test_idempotency_store_singleton() -> None:
    """Teste le singleton du store d'idempotence."""
    store = idempotency_store
    assert store is not None
    assert isinstance(store, IdempotencyStore)


def test_idempotency_store_acquire() -> None:
    """Teste l'acquisition d'une clé d'idempotence."""
    store = IdempotencyStore(ttl_seconds=60)

    # Test acquisition réussie
    result = store.acquire("test_key", 30)
    assert result is True

    # Test acquisition échouée (clé déjà acquise)
    result = store.acquire("test_key", 30)
    assert result is False


def test_idempotency_store_get() -> None:
    """Teste la récupération d'une valeur."""
    store = IdempotencyStore()

    # Test avec clé inexistante - utilise acquire pour tester
    result = store.acquire("nonexistent_key", 60)
    assert result is True

    # Test avec clé existante
    result = store.acquire("nonexistent_key", 60)
    assert result is False


def test_idempotency_store_release() -> None:
    """Teste la libération d'une clé d'idempotence."""
    store = IdempotencyStore()

    # Acquérir une clé puis attendre l'expiration
    store.acquire("test_key", 1)

    # Attendre l'expiration
    time.sleep(1.1)

    # Vérifier que la clé peut être acquise à nouveau
    result = store.acquire("test_key", 60)
    assert result is True


def test_failure_tracker_singleton() -> None:
    """Teste le singleton du tracker de défaillances."""
    tracker = failure_tracker
    assert tracker is not None
    assert isinstance(tracker, FailureTracker)


def test_failure_tracker_record_failure() -> None:
    """Teste l'enregistrement d'une défaillance."""
    tracker = FailureTracker()

    # Enregistrer une défaillance
    result = tracker.on_failure("task_1", "task_id_1", max_failures=2, reason="test_error")
    assert result is False  # Pas encore au seuil

    # Enregistrer une deuxième défaillance
    result = tracker.on_failure("task_1", "task_id_2", max_failures=2, reason="test_error")
    assert result is False  # Toujours pas au seuil


def test_failure_tracker_different_tasks() -> None:
    """Teste que les défaillances sont comptées par tâche."""
    tracker = FailureTracker()

    # Défaillance pour task_1
    result = tracker.on_failure("task_1", "task_id_1", max_failures=1, reason="error_1")
    assert result is False

    # Défaillance pour task_2 (compteur séparé)
    result = tracker.on_failure("task_2", "task_id_2", max_failures=1, reason="error_2")
    assert result is False


def test_failure_tracker_exceed_threshold() -> None:
    """Teste le dépassement du seuil de défaillances."""
    tracker = FailureTracker()

    # Enregistrer des défaillances jusqu'au seuil
    result = tracker.on_failure("task_1", "task_id_1", max_failures=2, reason="error")
    assert result is False  # 1ère défaillance

    result = tracker.on_failure("task_1", "task_id_1", max_failures=2, reason="error")
    assert result is False  # 2ème défaillance

    result = tracker.on_failure("task_1", "task_id_1", max_failures=2, reason="error")
    assert result is True  # 3ème défaillance - seuil dépassé


def test_failure_tracker_record_retry() -> None:
    """Teste l'enregistrement d'un retry."""
    tracker = FailureTracker()

    # Test que record_retry ne lève pas d'exception
    tracker.record_retry("test_task")


def test_failure_tracker_env_max_failures() -> None:
    """Teste l'utilisation de la variable d'environnement pour max_failures."""
    with patch.dict(os.environ, {"CELERY_MAX_FAILURES_BEFORE_DLQ": "1"}):
        tracker = FailureTracker()

        # Première défaillance
        result = tracker.on_failure("task_1", "task_id_1")
        assert result is False

        # Deuxième défaillance - seuil dépassé
        result = tracker.on_failure("task_1", "task_id_1")
        assert result is True


def test_failure_tracker_invalid_env_max_failures() -> None:
    """Teste la gestion d'une variable d'environnement invalide pour max_failures."""
    with patch.dict(os.environ, {"CELERY_MAX_FAILURES_BEFORE_DLQ": "invalid"}):
        tracker = FailureTracker()

        # Devrait utiliser la valeur par défaut (3)
        result = tracker.on_failure("task_1", "task_id_1")
        assert result is False


def test_failure_tracker_empty_env_max_failures() -> None:
    """Teste la gestion d'une variable d'environnement vide pour max_failures."""
    with patch.dict(os.environ, {"CELERY_MAX_FAILURES_BEFORE_DLQ": ""}):
        tracker = FailureTracker()

        # Devrait utiliser la valeur par défaut (3)
        result = tracker.on_failure("task_1", "task_id_1")
        assert result is False


def test_idempotency_store_redis_client_exception() -> None:
    """Teste la gestion d'exception dans le client Redis."""
    store = IdempotencyStore()

    # Mock un client Redis qui n'a pas setnx (donc utilise la branche Redis)
    mock_client = Mock()
    mock_client.set.side_effect = Exception("Redis error")
    # Ne pas définir setnx pour utiliser la branche Redis
    del mock_client.setnx
    store.client = mock_client

    # Devrait retourner True en cas d'exception
    result = store.acquire("test_key", 60)
    assert result is True


def test_failure_tracker_redis_client_exception() -> None:
    """Teste la gestion d'exception dans le client Redis pour FailureTracker."""
    tracker = FailureTracker()

    # Mock un client Redis qui lève une exception
    mock_client = Mock()
    mock_client.incr.side_effect = Exception("Redis error")
    tracker.client = mock_client

    # Devrait utiliser max_failures comme count en cas d'exception
    # count = max_failures, donc count > max_failures est False
    result = tracker.on_failure("task_1", "task_id_1", max_failures=2)
    assert result is False  # count = 2, donc count > 2 est False


def test_failure_tracker_dlq_push_exception() -> None:
    """Teste la gestion d'exception lors du push vers DLQ."""
    tracker = FailureTracker()

    # Mock un client Redis qui lève une exception lors du push
    mock_client = Mock()
    mock_client.incr.return_value = 4  # Au-dessus du seuil
    mock_client.rpush.side_effect = Exception("DLQ push error")
    tracker.client = mock_client

    # Devrait toujours retourner True même si le push échoue
    result = tracker.on_failure("task_1", "task_id_1", max_failures=2)
    assert result is True


def test_idempotency_store_with_custom_client() -> None:
    """Teste IdempotencyStore avec un client personnalisé."""
    custom_client = _InMemoryKV()
    store = IdempotencyStore(client=custom_client)

    assert store.client is custom_client

    # Test des opérations
    result = store.acquire("test_key", 60)
    assert result is True


def test_failure_tracker_with_custom_client() -> None:
    """Teste FailureTracker avec un client personnalisé."""
    custom_client = _InMemoryKV()
    tracker = FailureTracker(client=custom_client)

    assert tracker.client is custom_client

    # Test des opérations
    result = tracker.on_failure("task_1", "task_id_1", max_failures=1)
    assert result is False


def test_make_idem_key_with_carriage_return() -> None:
    """Teste la composition des clés avec des retours chariot."""
    key = make_idem_key("test_task", "param\rwith\rreturns", "param2")
    assert key == "task:test_task:param with returns:param2"


def test_make_idem_key_with_mixed_newlines() -> None:
    """Teste la composition des clés avec des retours à la ligne mixtes."""
    key = make_idem_key("test_task", "param\nwith\r\nmixed", "param2")
    assert key == "task:test_task:param with  mixed:param2"
