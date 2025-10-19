# ============================================================
# Module : backend/api/routes_retrieval.py
# Objet  : Endpoints internes pour /internal/retrieval/*.
# Notes  : Valider tailles input, labels tenant, sans données sensibles.
# ============================================================

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.retrieval_proxy import RetrievalProxy

router = APIRouter(prefix="/internal/retrieval", tags=["retrieval"])
_proxy = RetrievalProxy()


class EmbedRequest(BaseModel):
    """Payload pour l'endpoint d'embeddings."""

    texts: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    """Payload pour la recherche sémantique."""

    query: str = ""
    top_k: int = 5
    tenant: str | None = None


@router.post("/embed")
def embed(req: EmbedRequest) -> dict:
    """Encode une liste de textes.

    Returns:
        dict: {"vectors": [[...], ...]}
    """
    if not req.texts:
        raise HTTPException(status_code=400, detail="texts vide")
    vectors = _proxy.embed_texts(req.texts)
    return {"vectors": vectors}


@router.post("/search")
def search(req: SearchRequest) -> dict:
    """Recherche sémantique sur le corpus indexé.

    Returns:
        dict: {"results": [{"id": str, "score": float, "metadata": dict}, ...]}
    """
    if not req.query:
        raise HTTPException(status_code=400, detail="query vide")
    if req.top_k <= 0:
        raise HTTPException(status_code=400, detail="top_k invalide")
    results = _proxy.search(query=req.query, top_k=req.top_k, tenant=req.tenant)
    return {"results": results}
