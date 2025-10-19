# ============================================================
# Tests : tests/test_cost_controls.py
# Objet  : Guardrails de coût.
# ============================================================

from __future__ import annotations

from backend.app.cost_controls import check_budget


def test_budget_warn():
    assert check_budget("t1", 80, 100) == "warn"


def test_budget_block():
    assert check_budget("t1", 100, 100) == "block"
