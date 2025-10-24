# ============================================================
# Module : backend/infra/monitoring/celery_exporter.py
# Objet  : Exporter Prometheus pour métriques Celery (squelette).
# ============================================================
"""Exporter Prometheus pour métriques Celery.

Ce module fournit des métriques Prometheus pour le monitoring des tâches Celery, incluant les
compteurs de succès/échec, les durées d'exécution et la profondeur des files.
"""

from __future__ import annotations

import contextlib
import json
import os
import threading
import time
from typing import Any

import redis
from celery import signals
from opentelemetry import trace
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
_poller_stop = threading.Event()


class _PollerState:
    """État du poller de profondeur de file."""

    def __init__(self):
        self.started = False
        self.lock = threading.Lock()


_poller_state = _PollerState()


def metrics_wsgi_app(environ, start_response):  # type: ignore[no-untyped-def]
    """WSGI simple pour exposer les métriques Prometheus."""
    data = generate_latest()
    status = "200 OK"
    headers = [("Content-Type", "text/plain; version=0.0.4")]
    start_response(status, headers)
    return [data]


def _maybe_start_span(task_name: str, task_id: str, task_obj: Any) -> None:
    """Démarre un span OpenTelemetry pour une tâche Celery."""
    with contextlib.suppress(Exception):  # pragma: no cover - optional
        tracer = trace.get_tracer(__name__)
        # Basic span; correlation via upstream middleware when headers are propagated
        span = tracer.start_span(name=f"celery:{task_name}")
        _spans[task_id] = span


def _maybe_end_span(task_id: str) -> None:
    """Termine un span OpenTelemetry pour une tâche Celery."""
    span = _spans.pop(task_id, None)
    if span is not None:
        with contextlib.suppress(Exception):  # pragma: no cover - defensive
            span.end()


def on_task_prerun(task_id: str, task_name: str, task_obj: Any) -> None:
    """Gère le démarrage d'une tâche Celery."""
    _starts[task_id] = time.time()
    _maybe_start_span(task_name, task_id, task_obj)


def on_task_postrun(task_id: str, task_name: str, state: str) -> None:
    """Gère la fin d'une tâche Celery."""
    start = _starts.pop(task_id, None)
    if start is not None:
        TASK_RUNTIME_SECONDS.labels(task=task_name).observe(max(0.0, time.time() - start))
    if state.upper() == "SUCCESS":
        TASK_SUCCESS.inc()
    _maybe_end_span(task_id)


def on_task_failure(task_id: str, task_name: str) -> None:
    """Gère l'échec d'une tâche Celery."""
    TASK_FAILURE.labels(task=task_name).inc()
    _maybe_end_span(task_id)


def on_task_retry(task_name: str) -> None:
    """Gère le retry d'une tâche Celery."""
    TASK_RETRY.labels(task=task_name).inc()


def bind_celery_signals(celery_app) -> None:  # type: ignore[no-untyped-def]
    """Attach Celery signal handlers to populate Prometheus metrics.

    Safe to call multiple times; signals register idempotently.
    """
    with contextlib.suppress(Exception):  # pragma: no cover - optional

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
    """Retourne un client Redis ou None si indisponible."""
    with contextlib.suppress(Exception):
        url = os.getenv("REDIS_URL")
        if not url:
            return None
        return redis.Redis.from_url(url, decode_responses=True)
    return None


def _queues_from_env() -> list[str]:
    """Parse les noms de files Celery depuis les variables d'environnement."""
    names = os.getenv("CELERY_QUEUE_NAMES") or "celery,default"
    # allow JSON array or comma list
    with contextlib.suppress(Exception):
        data = json.loads(names)
        if isinstance(data, list):
            return [str(x) for x in data]
    return [q.strip() for q in names.split(",") if q.strip()]


def _maybe_start_queue_depth_poller(interval: float = 5.0) -> None:
    """Démarre le poller de profondeur de file si Redis est disponible."""
    with _poller_state.lock:
        if _poller_state.started:
            return
        _poller_state.started = True

    client = _redis_client()
    if not client:
        return

    def _run() -> None:
        while not _poller_stop.is_set():
            for q in _queues_from_env():
                with contextlib.suppress(Exception):
                    depth = int(client.llen(q))  # type: ignore[attr-defined]
                    QUEUE_DEPTH.set(depth)
            _poller_stop.wait(interval)

    t = threading.Thread(target=_run, name="celery-queue-depth-poller", daemon=True)
    t.start()
