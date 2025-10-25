"""Task idempotency and failure tracking helpers (Redis or in-memory).

- IdempotencyStore: simple `acquire(key, ttl)` to deduplicate task execution.
- FailureTracker: counts failures per task-id and emits to a poison queue
  (DLQ) when a threshold is exceeded.

Idempotency key rule (recommended):
    task:{name}:{param_significant}

Use `make_idem_key("render_pdf", chart_id)` to compose keys consistently.

These helpers are pure-Python with a Redis backend if `REDIS_URL` is set;
otherwise they fallback to an in-memory store suitable for unit tests.
They also expose Prometheus counters via
`backend.infra.monitoring.celery_exporter`.
"""

from __future__ import annotations

import base64
import contextlib
import functools
import json
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    redis = None  # type: ignore

from backend.infra.monitoring.celery_exporter import DLQ_TOTAL, TASK_FAILURE, TASK_RETRY

try:  # metrics are optional in unit tests
    from prometheus_client import Counter as _PromCounter  # type: ignore

    WORKER_IDEMPOTENCY_ATTEMPTS_TOTAL = _PromCounter(
        "worker_idempotency_attempts_total",
        "Idempotency attempts at worker",
        ["task", "result"],
    )
    WORKER_IDEMPOTENCY_STATE_TOTAL = _PromCounter(
        "worker_idempotency_state_total",
        "Idempotency state transitions",
        ["task", "state"],
    )
except Exception:  # pragma: no cover
    WORKER_IDEMPOTENCY_ATTEMPTS_TOTAL = None  # type: ignore[assignment]
    WORKER_IDEMPOTENCY_STATE_TOTAL = None  # type: ignore[assignment]


def make_idem_key(task: str, *parts: str) -> str:
    """Compose a stable idempotency key following `task:{name}:{param}` rule."""
    safe_parts = [str(p).replace("\n", " ").replace("\r", " ") for p in parts]
    suffix = ":".join(safe_parts) if safe_parts else ""
    return f"task:{task}:{suffix}" if suffix else f"task:{task}"


class _InMemoryKV:
    def __init__(self) -> None:
        self._exp: dict[str, float] = {}
        self._vals: dict[str, str] = {}
        self._lists: dict[str, list[str]] = {}

    def setnx(self, key: str, value: str, ex: int) -> bool:
        now = time.time()
        # Purge expired
        exp = self._exp.get(key)
        if exp is not None and exp <= now:
            self._exp.pop(key, None)
            self._vals.pop(key, None)
        if key in self._vals:
            return False
        self._vals[key] = value
        self._exp[key] = now + ex
        return True

    def incr(self, key: str) -> int:
        v = int(self._vals.get(key, "0")) + 1
        self._vals[key] = str(v)
        return v

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        now = time.time()
        self._vals[key] = value
        if ex:
            self._exp[key] = now + int(ex)

    def rpush(self, list_key: str, value: str) -> None:
        self._lists.setdefault(list_key, []).append(value)

    def lrange(self, list_key: str, start: int, end: int) -> list[str]:
        return list(self._lists.get(list_key, []))[start : end + 1]


def _redis_client():  # pragma: no cover - smoke path
    url = os.getenv("REDIS_URL")
    if not url or not redis:
        return None
    try:
        return redis.Redis.from_url(url, decode_responses=True)
    except Exception:
        return None


@dataclass
class IdempotencyStore:
    """Store pour l'idempotence des tâches avec TTL."""

    ttl_seconds: int = 300
    client: object | None = field(default=None)

    def __post_init__(self) -> None:
        """Initialise le client Redis ou fallback en mémoire."""
        if self.client is None:
            self.client = _redis_client() or _InMemoryKV()

    def acquire(self, key: str, ttl: int | None = None) -> bool:
        """Acquiert une clé d'idempotence avec TTL (verrou in_progress)."""
        ttl = int(ttl or self.ttl_seconds)
        if hasattr(self.client, "setnx"):
            return self.client.setnx(key, "1", ex=ttl)  # type: ignore[no-any-return]
        # Redis client
        try:
            ok = self.client.set(name=key, value="1", nx=True, ex=ttl)  # type: ignore[attr-defined]
            return bool(ok)
        except Exception:
            return True

    def set_state(self, key: str, state: str, ttl: int | None = None) -> None:
        """Enregistre un état (in_progress/succeeded/failed) avec TTL."""
        ttl = int(ttl or self.ttl_seconds)
        if hasattr(self.client, "set"):
            try:
                self.client.set(key, state, ex=ttl)  # type: ignore[no-untyped-call]
                return
            except Exception:
                pass
        with contextlib.suppress(Exception):
            self.client.set(name=key, value=state, ex=ttl)  # type: ignore[attr-defined]


