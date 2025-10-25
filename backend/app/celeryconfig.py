"""Configuration centralisée Celery pour les tâches asynchrones.

Ce module définit la configuration globale de Celery incluant les politiques de retry, timeouts et
limites de connexion au broker.
"""

# ============================================================
# Module : backend/app/celeryconfig.py
# Objet  : Configuration centralisée Celery (retries, timeouts).
# ============================================================

from __future__ import annotations

# Retries & acks
task_acks_late = True
task_reject_on_worker_lost = True
worker_prefetch_multiplier = 1
task_time_limit = 300  # secondes
broker_pool_limit = 10

# Politique de retry par défaut (à spécialiser par tâche)
max_retries = 5
retry_backoff = True
retry_backoff_max = 60  # secondes
