# ============================================================
# Tests : tests/test_retrieval_proxy.py
# Objet  : Vérifier endpoints /internal/retrieval/* (squelette).
# ============================================================

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes_retrieval import router

app = FastAPI()
app.include_router(router)


def test_embed_ok():
    client = TestClient(app)
    resp = client.post("/internal/retrieval/embed", json={"texts": ["a", "b"]})
    assert resp.status_code == 200
    assert "vectors" in resp.json()


def test_search_400():
    client = TestClient(app)
    resp = client.post("/internal/retrieval/search", json={"query": ""})
    assert resp.status_code == 400
