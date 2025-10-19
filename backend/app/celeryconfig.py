# ============================================================
# Module : backend/app/celeryconfig.py
# Objet  : Configuration centralisée Celery (retries, timeouts).
# ============================================================

from __future__ import annotations

# Retries & acks
task_acks_late = True
task_time_limit = 300  # secondes
broker_pool_limit = 10

# Exemple de politique de retry (à appliquer par task)
max_retries = 5
retry_backoff = True
retry_backoff_max = 60  # secondes
