# ============================================================
# Tests : tests/test_retrieval_weaviate.py
# Objet  : Vérifier l'adaptateur Weaviate via l'API FastAPI.
# ============================================================

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes_retrieval import router


class _DummyResp:
    def __init__(self, json_data: dict[str, Any], status_code: int = 200) -> None:
        self._data = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:  # pragma: no cover - simple stub
        if self.status_code >= 400:
            from httpx import HTTPStatusError

            raise HTTPStatusError("err", request=None, response=None)

    def json(self) -> dict[str, Any]:
        return self._data


def test_weaviate_search_ok(monkeypatch: Any) -> None:
    # Configurer l'adaptateur Weaviate AVANT d'importer le router
    monkeypatch.setenv("RETRIEVAL_BACKEND", "weaviate")
    monkeypatch.setenv("WEAVIATE_URL", "https://example.weaviate.local")

    # Recharger le router pour forcer la (ré)construction du proxy avec les env
    import importlib
    import backend.api.routes_retrieval as routes

    importlib.reload(routes)
    app = FastAPI()
    app.include_router(routes.router)
    client = TestClient(app)

    # Stub httpx.Client.post pour retourner une réponse GraphQL valide
    import httpx

    _orig_post = httpx.Client.post

    def _fake_post(self, url: str, json: dict[str, Any], **kwargs: Any) -> _DummyResp:  # type: ignore[no-redef]
        if str(url).endswith("/v1/graphql"):
            return _DummyResp(
                {
                    "data": {
                        "Get": {
                            "Document": [
                                {"_additional": {"id": "w1", "certainty": 0.88}, "tenant": "t1"}
                            ]
                        }
                    }
                }
            )
        return _orig_post(self, url, json=json, **kwargs)

    monkeypatch.setattr("httpx.Client.post", _fake_post)

    resp = client.post(
        "/internal/retrieval/search",
        json={"query": "hello", "top_k": 5, "tenant": "t1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "results" in body and body["results"][0]["id"] == "w1"


def test_weaviate_search_502_on_network(monkeypatch: Any) -> None:
    monkeypatch.setenv("RETRIEVAL_BACKEND", "weaviate")
    monkeypatch.setenv("WEAVIATE_URL", "https://example.weaviate.local")

    import importlib
    import backend.api.routes_retrieval as routes

    importlib.reload(routes)
    app = FastAPI()
    app.include_router(routes.router)
    client = TestClient(app)

    # Forcer httpx à lever une erreur réseau
    import httpx

    _orig_post = httpx.Client.post

    def _boom(self, url: str, json: dict[str, Any], **kwargs: Any):  # type: ignore[no-redef]
        if str(url).endswith("/v1/graphql"):
            raise httpx.HTTPError("network")
        return _orig_post(self, url, json=json, **kwargs)

    monkeypatch.setattr("httpx.Client.post", _boom)

    resp = client.post(
        "/internal/retrieval/search",
        json={"query": "hello", "top_k": 5},
    )
    assert resp.status_code == 502
