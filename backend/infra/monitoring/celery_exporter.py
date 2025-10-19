# ============================================================
# Module : backend/infra/monitoring/celery_exporter.py
# Objet  : Exporter Prometheus pour métriques Celery (squelette).
# ============================================================

from __future__ import annotations

from prometheus_client import Counter, Gauge, generate_latest

QUEUE_DEPTH = Gauge("celery_queue_depth", "Taille de la file Celery")
TASK_SUCCESS = Counter("celery_task_success_total", "Tasks réussies")
TASK_FAILURE = Counter("celery_task_failure_total", "Tasks échouées")


def metrics_wsgi_app(environ, start_response):  # type: ignore[no-untyped-def]
    """WSGI simple pour exposer les métriques Prometheus."""
    data = generate_latest()
    status = "200 OK"
    headers = [("Content-Type", "text/plain; version=0.0.4")]
    start_response(status, headers)
    return [data]
