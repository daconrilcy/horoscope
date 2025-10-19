# ============================================================
# Module : backend/app/cost_controls.py
# Objet  : Guardrails de coût LLM (budgets/alertes/dégradés).
# ============================================================

from __future__ import annotations


def check_budget(tenant: str, spent_usd: float, budget_usd: float) -> str:
    """Retourne l'état budgétaire ('ok' | 'warn' | 'block')."""
    if budget_usd <= 0:
        return "ok"
    ratio = spent_usd / budget_usd
    if ratio >= 1.0:
        return "block"
    if ratio >= 0.8:
        return "warn"
    return "ok"


def degraded_response() -> str:
    """Message standard en cas de blocage budgétaire (dégradé gracieux)."""
    return "Budget atteint : réponse limitée. Réessayez plus tard ou réduisez le contexte."
