"""
Tests pour la limitation de débit et les budgets.

Ce module teste les fonctionnalités de limitation de débit par tenant et les contrôles de budget
dans l'application.
"""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from backend.app.cost_controls import BudgetManager, degraded_response
from backend.app.main import app
from backend.app.metrics import LLM_COST_USD, RATE_LIMIT_BLOCKS
from backend.core.constants import (
    TEST_HTTP_STATUS_OK,
    TEST_HTTP_STATUS_TOO_MANY_REQUESTS,
    TEST_METRICS_COST_THRESHOLD,
)


def test_qps_rate_limit_per_tenant(monkeypatch) -> None:
    """Teste que la limitation de débit par tenant fonctionne correctement."""
    monkeypatch.setenv("RATE_LIMIT_TENANT_QPS", "1")
    c = TestClient(app)
    headers = {"X-Tenant": "t1"}
    ok = c.get("/health", headers=headers)
    assert ok.status_code == TEST_HTTP_STATUS_OK
    # second within same second should be 429
    blocked = c.get("/health", headers=headers)
    assert blocked.status_code == TEST_HTTP_STATUS_TOO_MANY_REQUESTS
    # sleep to cross window and allow again
    time.sleep(1.1)
    ok2 = c.get("/health", headers=headers)
    assert ok2.status_code == TEST_HTTP_STATUS_OK


def test_budget_warn_and_block(monkeypatch) -> None:
    """Teste que les avertissements et blocages de budget fonctionnent."""
    monkeypatch.setenv("TENANT_DEFAULT_BUDGET_USD", "10")
    bm = BudgetManager.from_env()
    # spend 8 -> 80% warn
    st1 = bm.record_usage("tA", model="gpt-4o-mini", usd=8.0)
    assert st1 == "warn"
    # counters increased
    val = LLM_COST_USD.labels(tenant="tA", model="gpt-4o-mini")._value.get()  # type: ignore[attr-defined]
    assert val >= TEST_METRICS_COST_THRESHOLD
    # spend 2.1 more -> block
    before = RATE_LIMIT_BLOCKS.labels(tenant="tA", reason="budget")._value.get()  # type: ignore[attr-defined]
    st2 = bm.record_usage("tA", model="gpt-4o-mini", usd=2.1)
    assert st2 == "block"
    after = RATE_LIMIT_BLOCKS.labels(tenant="tA", reason="budget")._value.get()  # type: ignore[attr-defined]
    assert after >= before + 1
    # degraded response helper
    msg = degraded_response()
    assert "Budget atteint" in msg
