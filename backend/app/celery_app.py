



from celery import Celery

from backend.core.container import container

celery_app = Celery(
    "horoscope",
    broker=container.settings.CELERY_BROKER_URL,
    backend=container.settings.CELERY_RESULT_BACKEND,
)
celery_app.conf.task_routes = {"backend.tasks.*": {"queue": "default"}}

