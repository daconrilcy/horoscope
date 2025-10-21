from __future__ import annotations

import os
from typing import Any

from prometheus_client import generate_latest

from backend.services import retrieval_target as rt


def _metric_value_contains(fragment: str) -> bool:
    scrape = generate_latest().decode("utf-8")
    return fragment in scrape


def test_circuit_breaker_opens_and_skips(monkeypatch: Any) -> None:
    # Reset state and set low threshold
    rt._reset_cb_and_outbox_for_tests()
    monkeypatch.setenv("RETRIEVAL_DUAL_WRITE_CB_THRESHOLD", "2")
    monkeypatch.setenv("RETRIEVAL_DUAL_WRITE_CB_WINDOW_S", "60")
    monkeypatch.setenv("RETRIEVAL_DUAL_WRITE_OUTBOX_MAX", "10")

    # Make target write fail first
    called: dict[str, int] = {"n": 0}

    def _fail(doc: dict, tenant: str | None = None) -> None:  # type: ignore[unused-argument]
        called["n"] += 1
        raise RuntimeError("boom")

    monkeypatch.setattr(rt, "write_to_target", _fail)

    # Two failures -> breaker should open; third call should be skipped (circuit_open)
    rt.safe_write_to_target({"id": "a"}, "t1")
    rt.safe_write_to_target({"id": "b"}, "t1")
    before = generate_latest().decode("utf-8").count('retrieval_dual_write_skipped_total{reason="circuit_open"}')
    rt.safe_write_to_target({"id": "c"}, "t1")
    after = generate_latest().decode("utf-8").count('retrieval_dual_write_skipped_total{reason="circuit_open"}')
    assert after == before + 1

    # Now make writes succeed and replay outbox; should consume queued items
    def _ok(doc: dict, tenant: str | None = None) -> None:  # type: ignore[unused-argument]
        return None

    monkeypatch.setattr(rt, "write_to_target", _ok)
    replayed = rt.replay_outbox(limit=None)
    assert isinstance(replayed, int)


def test_outbox_ttl_and_dropped_counter(monkeypatch: Any) -> None:
    rt._reset_cb_and_outbox_for_tests()
    monkeypatch.setenv("RETRIEVAL_DUAL_WRITE_OUTBOX_MAX", "1")
    monkeypatch.setenv("RETRIEVAL_DUAL_WRITE_OUTBOX_TTL_S", "0")

    # Always fail -> items stay and then drop by TTL during replay
    monkeypatch.setattr(rt, "write_to_target", lambda d, t=None: (_ for _ in ()).throw(RuntimeError("fail")))

    # Enqueue two items via safe_write (simulate breaker open to skip actual call)
    monkeypatch.setenv("RETRIEVAL_DUAL_WRITE_CB_THRESHOLD", "0")
    rt.safe_write_to_target({"id": "x"}, "t")
    rt.safe_write_to_target({"id": "y"}, "t")

    # Third enqueue should evict oldest and increment dropped counter
    from backend.app import metrics as m
    before_drop = float(m.RETRIEVAL_DUAL_WRITE_OUTBOX_DROPPED._value.get())  # type: ignore[attr-defined]
    rt.safe_write_to_target({"id": "z"}, "t")
    after_drop = float(m.RETRIEVAL_DUAL_WRITE_OUTBOX_DROPPED._value.get())  # type: ignore[attr-defined]
    assert after_drop >= before_drop + 1.0

    # Replay with TTL==0 should drop failing items (and not loop)
    rt.replay_outbox(limit=5)
