"""
Module: celery_app.

But: Initialiser l’instance Celery de l’application et charger la config runtime.

Ajout: branche l’instrumentation Prometheus/OTEL des tâches Celery via bind_celery_signals.
Notes:
- Aucun secret loggé.
- Le binding est idempotent et no-op si Celery/OTEL non disponibles.
"""

from celery import Celery

from backend.core.container import container

celery_app = Celery(
    "horoscope",
    broker=container.settings.CELERY_BROKER_URL,
    backend=container.settings.CELERY_RESULT_BACKEND,
)
# Load configuration from module (retries, timeouts, acks)
celery_app.config_from_object("backend.app.celeryconfig")
celery_app.conf.task_routes = {"backend.tasks.*": {"queue": "default"}}

# Brancher l’instrumentation des tâches (Prom + OTEL)
try:
    # Import local pour éviter coûts si non utilisé côté API
    from backend.infra.monitoring.celery_exporter import bind_celery_signals

    bind_celery_signals(celery_app)
except Exception as exc:  # ne jamais casser le worker pour l’observabilité
    # Log minimal sans secrets
    import logging

    logging.getLogger(__name__).warning("celery_signals_binding_failed: %s", type(exc).__name__)

__all__ = ["celery_app"]
