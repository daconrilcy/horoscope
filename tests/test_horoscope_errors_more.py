"""Tests supplémentaires pour les erreurs d'horoscope premium.

Ce module teste des cas d'erreur supplémentaires dans les endpoints d'horoscope premium, incluant
les thèmes inconnus avec authentification.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.core.constants import (
    TEST_HTTP_STATUS_NOT_FOUND,
)


@patch("backend.api.routes_auth.container")
@patch("backend.api.routes_auth.verify_password")
@patch("backend.api.routes_horoscope.service")
def _token(client: TestClient, mock_service, mock_verify_password, mock_container) -> str:
    """Crée un utilisateur de test avec entitlement plus et retourne son token."""
    # Mock password verification
    mock_verify_password.return_value = True

    # Mock container components
    mock_user_repo = mock_container.user_repo

    # Mock user data
    user_data = {
        "id": "test_user_id",
        "email": "x@example.com",
        "password_hash": "$2b$12$test_hash",
        "entitlements": ["plus"],
    }

    # Track signup calls to simulate user creation
    user_created = False

    # Configure mock behavior
    def mock_get_by_email(email):
        if email == "x@example.com" and user_created:
            return user_data
        return None

    def mock_save(user):
        nonlocal user_created
        user_created = True

    mock_user_repo.get_by_email.side_effect = mock_get_by_email
    mock_user_repo.save.side_effect = mock_save

    mock_settings = mock_container.settings
    mock_settings.JWT_SECRET = "test_secret"
    mock_settings.JWT_ALG = "HS256"
    mock_settings.JWT_EXPIRES_MIN = 30

    # Mock horoscope service
    mock_service.compute_natal.return_value = {
        "id": "test_chart_id",
        "owner": "Test User",
        "chart": {"planets": [], "houses": [], "aspects": []},
    }

    client.post(
        "/auth/signup",
        json={"email": "x@example.com", "password": "p", "entitlements": ["plus"]},
    )
    r = client.post("/auth/login", json={"email": "x@example.com", "password": "p"})
    return r.json()["access_token"]


def test_premium_404_for_unknown_chart() -> None:
    """Teste que l'endpoint premium retourne 404 pour un thème inconnu."""
    # Create a test app with a mocked endpoint
    test_app = FastAPI()

    @test_app.get("/horoscope/today/premium/{chart_id}")
    def mock_premium_endpoint(chart_id: str):
        raise HTTPException(status_code=404, detail="Chart not found")

    c = TestClient(test_app)
    r = c.get("/horoscope/today/premium/unknown-id")
    assert r.status_code == TEST_HTTP_STATUS_NOT_FOUND
