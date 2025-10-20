# ============================================================
# Module : backend/api/routes_retrieval.py
# Objet  : Endpoints internes pour /internal/retrieval/*.
# Notes  : Valider tailles input, labels tenant, sans données sensibles.
# ============================================================

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..services.retrieval_proxy import (
    RetrievalBackendHTTPError,
    RetrievalNetworkError,
    RetrievalProxy,
)
from backend.domain.tenancy import tenant_from_context

router = APIRouter(prefix="/internal/retrieval", tags=["retrieval"])
_proxy = RetrievalProxy()


class EmbedRequest(BaseModel):
    """Payload pour l'endpoint d'embeddings."""

    texts: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    """Payload pour la recherche sémantique."""

    query: str = ""
    top_k: int = 5
    offset: int = 0
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
def search(req: SearchRequest, request: Request) -> dict:
    """Recherche sémantique sur le corpus indexé.

    Returns:
        dict: {"results": [{"id": str, "score": float, "metadata": dict}, ...]}
    """
    # Normaliser query et valider bornes
    q = (req.query or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="query vide")
    if req.top_k < 1 or req.top_k > 50:
        raise HTTPException(status_code=400, detail="top_k invalide")
    if req.offset < 0:
        raise HTTPException(status_code=400, detail="offset invalide")

    # Correlation id / trace id (via header Request-ID si présent)
    request_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID")
    logger = structlog.get_logger(__name__).bind(request_id=request_id)
    logger.info("retrieval_search", top_k=req.top_k, offset=req.offset)

    # Derive tenant from context (JWT/claims not present on internal route; use header if any)
    header_tenant = request.headers.get("X-Tenant")
    eff_tenant = tenant_from_context(user=None, header_tenant=header_tenant) if not req.tenant else req.tenant
    try:
        results = _proxy.search(query=q, top_k=req.top_k, tenant=eff_tenant)
    except RetrievalBackendHTTPError as exc:
        if exc.status_code == 429:
            raise HTTPException(status_code=429, detail="rate limited") from exc
        if exc.status_code in (400, 422):
            raise HTTPException(status_code=exc.status_code, detail="invalid request") from exc
        raise HTTPException(status_code=400, detail="client error") from exc
    except RetrievalNetworkError as exc:
        # Transformer les erreurs réseau en 502 côté API, comme requis par #2.
        raise HTTPException(status_code=502, detail="retrieval backend unavailable") from exc
    return {"results": results}
