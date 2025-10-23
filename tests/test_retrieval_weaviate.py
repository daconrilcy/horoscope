"""Tests pour l'adaptateur Weaviate via l'API FastAPI.

Ce module teste l'intégration de l'adaptateur Weaviate avec l'API FastAPI, incluant la gestion des
erreurs réseau et du rate limiting.
"""

# ============================================================
# Tests : tests/test_retrieval_weaviate.py
# Objet  : Vérifier l'adaptateur Weaviate via l'API FastAPI.
# ============================================================

from __future__ import annotations

import importlib
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.api.routes_retrieval as routes
from backend.core.constants import (
    TEST_HTTP_STATUS_BAD_GATEWAY,
    TEST_HTTP_STATUS_BAD_REQUEST,
    TEST_HTTP_STATUS_OK,
    TEST_HTTP_STATUS_TOO_MANY_REQUESTS,
)


class _DummyResp:
    def __init__(self, json_data: dict[str, Any], status_code: int = 200) -> None:
        self._data = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:  # pragma: no cover - simple stub
        if self.status_code >= TEST_HTTP_STATUS_BAD_REQUEST:
            raise httpx.HTTPStatusError("err", request=None, response=None)

    def json(self) -> dict[str, Any]:
        return self._data


def test_weaviate_search_ok(monkeypatch: Any) -> None:
    """Teste une recherche Weaviate réussie.

    Vérifie que l'adaptateur Weaviate fonctionne correctement avec une réponse GraphQL valide et
    retourne les bons résultats.
    """
    # Configurer l'adaptateur Weaviate AVANT d'importer le router
    monkeypatch.setenv("RETRIEVAL_BACKEND", "weaviate")
    monkeypatch.setenv("WEAVIATE_URL", "https://example.weaviate.local")

    # Recharger le router pour forcer la (ré)construction du proxy avec les env

    importlib.reload(routes)
    app = FastAPI()
    app.include_router(routes.router)
    client = TestClient(app)

    # Stub httpx.Client.post pour retourner une réponse GraphQL valide

    _orig_post = httpx.Client.post

    def _fake_post(self, url: str, json: dict[str, Any], **kwargs: Any) -> _DummyResp:  # type: ignore[no-redef]
        if str(url).endswith("/v1/graphql"):
            return _DummyResp(
                {
                    "data": {
                        "Get": {
                            "Document": [
                                {
                                    "_additional": {"id": "w1", "certainty": 0.88},
                                    "tenant": "t1",
                                }
                            ]
                        }
                    }
                }
            )
        return _orig_post(self, url, json=json, **kwargs)

    monkeypatch.setattr("httpx.Client.post", _fake_post)

    resp = client.post(
        "/internal/retrieval/search",
        json={"query": "  hello  ", "top_k": 5, "tenant": "t1", "offset": 0},
    )
    assert resp.status_code == TEST_HTTP_STATUS_OK
    body = resp.json()
    assert "results" in body and body["results"][0]["id"] == "w1"


def test_weaviate_search_502_on_network(monkeypatch: Any) -> None:
    """Teste la gestion des erreurs réseau avec Weaviate.

    Vérifie qu'une erreur réseau lors de l'appel à Weaviate retourne correctement un code d'erreur
    502.
    """
    monkeypatch.setenv("RETRIEVAL_BACKEND", "weaviate")
    monkeypatch.setenv("WEAVIATE_URL", "https://example.weaviate.local")

    importlib.reload(routes)
    app = FastAPI()
    app.include_router(routes.router)
    client = TestClient(app)

    # Forcer httpx à lever une erreur réseau

    _orig_post = httpx.Client.post

    def _boom(self, url: str, json: dict[str, Any], **kwargs: Any):  # type: ignore[no-redef]
        if str(url).endswith("/v1/graphql"):
            raise httpx.HTTPError("network")
        return _orig_post(self, url, json=json, **kwargs)

    monkeypatch.setattr("httpx.Client.post", _boom)

    resp = client.post(
        "/internal/retrieval/search",
        json={"query": "hello", "top_k": 5, "offset": 0},
    )
    assert resp.status_code == TEST_HTTP_STATUS_BAD_GATEWAY


def test_weaviate_429_rate_limit(monkeypatch: Any) -> None:
    """Teste la gestion du rate limiting avec Weaviate.

    Vérifie qu'une réponse 429 de Weaviate est correctement propagée au client avec le bon code
    d'erreur.
    """
    monkeypatch.setenv("RETRIEVAL_BACKEND", "weaviate")
    monkeypatch.setenv("WEAVIATE_URL", "https://example.weaviate.local")

    importlib.reload(routes)
    app = FastAPI()
    app.include_router(routes.router)
    client = TestClient(app)

    class R429:
        def __init__(self) -> None:
            self.status_code = 429

        def raise_for_status(self) -> None:  # pragma: no cover - not called
            raise httpx.HTTPStatusError("rate", request=None, response=None)

        def json(self) -> dict[str, Any]:  # pragma: no cover - not used
            return {}

    _orig_post = httpx.Client.post

    def _ratelimit(self, url: str, json: dict[str, Any], **kwargs: Any):  # type: ignore[no-redef]
        if str(url).endswith("/v1/graphql"):
            return R429()
        return _orig_post(self, url, json=json, **kwargs)

    monkeypatch.setattr("httpx.Client.post", _ratelimit)

    resp = client.post(
        "/internal/retrieval/search",
        json={"query": "hello", "top_k": 5, "offset": 0},
    )
    assert resp.status_code == TEST_HTTP_STATUS_TOO_MANY_REQUESTS


def test_search_topk_bounds_and_offset_errors() -> None:
    """Teste la validation des paramètres top_k et offset.

    Vérifie que les valeurs invalides pour top_k (hors limites) et offset (négatif) retournent des
    erreurs 400.
    """
    # Basic validation: top_k out of bounds and negative offset
    app = FastAPI()

    importlib.reload(routes)
    app.include_router(routes.router)
    client = TestClient(app)
    resp = client.post("/internal/retrieval/search", json={"query": "x", "top_k": 0})
    assert resp.status_code == TEST_HTTP_STATUS_BAD_REQUEST
    resp2 = client.post("/internal/retrieval/search", json={"query": "x", "top_k": 51})
    assert resp2.status_code == TEST_HTTP_STATUS_BAD_REQUEST
    resp3 = client.post("/internal/retrieval/search", json={"query": "x", "top_k": 5, "offset": -1})
    assert resp3.status_code == TEST_HTTP_STATUS_BAD_REQUEST
