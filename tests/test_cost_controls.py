# ============================================================
# Tests : tests/test_cost_controls.py
# Objet  : Guardrails de coût.
# ============================================================
"""Tests pour les contrôles de coût.

Ce module teste les garde-fous de coût et les budgets des tenants dans l'application.
"""

from __future__ import annotations

from backend.app.cost_controls import check_budget


def test_budget_warn():
    """Teste que l'avertissement de budget est déclenché à 80%."""
    assert check_budget("t1", 80, 100) == "warn"


def test_budget_block():
    """Teste que le blocage de budget est déclenché à 100%."""
    assert check_budget("t1", 100, 100) == "block"
