from __future__ import annotations

from backend.app.cost_controls import BudgetManager


def test_malformed_budgets_json_fallback(monkeypatch) -> None:
    monkeypatch.setenv("TENANT_BUDGETS_JSON", "{not: valid json}")
    bm = BudgetManager.from_env()
    assert bm.budgets == {}

