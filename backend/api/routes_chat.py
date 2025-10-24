"""Routes de chat et conseils astrologiques.

Ce module fournit les endpoints pour les fonctionnalités de chat, incluant les conseils
astrologiques et la gestion des tokens.
"""

from __future__ import annotations

import os
import time

import tiktoken
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.api.routes_auth import get_current_user
from backend.app.metrics import (
    CHAT_LATENCY,
    CHAT_REQUESTS,
    LLM_GUARD_BLOCKS,
    LLM_GUARD_WARN,
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
_current_user_dep = Depends(get_current_user)


class ChatPayload(BaseModel):
    """Payload pour les requêtes de chat astrologique."""

    chart_id: str
    question: str


@router.post("/advise")
def advise(payload: ChatPayload, request: Request, user=_current_user_dep):
    """Fournit des conseils astrologiques basés sur un thème natal et une question."""
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
        rule = str(exc)
        env_flag = os.getenv("FF_GUARD_ENFORCE") or "true"
        val = env_flag.strip().lower()
        enforce = val in {"1", "true", "yes", "on"}
        if enforce:
            LLM_GUARD_BLOCKS.labels(rule=rule).inc()
            raise HTTPException(status_code=400, detail=rule) from exc
        # warn-only path: increment metric and continue with safe fallback
        LLM_GUARD_WARN.labels(rule=rule).inc()
        q = (payload.question or "").strip()
        try:
            max_len = int(getattr(container.settings, "LLM_GUARD_MAX_INPUT_LEN", 1000) or 1000)
        except Exception:
            max_len = 1000
        if rule == "question_too_long" and len(q) > max_len:
            q = q[:max_len]
        clean = {"question": q}
    text, usage = orch.advise(chart, today, clean["question"])
    tokens = estimate_tokens(text, model, usage)
    LLM_TOKENS_TOTAL.labels(tenant=tenant_lbl, model=model_lbl).inc(tokens)
    safe = validate_output(text, tenant=tenant)
    CHAT_LATENCY.labels(tenant=tenant_lbl, model=model_lbl).observe(time.perf_counter() - start_t)
    return {"answer": safe, "date": today.get("date")}
