# ============================================================
# Tests : tests/test_retrieval_proxy.py
# Objet  : Vérifier endpoints /internal/retrieval/* (squelette).
# ============================================================
"""Tests pour le proxy de récupération.

Ce module teste les endpoints internes de récupération et d'embeddings via le proxy.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes_retrieval import router
from backend.core.constants import (
    TEST_HTTP_STATUS_BAD_REQUEST,
    TEST_HTTP_STATUS_OK,
)

app = FastAPI()
app.include_router(router)


def test_embed_ok():
    """Teste que l'endpoint d'embedding fonctionne correctement."""
    client = TestClient(app)
    resp = client.post("/internal/retrieval/embed", json={"texts": ["a", "b"]})
    assert resp.status_code == TEST_HTTP_STATUS_OK
    assert "vectors" in resp.json()


def test_search_400():
    """Teste que l'endpoint de recherche retourne 400 pour une requête vide."""
    client = TestClient(app)
    resp = client.post("/internal/retrieval/search", json={"query": ""})
    assert resp.status_code == TEST_HTTP_STATUS_BAD_REQUEST
