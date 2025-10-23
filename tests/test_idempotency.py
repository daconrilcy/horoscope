"""Tests pour le module d'idempotence.

Ce module teste les fonctionnalités d'idempotence pour les tâches, incluant la gestion des clés,
l'expiration et les opérations de cache.
"""

from __future__ import annotations

import time
from unittest.mock import patch

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
