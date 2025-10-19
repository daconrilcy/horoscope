from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Document(BaseModel):
    id: str
    text: str
    meta: dict[str, Any] = Field(default_factory=dict)


class Query(BaseModel):
    text: str
    k: int = 5


class ScoredDocument(BaseModel):
    doc: Document
    score: float
