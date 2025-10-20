from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.routes_auth import get_current_user
from backend.app.middleware_llm_guard import sanitize_input, validate_output
from backend.core.container import container
from backend.domain.chat_orchestrator import ChatOrchestrator
from backend.domain.entitlements import require_entitlement
from backend.domain.services import HoroscopeService

router = APIRouter(prefix="/chat", tags=["chat"])
orch = ChatOrchestrator()


class ChatPayload(BaseModel):
    chart_id: str
    question: str


@router.post("/advise")
def advise(payload: ChatPayload, user=Depends(get_current_user)):
    require_entitlement(user, "plus")
    chart = container.chart_repo.get(payload.chart_id)
    if not chart:
        raise HTTPException(status_code=404, detail="chart_not_found")
    service = HoroscopeService(container.astro, container.content_repo, container.chart_repo)
    today = service.get_today(payload.chart_id)
    # LLM Guard: sanitize input and mask PII in output
    try:
        clean = sanitize_input({"question": payload.question})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    text = orch.advise(chart, today, clean["question"])
    safe = validate_output(text, tenant=user.get("tenant"))
    return {"answer": safe, "date": today.get("date")}
