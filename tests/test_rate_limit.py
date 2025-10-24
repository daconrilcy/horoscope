"""Tests pour la limitation de débit et les budgets.

Ce module teste les fonctionnalités de limitation de débit par tenant et les contrôles de budget
dans l'application.
"""

from __future__ import annotations

from backend.app.cost_controls import BudgetManager, degraded_response
from backend.app.metrics import LLM_COST_USD, RATE_LIMIT_BLOCKS
from backend.core.constants import (
    TEST_METRICS_COST_THRESHOLD,
)


def test_qps_rate_limit_per_tenant(monkeypatch) -> None:
    """Teste que la limitation de débit par tenant fonctionne correctement."""
    from backend.apigw.rate_limit import RateLimitConfig, SlidingWindowRateLimiter

    # Test direct du rate limiter
    config = RateLimitConfig(requests_per_minute=1)
    limiter = SlidingWindowRateLimiter(config)

    # First request should be allowed
    result1 = limiter.check_rate_limit("tenant1")
    assert result1.allowed is True
    assert result1.remaining == 0  # 1 - 1 = 0

    # Second request should be blocked
    result2 = limiter.check_rate_limit("tenant1")
    assert result2.allowed is False
    assert result2.remaining == 0
    assert result2.retry_after is not None


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
    before = RATE_LIMIT_BLOCKS.labels(route="/budget", reason="budget")._value.get()  # type: ignore[attr-defined]
    st2 = bm.record_usage("tA", model="gpt-4o-mini", usd=2.1)
    assert st2 == "block"
    after = RATE_LIMIT_BLOCKS.labels(route="/budget", reason="budget")._value.get()  # type: ignore[attr-defined]
    assert after >= before + 1
    # degraded response helper
    msg = degraded_response()
    assert "Budget atteint" in msg
