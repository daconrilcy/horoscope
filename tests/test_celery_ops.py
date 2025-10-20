from __future__ import annotations

import os
from typing import Any

from backend.infra.ops.idempotency import FailureTracker, IdempotencyStore
from backend.tasks.pdf_tasks import render_pdf_task


def test_idempotency_store_in_memory(monkeypatch: Any) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    store = IdempotencyStore(ttl_seconds=1)
    key = "k:test:1"
    assert store.acquire(key, ttl=5) is True
    assert store.acquire(key, ttl=5) is False


def test_failure_tracker_dlq(monkeypatch: Any) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    ft = FailureTracker()
    # Simulate exceeding failure threshold
    dlq = False
    for _ in range(4):
        dlq = ft.on_failure(task="unit.task", task_id="abc", max_failures=2)
    assert dlq is True


def test_render_pdf_task_idempotent(monkeypatch: Any) -> None:
    # Ensure chart exists
    from backend.core.container import container

    chart_id = "c123"
    container.chart_repo.save({"id": chart_id, "owner": "t", "chart": {"precision_score": 1}})
    r1 = render_pdf_task(chart_id)
    r2 = render_pdf_task(chart_id)
    assert r1 in {"ok", "not_found"}
    assert r2 == "duplicate"

