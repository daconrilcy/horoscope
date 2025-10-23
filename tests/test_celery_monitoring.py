"""
Tests pour le monitoring Celery.

Ce module teste les métriques Prometheus générées par le monitoring des tâches Celery.
"""

from __future__ import annotations

import importlib

from prometheus_client import generate_latest

from backend.infra.monitoring.celery_exporter import (
    bind_celery_signals,
    on_task_failure,
    on_task_postrun,
    on_task_prerun,
    on_task_retry,
)


def test_celery_metrics_increment_and_runtime(monkeypatch) -> None:
    """Teste que les métriques Celery sont incrémentées correctement."""
    # prerun -> postrun success
    on_task_prerun(task_id="t1", task_name="unit.task", task_obj=None)
    # simulate instant run
    on_task_postrun(task_id="t1", task_name="unit.task", state="SUCCESS")
    # counters visible
    content = generate_latest()
    assert b"celery_task_success_total" in content
    assert b"celery_task_runtime_seconds_count" in content

    # failure and retry
    on_task_prerun(task_id="t2", task_name="unit.task", task_obj=None)
    on_task_failure(task_id="t2", task_name="unit.task")
    on_task_retry(task_name="unit.task")
    text = generate_latest()
    assert b"celery_task_failure_total" in text
    assert b"celery_task_retry_total" in text


def test_bind_celery_signals_is_noop_without_celery(monkeypatch) -> None:
    """Teste que la liaison des signaux Celery ne plante pas sans Celery."""
    # If celery not importable, bind should not raise

    mod = importlib.import_module("backend.infra.monitoring.celery_exporter")
    bind_celery_signals(None)
    # Just ensure counters are still accessible
    assert hasattr(mod, "TASK_SUCCESS")
