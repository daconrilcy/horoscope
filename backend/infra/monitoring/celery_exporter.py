# ============================================================
# Module : backend/infra/monitoring/celery_exporter.py
# Objet  : Exporter Prometheus pour métriques Celery (squelette).
# ============================================================

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

from prometheus_client import Counter, Gauge, Histogram, generate_latest

QUEUE_DEPTH = Gauge("celery_queue_depth", "Taille de la file Celery")
TASK_SUCCESS = Counter("celery_task_success_total", "Tasks réussies")
TASK_FAILURE = Counter("celery_task_failure_total", "Tasks échouées", ["task"])
TASK_RETRY = Counter("celery_task_retry_total", "Tasks en retry", ["task"])
DLQ_TOTAL = Counter("celery_dlq_total", "Messages placés en DLQ", ["queue"])
TASK_RUNTIME_SECONDS = Histogram(
    "celery_task_runtime_seconds", "Durée d'exécution des tâches", ["task"]
)

_starts: dict[str, float] = {}
_spans: dict[str, Any] = {}
_poller_started = False
_poller_stop = threading.Event()


def metrics_wsgi_app(environ, start_response):  # type: ignore[no-untyped-def]
    """WSGI simple pour exposer les métriques Prometheus."""
    data = generate_latest()
    status = "200 OK"
    headers = [("Content-Type", "text/plain; version=0.0.4")]
    start_response(status, headers)
    return [data]


def _maybe_start_span(task_name: str, task_id: str, task_obj: Any) -> None:
    try:
        from opentelemetry import trace  # type: ignore
    except Exception:  # pragma: no cover - optional
        return
    tracer = trace.get_tracer(__name__)
    # Basic span; correlation via upstream middleware when headers are propagated
    span = tracer.start_span(name=f"celery:{task_name}")
    _spans[task_id] = span


def _maybe_end_span(task_id: str) -> None:
    span = _spans.pop(task_id, None)
    if span is not None:
        try:
            span.end()
        except Exception:  # pragma: no cover - defensive
            pass


def on_task_prerun(task_id: str, task_name: str, task_obj: Any) -> None:
    _starts[task_id] = time.time()
    _maybe_start_span(task_name, task_id, task_obj)


def on_task_postrun(task_id: str, task_name: str, state: str) -> None:
    start = _starts.pop(task_id, None)
    if start is not None:
        TASK_RUNTIME_SECONDS.labels(task=task_name).observe(max(0.0, time.time() - start))
    if state.upper() == "SUCCESS":
        TASK_SUCCESS.inc()
    _maybe_end_span(task_id)


def on_task_failure(task_id: str, task_name: str) -> None:
    TASK_FAILURE.labels(task=task_name).inc()
    _maybe_end_span(task_id)


def on_task_retry(task_name: str) -> None:
    TASK_RETRY.labels(task=task_name).inc()


def bind_celery_signals(celery_app) -> None:  # type: ignore[no-untyped-def]
    """Attach Celery signal handlers to populate Prometheus metrics.

    Safe to call multiple times; signals register idempotently.
    """
    try:
        from celery import signals  # type: ignore
    except Exception:  # pragma: no cover - optional
        return

    @signals.task_prerun.connect  # type: ignore[misc]
    def _pre(sender=None, task_id: str = "", task=None, args=None, kwargs=None, **kw):  # type: ignore[no-untyped-def]
        name = getattr(sender, "name", None) or getattr(task, "name", None) or "unknown"
        on_task_prerun(task_id=task_id, task_name=name, task_obj=task)

    @signals.task_postrun.connect  # type: ignore[misc]
    def _post(sender=None, task_id: str = "", state: str = "", **kw):  # type: ignore[no-untyped-def]
        name = getattr(sender, "name", None) or "unknown"
        on_task_postrun(task_id=task_id, task_name=name, state=state or "")

    @signals.task_failure.connect  # type: ignore[misc]
    def _fail(sender=None, task_id: str = "", **kw):  # type: ignore[no-untyped-def]
        name = getattr(sender, "name", None) or "unknown"
        on_task_failure(task_id=task_id, task_name=name)

    @signals.task_retry.connect  # type: ignore[misc]
    def _retry(sender=None, **kw):  # type: ignore[no-untyped-def]
        name = getattr(sender, "name", None) or "unknown"
        on_task_retry(task_name=name)

    # Optionnel: démarrer un poller de profondeur de file si Redis est dispo
    _maybe_start_queue_depth_poller()


def _redis_client():  # pragma: no cover - smoke path
    try:
        import redis  # type: ignore
    except Exception:
        return None
    url = os.getenv("REDIS_URL")
    if not url:
        return None
    try:
        return redis.Redis.from_url(url, decode_responses=True)
    except Exception:
        return None


def _queues_from_env() -> list[str]:
    names = os.getenv("CELERY_QUEUE_NAMES") or "celery,default"
    # allow JSON array or comma list
    try:
        data = json.loads(names)
        if isinstance(data, list):
            return [str(x) for x in data]
    except Exception:
        pass
    return [q.strip() for q in names.split(",") if q.strip()]


def _maybe_start_queue_depth_poller(interval: float = 5.0) -> None:
    global _poller_started
    if _poller_started:
        return
    client = _redis_client()
    if not client:
        return

    def _run() -> None:
        while not _poller_stop.is_set():
            for q in _queues_from_env():
                try:
                    depth = int(client.llen(q))  # type: ignore[attr-defined]
                except Exception:
                    depth = 0
                QUEUE_DEPTH.set(depth)
            _poller_stop.wait(interval)

    t = threading.Thread(target=_run, name="celery-queue-depth-poller", daemon=True)
    t.start()
    _poller_started = True
