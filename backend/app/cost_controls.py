# ============================================================
# Module : backend/app/cost_controls.py
# Objet  : Guardrails de coût LLM (budgets/alertes/dégradés).
# ============================================================

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import structlog

from backend.app.metrics import LLM_COST_USD, RATE_LIMIT_BLOCKS


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


@dataclass
class BudgetManager:
    """Gestion des budgets par tenant et cumul des coûts.

    - Budgets chargés depuis env:
      - TENANT_DEFAULT_BUDGET_USD (float, défaut 0 = illimité)
      - TENANT_BUDGETS_JSON (ex: '{"t1": 5.0, "t2": 10.0}')
    - Enregistre les coûts via `record_usage` et met à jour métrique `llm_cost_usd_total`.
    """

    default_budget: float = 0.0
    budgets: dict[str, float] = field(default_factory=dict)
    spent: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> BudgetManager:
        default_budget = float(os.getenv("TENANT_DEFAULT_BUDGET_USD", "0") or 0)
        budgets_json = os.getenv("TENANT_BUDGETS_JSON") or "{}"
        logger = structlog.get_logger(__name__)
        try:
            budgets = json.loads(budgets_json)
        except Exception as exc:  # log warn and fallback
            logger.warning("invalid_tenant_budgets_json", msg="fallback to {}", error=str(exc))
            budgets = {}
        # ensure float values
        budgets = {str(k): float(v) for k, v in budgets.items()}
        return cls(default_budget=default_budget, budgets=budgets)

    def get_budget(self, tenant: str) -> float:
        return float(self.budgets.get(tenant, self.default_budget))

    def get_status(self, tenant: str) -> str:
        return check_budget(tenant, float(self.spent.get(tenant, 0.0)), self.get_budget(tenant))

    def record_usage(self, tenant: str, model: str, usd: float) -> str:
        if usd <= 0:
            return self.get_status(tenant)
        self.spent[tenant] = float(self.spent.get(tenant, 0.0)) + float(usd)
        # increment Prom counter
        LLM_COST_USD.labels(tenant=tenant, model=model).inc(float(usd))
        status = self.get_status(tenant)
        if status == "block":
            RATE_LIMIT_BLOCKS.labels(tenant=tenant, reason="budget").inc()
        return status


# Singleton budget manager used by the app
budget_manager = BudgetManager.from_env()
