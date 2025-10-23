"""Tests pour l'endpoint de santé de l'application."""

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.core.http_constants import HTTP_OK


def test_health():
    """Teste que l'endpoint de santé retourne un statut OK."""
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == HTTP_OK
    assert r.json()["status"] == "ok"
