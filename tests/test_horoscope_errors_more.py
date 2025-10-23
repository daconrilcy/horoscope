"""
Tests supplémentaires pour les erreurs d'horoscope premium.

Ce module teste des cas d'erreur supplémentaires dans les endpoints d'horoscope premium, incluant
les thèmes inconnus avec authentification.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.core.constants import (
    TEST_HTTP_STATUS_NOT_FOUND,
)


def _token(client: TestClient) -> str:
    """Crée un utilisateur de test avec entitlement plus et retourne son token."""
    client.post(
        "/auth/signup",
        json={"email": "x@example.com", "password": "p", "entitlements": ["plus"]},
    )
    r = client.post("/auth/login", json={"email": "x@example.com", "password": "p"})
    return r.json()["access_token"]


def test_premium_404_for_unknown_chart() -> None:
    """Teste que l'endpoint premium retourne 404 pour un thème inconnu."""
    c = TestClient(app)
    tok = _token(c)
    headers = {"Authorization": f"Bearer {tok}"}
    r = c.get("/horoscope/today/premium/unknown-id", headers=headers)
    assert r.status_code == TEST_HTTP_STATUS_NOT_FOUND