@dataclass
class FailureTracker:
    """Tracker pour les échecs de tâches avec DLQ."""

    client: object | None = field(default=None)
    dlq_list: str = "celery:dlq"

    def __post_init__(self) -> None:
        """Initialise le client Redis ou fallback en mémoire."""
        if self.client is None:
            self.client = _redis_client() or _InMemoryKV()

    def record_retry(self, task: str) -> None:
        """Enregistre un retry de tâche."""
        TASK_RETRY.labels(task=task).inc()

    def on_failure(
        self,
        task: str,
        task_id: str,
        max_failures: int | None = None,
        reason: str = "max_failures",
    ) -> bool:
        """Record a failure and push to DLQ if threshold exceeded.

        Threshold comes from `CELERY_MAX_FAILURES_BEFORE_DLQ` env when not provided.
        DLQ entry is a JSON with {task, task_id, reason, ts}.
        """
        TASK_FAILURE.labels(task=task).inc()
        if max_failures is None:
            try:
                max_failures = int(os.getenv("CELERY_MAX_FAILURES_BEFORE_DLQ", "3") or 3)
            except Exception:
                max_failures = 3
        key = f"celery:fail:{task}:{task_id}"
        # incr count
        try:
            if hasattr(self.client, "incr"):
                count = self.client.incr(key)  # type: ignore[no-untyped-call]
            else:
                count = int(self.client.incr(key))  # type: ignore[attr-defined]
        except Exception:
            count = max_failures
        if count > max_failures:
            # push to DLQ
            try:
                payload = json.dumps(
                    {
                        "task": task,
                        "task_id": task_id,
                        "reason": reason,
                        "ts": time.time(),
                    }
                )
                if hasattr(self.client, "rpush"):
                    self.client.rpush(self.dlq_list, payload)  # type: ignore[no-untyped-call]
                else:
                    self.client.rpush(self.dlq_list, payload)  # type: ignore[attr-defined]
            except Exception:
                pass
            DLQ_TOTAL.labels(queue=self.dlq_list).inc()
            return True
        return False


# Module singletons
idempotency_store = IdempotencyStore()
failure_tracker = FailureTracker()


def _normalize_for_json(value: Any) -> Any:
    """Normalize complex values for canonical JSON (bytes, sets, datetime)."""
    normalized: Any
    if isinstance(value, (bytes, bytearray)):
        normalized = base64.b64encode(bytes(value)).decode("ascii")
    elif isinstance(value, (set, frozenset)):
        normalized = sorted([_normalize_for_json(v) for v in value])
    elif isinstance(value, (list, tuple)):
        normalized = [_normalize_for_json(v) for v in value]
    elif isinstance(value, dict):
        normalized = {str(k): _normalize_for_json(v) for k, v in value.items()}
    elif isinstance(value, datetime):
        v = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        normalized = v.astimezone(UTC).isoformat()
    else:
        try:
            json.dumps(value)
            normalized = value
        except Exception:
            normalized = str(value)
    return normalized


def canonical_task_key(task_name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    """Construis une clé canonique stable depuis nom de tâche et args/kwargs normalisés."""
    payload = {
        "task": str(task_name),
        "args": _normalize_for_json(list(args)),
        "kwargs": _normalize_for_json(dict(kwargs)),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return make_idem_key(task_name, raw)


def _record_attempt(task_name: str, result: str) -> None:
    if WORKER_IDEMPOTENCY_ATTEMPTS_TOTAL:
        WORKER_IDEMPOTENCY_ATTEMPTS_TOTAL.labels(task=task_name, result=result).inc()


def _record_state(task_name: str, state: str) -> None:
    if WORKER_IDEMPOTENCY_STATE_TOTAL:
        WORKER_IDEMPOTENCY_STATE_TOTAL.labels(task=task_name, state=state).inc()


def idempotent_task(
    key_builder=None, ttl_seconds: int = 300, on_duplicate_return: object = "duplicate"
):
    """Decorate a task function to enforce idempotence via shared store.

    La clé d'idempotence est construite dynamiquement par `key_builder(*args, **kwargs)`.
    Si la clé existe déjà (dans la fenêtre TTL), la fonction décorée renvoie immédiatement
    `on_duplicate_return` sans exécuter la logique métier.

    Args:
        key_builder: Fonction construisant une clé stable à partir des arguments.
        ttl_seconds: Fenêtre d'idempotence en secondes.
        on_duplicate_return: Valeur renvoyée si doublon détecté.
    """

    def _decorator(func):
        @functools.wraps(func)
        def _wrapper(*args, **kwargs):
            task_name = getattr(func, "__name__", "task")
            kb = key_builder or (lambda *a, **k: canonical_task_key(task_name, a, k))
            key = kb(*args, **kwargs)
            try:
                ok = idempotency_store.acquire(key, ttl=ttl_seconds)
            except Exception:
                ok = True
            if not ok:
                _record_attempt(task_name, "deduped")
                return on_duplicate_return
            _record_attempt(task_name, "allowed")
            _record_state(task_name, "in_progress")
            with contextlib.suppress(Exception):
                idempotency_store.set_state(f"{key}:state", "in_progress", ttl_seconds)
            try:
                result = func(*args, **kwargs)
                _record_state(task_name, "succeeded")
                with contextlib.suppress(Exception):
                    idempotency_store.set_state(f"{key}:state", "succeeded", ttl_seconds)
                return result
            except Exception:
                _record_state(task_name, "failed")
                with contextlib.suppress(Exception):
                    idempotency_store.set_state(f"{key}:state", "failed", ttl_seconds)
                raise

        return _wrapper

    return _decorator
