"""Tests supplémentaires pour les routes de récupération.

Ce module teste des cas supplémentaires des routes de récupération, incluant les erreurs de
validation et les cas limites.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import routes_retrieval as rr
from backend.core.constants import (
    TEST_HTTP_STATUS_BAD_GATEWAY,
    TEST_HTTP_STATUS_BAD_REQUEST,
    TEST_HTTP_STATUS_TOO_MANY_REQUESTS,
)
from backend.services.retrieval_proxy import (
    RetrievalBackendHTTPError,
    RetrievalNetworkError,
)


def _app() -> FastAPI:
    """Crée une application FastAPI avec les routes de récupération."""
    app = FastAPI()
    app.include_router(rr.router)
    return app


def test_embed_400_on_empty_texts() -> None:
    """Teste que l'embedding retourne 400 pour une liste de textes vide."""
    client = TestClient(_app())
    resp = client.post("/internal/retrieval/embed", json={"texts": []})
    assert resp.status_code == TEST_HTTP_STATUS_BAD_REQUEST


def test_search_param_bounds() -> None:
    """Teste que la recherche valide les bornes des paramètres."""
    client = TestClient(_app())
    # invalid top_k
    r1 = client.post("/internal/retrieval/search", json={"query": "x", "top_k": 100})
    assert r1.status_code == TEST_HTTP_STATUS_BAD_REQUEST
    # invalid offset
    r2 = client.post("/internal/retrieval/search", json={"query": "x", "offset": -1})
    assert r2.status_code == TEST_HTTP_STATUS_BAD_REQUEST


def test_search_handles_backend_errors(monkeypatch) -> None:
    """Teste que la recherche gère les erreurs du backend correctement."""
    client = TestClient(_app())

    class _Proxy:
        def search(self, query: str, top_k: int = 5, tenant: str | None = None):
            raise RetrievalBackendHTTPError(429, "rate-limited")

    monkeypatch.setattr(rr, "_proxy", _Proxy())
    r = client.post("/internal/retrieval/search", json={"query": "q"})
    assert r.status_code == TEST_HTTP_STATUS_TOO_MANY_REQUESTS

    class _Proxy2:
        def search(self, query: str, top_k: int = 5, tenant: str | None = None):
            raise RetrievalNetworkError("down")

    monkeypatch.setattr(rr, "_proxy", _Proxy2())
    r2 = client.post("/internal/retrieval/search", json={"query": "q"})
    assert r2.status_code == TEST_HTTP_STATUS_BAD_GATEWAY
