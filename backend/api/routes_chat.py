from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.api.routes_auth import get_current_user
from backend.app.metrics import (
    CHAT_LATENCY,
    CHAT_REQUESTS,
    LLM_TOKENS_TOTAL,
    TOKEN_COUNT_STRATEGY_INFO,
    labelize_model,
    labelize_tenant,
)
from backend.app.middleware_llm_guard import sanitize_input, validate_output
from backend.core.container import container
from backend.core.settings import get_settings
from backend.domain.chat_orchestrator import ChatOrchestrator
from backend.domain.entitlements import require_entitlement
from backend.domain.services import HoroscopeService

DEFAULT_MODEL_ENCODING = "cl100k_base"


def estimate_tokens(text: str, model: str | None, usage: dict | None) -> int:
    """Estimate tokens using configured strategy: auto|api|tiktoken|words.

    Never logs text; only counts. Falls back gracefully across methods.
    """
    settings = get_settings()
    strategy = (getattr(settings, "TOKEN_COUNT_STRATEGY", "auto") or "auto").lower()
    TOKEN_COUNT_STRATEGY_INFO.labels(strategy=strategy).set(1)

    def _from_api() -> int | None:
        if usage and isinstance(usage, dict):
            val = usage.get("total_tokens")
            if isinstance(val, int | float):
                return int(val)
        return None

    def _from_tiktoken() -> int | None:
        try:
            import tiktoken  # type: ignore

            enc = (
                tiktoken.encoding_for_model(model)
                if model
                else tiktoken.get_encoding(DEFAULT_MODEL_ENCODING)
            )
            return len(enc.encode(text or ""))
        except Exception:
            return None

    def _from_words() -> int:
        return max(0, len((text or "").split()))

    if strategy == "api":
        return _from_api() or _from_words()
    if strategy == "tiktoken":
        return _from_tiktoken() or _from_words()
    if strategy == "words":
        return _from_words()
    # auto
    return _from_api() or _from_tiktoken() or _from_words()


router = APIRouter(prefix="/chat", tags=["chat"])
orch = ChatOrchestrator()


class ChatPayload(BaseModel):
    chart_id: str
    question: str


@router.post("/advise")
def advise(payload: ChatPayload, request: Request, user=Depends(get_current_user)):
    require_entitlement(user, "plus")
    chart = container.chart_repo.get(payload.chart_id)
    if not chart:
        raise HTTPException(status_code=404, detail="chart_not_found")
    service = HoroscopeService(container.astro, container.content_repo, container.chart_repo)
    today = service.get_today(payload.chart_id)
    # LLM Guard + business metrics
    # Prefer tenant from authenticated user (JWT/claims) over header/state
    tenant = (
        user.get("tenant") or getattr(getattr(request, "state", None), "tenant", None) or "default"
    )
    model = getattr(orch.llm, "model", "unknown")
    start_t = time.perf_counter()
    settings = container.settings
    tenant_lbl = labelize_tenant(tenant, settings.ALLOWED_TENANTS)
    model_lbl = labelize_model(model, settings.ALLOWED_LLM_MODELS)
    CHAT_REQUESTS.labels(tenant=tenant_lbl, model=model_lbl).inc()
    try:
        clean = sanitize_input({"question": payload.question})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    text, usage = orch.advise(chart, today, clean["question"])
    tokens = estimate_tokens(text, model, usage)
    LLM_TOKENS_TOTAL.labels(tenant=tenant_lbl, model=model_lbl).inc(tokens)
    safe = validate_output(text, tenant=tenant)
    CHAT_LATENCY.labels(tenant=tenant_lbl, model=model_lbl).observe(time.perf_counter() - start_t)
    return {"answer": safe, "date": today.get("date")}
