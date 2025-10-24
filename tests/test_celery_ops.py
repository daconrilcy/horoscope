"""Tests pour les opérations Celery.

Ce module teste les fonctionnalités d'idempotence, de suivi des échecs et des tâches Celery dans
l'application.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from backend.infra.ops.idempotency import FailureTracker, IdempotencyStore
from backend.tasks.pdf_tasks import render_pdf_task


def test_idempotency_store_in_memory(monkeypatch: Any) -> None:
    """Teste le store d'idempotence en mémoire."""
    monkeypatch.delenv("REDIS_URL", raising=False)
    store = IdempotencyStore(ttl_seconds=1)
    key = "k:test:1"
    assert store.acquire(key, ttl=5) is True
    assert store.acquire(key, ttl=5) is False


def test_failure_tracker_dlq(monkeypatch: Any) -> None:
    """Teste que le tracker d'échecs envoie vers la DLQ après le seuil."""
    monkeypatch.delenv("REDIS_URL", raising=False)
    ft = FailureTracker()
    # Simulate exceeding failure threshold
    dlq = False
    for _ in range(4):
        dlq = ft.on_failure(task="unit.task", task_id="abc", max_failures=2)
    assert dlq is True


@patch("backend.tasks.pdf_tasks.container")
def test_render_pdf_task_idempotent(mock_container, monkeypatch: Any) -> None:
    """Teste que la tâche de rendu PDF est idempotente."""
    # Mock chart_repo and user_repo
    mock_container.chart_repo.save.return_value = None
    mock_container.chart_repo.get.return_value = {
        "id": "c123",
        "owner": "t",
        "chart": {"precision_score": 1},
    }
    mock_container.user_repo.client.setex.return_value = None
    mock_container.settings.REDIS_URL = "redis://localhost:6379"

    chart_id = "c123"
    mock_container.chart_repo.save({"id": chart_id, "owner": "t", "chart": {"precision_score": 1}})
    r1 = render_pdf_task(chart_id)
    r2 = render_pdf_task(chart_id)
    assert r1 in {"ok", "not_found"}
    assert r2 == "duplicate"
