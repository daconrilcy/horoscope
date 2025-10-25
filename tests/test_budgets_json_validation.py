"""Tests pour la validation des budgets JSON.

Ce module teste la gestion des erreurs dans la configuration des budgets des tenants.
"""

from __future__ import annotations

from backend.app.cost_controls import BudgetManager


def test_malformed_budgets_json_fallback(monkeypatch) -> None:
    """Teste que les budgets JSON malformés utilisent un fallback vide."""
    monkeypatch.setenv("TENANT_BUDGETS_JSON", "{not: valid json}")
    bm = BudgetManager.from_env()
    assert bm.budgets == {}
