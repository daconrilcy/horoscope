"""Target adapter resolution for retrieval migration (dual-write/shadow-read).

Resolves a secondary backend used as migration target. Defaults to "weaviate".
"""

from __future__ import annotations

import contextlib
import os
import threading as _th
import time as _t

from backend.app.metrics import (
    RETRIEVAL_DUAL_WRITE_ERRORS,
    RETRIEVAL_DUAL_WRITE_OUTBOX_DROPPED,
    RETRIEVAL_DUAL_WRITE_OUTBOX_SIZE,
    RETRIEVAL_DUAL_WRITE_SKIPPED,
)


# Import circulaire évité - import local dans les fonctions
def _get_retrieval_proxy():
    """Import local pour éviter les imports circulaires."""
    from backend.services.retrieval_proxy import (  # noqa: PLC0415
        ElasticVectorAdapter,
        PineconeAdapter,
        WeaviateAdapter,
    )

    return ElasticVectorAdapter, PineconeAdapter, WeaviateAdapter


def get_target_backend_name() -> str:
    """Return the configured migration target backend name."""
    return (
        os.getenv("RETRIEVAL_TARGET_BACKEND")
        or os.getenv("RETRIEVAL_MIGRATION_TARGET")
        or "weaviate"
    ).lower()


def get_target_adapter():
    """Construct the adapter for the migration target backend.

    Supports: weaviate | pinecone | elastic (defaults to weaviate).
    """
    name = get_target_backend_name()
    # Import adapters lazily to avoid circular import during module load

    ElasticVectorAdapter, PineconeAdapter, WeaviateAdapter = _get_retrieval_proxy()

    if name == "pinecone":
        return PineconeAdapter()
    if name == "elastic":
        return ElasticVectorAdapter()
    if name == "weaviate":
        return WeaviateAdapter()
    raise ValueError(f"invalid RETRIEVAL_TARGET_BACKEND: {name}")


def write_to_target(_doc: dict, _tenant: str | None = None) -> None:
    """Write document to the target backend.

    Intentionally no-op for now. Tests may monkeypatch this to simulate success/failure. Real
    implementations should index documents to the target.
    """
    return None


# --- Dual-write safety: circuit breaker + outbox (in-memory) ---
class _DualWriteState:
    """État du circuit breaker et de l'outbox pour le dual-write."""

    def __init__(self):
        self.cb_fail_count: int = 0
        self.cb_open_until: float = 0.0
        self.outbox: list[tuple[dict, str | None, float]] = []
        self.outbox_lock = None  # lazy to avoid threading import at import-time for tests


_dw_state = _DualWriteState()


def _cb_threshold() -> int:
    try:
        return int(os.getenv("RETRIEVAL_DUAL_WRITE_CB_THRESHOLD") or 3)
    except Exception:
        return 3


def _cb_window_s() -> float:
    try:
        return float(os.getenv("RETRIEVAL_DUAL_WRITE_CB_WINDOW_S") or 30.0)
    except Exception:
        return 30.0


def _outbox_max() -> int:
    try:
        return int(os.getenv("RETRIEVAL_DUAL_WRITE_OUTBOX_MAX") or 1000)
    except Exception:
        return 1000


def _outbox_ttl_s() -> float:
    try:
        return float(os.getenv("RETRIEVAL_DUAL_WRITE_OUTBOX_TTL_S") or 86400.0)
    except Exception:
        return 86400.0


def _now() -> float:
    return _t.time()


def safe_write_to_target(doc: dict, tenant: str | None = None) -> None:
    """Write to target with circuit-breaker and outbox fallback.

    - If circuit is open, skip write and enqueue to outbox.
    - On failure, increment fail count, open circuit when threshold reached,
      and enqueue to outbox (bounded).
    """
    if _now() < _dw_state.cb_open_until:
        RETRIEVAL_DUAL_WRITE_SKIPPED.labels("circuit_open").inc()
        _enqueue_outbox(doc, tenant)
        return
    try:
        write_to_target(doc, tenant)
        _dw_state.cb_fail_count = 0
    except Exception:  # pragma: no cover - behavior verified via counters in tests
        _dw_state.cb_fail_count += 1
        _enqueue_outbox(doc, tenant)
        if _dw_state.cb_fail_count >= _cb_threshold():
            _dw_state.cb_open_until = _now() + _cb_window_s()
        # Errors total is already incremented in proxy; keep proxy as source of truth
        # but increment here as well in case safe_write_to_target is used directly.
        with contextlib.suppress(Exception):
            # Using generic labels; target/tenant not available here without duplication
            RETRIEVAL_DUAL_WRITE_ERRORS.labels(
                get_target_backend_name(), str(tenant or "default")
            ).inc()


def _enqueue_outbox(doc: dict, tenant: str | None) -> None:
    if _dw_state.outbox_lock is None:
        _dw_state.outbox_lock = _th.Lock()
    dropped = False
    with _dw_state.outbox_lock:
        if len(_dw_state.outbox) >= _outbox_max():
            # drop oldest
            with contextlib.suppress(Exception):
                _dw_state.outbox.pop(0)
            dropped = True
        _dw_state.outbox.append((doc, tenant, _now()))
        RETRIEVAL_DUAL_WRITE_OUTBOX_SIZE.set(len(_dw_state.outbox))
    if dropped:
        RETRIEVAL_DUAL_WRITE_OUTBOX_DROPPED.inc()


def replay_outbox(limit: int | None = None) -> int:
    """Replay items from outbox.

    Returns number of successful replays.
    """
    ok = 0
    n = len(_dw_state.outbox)
    if limit is not None:
        n = min(n, max(0, int(limit)))
    i = 0
    # Iterate over a snapshot to allow modification during replay
    while i < n:
        try:
            doc, tenant, ts = _dw_state.outbox.pop(0)
        except Exception:
            break
        try:
            write_to_target(doc, tenant)
            ok += 1
        except Exception:
            # Re-enqueue at end
            if _now() - ts <= _outbox_ttl_s():
                _dw_state.outbox.append((doc, tenant, ts))
            else:
                RETRIEVAL_DUAL_WRITE_OUTBOX_DROPPED.inc()
        i += 1
    with contextlib.suppress(Exception):
        RETRIEVAL_DUAL_WRITE_OUTBOX_SIZE.set(len(_dw_state.outbox))
    return ok


def _reset_cb_and_outbox_for_tests() -> None:  # pragma: no cover - used by tests
    _dw_state.cb_fail_count = 0
    _dw_state.cb_open_until = 0.0
    _dw_state.outbox = []
    with contextlib.suppress(Exception):
        RETRIEVAL_DUAL_WRITE_OUTBOX_SIZE.set(0)
