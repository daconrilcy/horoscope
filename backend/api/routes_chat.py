from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.domain.chat_orchestrator import ChatOrchestrator

router = APIRouter(prefix="/chat", tags=["chat"])
orch = ChatOrchestrator()


class ChatPayload(BaseModel):
    chart_id: str | None = None
    question: str


@router.post("/advise")
def advise(payload: ChatPayload):
    advice = orch.advise(chart={"id": payload.chart_id}, question=payload.question)
    return {"advice": advice}
