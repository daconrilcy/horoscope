"""Tests pour l'authentification et les permissions.

Ce module teste les fonctionnalités d'authentification, d'inscription, de connexion et de gestion
des permissions utilisateur.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.core.constants import (
    TEST_HTTP_STATUS_FORBIDDEN,
    TEST_HTTP_STATUS_OK,
)


def _create_chart(client: TestClient) -> str:
    """Crée un thème natal de test et retourne son ID."""
    birth = {
        "name": "Test",
        "date": "1990-01-01",
        "time": None,
        "tz": "Europe/Paris",
        "lat": 48.85,
        "lon": 2.35,
        "time_certainty": "exact",
    }
    r = client.post("/horoscope/natal", json=birth)
    assert r.status_code == TEST_HTTP_STATUS_OK
    return r.json()["id"]


@patch("backend.api.routes_horoscope.service")
@patch("backend.api.routes_auth.container")
@patch("backend.api.routes_auth.verify_password")
def test_signup_login_and_premium_gate(mock_verify_password, mock_container, mock_service):
    """Teste le flux complet.

    Teste le flux complet d'inscription, connexion et vérification des permissions.
    """
    # Mock password verification
    mock_verify_password.return_value = True

    # Mock horoscope service
    mock_service.compute_natal.return_value = {
        "id": "test_chart_id",
        "owner": "Test User",
        "chart": {"planets": [], "houses": [], "aspects": []},
    }
    mock_service.get_today.return_value = {
        "date": "2024-01-01",
        "leaders": [],
        "influences": [],
        "eao": {"energy": 0, "attention": 0, "opportunity": 0},
        "snippets": [],
        "precision_score": 100,
    }

    # Mock container components
    mock_user_repo = mock_container.user_repo

    # Mock user data
    user_data = {
        "id": "test_user_id",
        "email": "u@test.io",
        "password_hash": "$2b$12$test_hash",  # Mocked hash
        "entitlements": ["plus"],
    }

    # Track signup calls to simulate user creation
    user_created = False

    # Configure mock behavior
    def mock_get_by_email(email):
        if email == "u@test.io" and user_created:
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

    c = TestClient(app)
    # signup with plus entitlement
    r = c.post(
        "/auth/signup",
        json={"email": "u@test.io", "password": "p", "entitlements": ["plus"]},
    )
    assert r.status_code == TEST_HTTP_STATUS_OK
    # login
    r = c.post("/auth/login", json={"email": "u@test.io", "password": "p"})
    assert r.status_code == TEST_HTTP_STATUS_OK
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    # premium endpoint requires token and entitlement
    chart_id = _create_chart(c)
    rp = c.get(f"/horoscope/today/premium/{chart_id}", headers=headers)
    assert rp.status_code == TEST_HTTP_STATUS_OK
    assert rp.json().get("premium") is True


@patch("backend.api.routes_horoscope.service")
@patch("backend.api.routes_auth.container")
@patch("backend.api.routes_auth.verify_password")
def test_premium_forbidden_without_plus(mock_verify_password, mock_container, mock_service):
    """Teste que l'accès premium est refusé sans entitlement 'plus'."""
    # Mock password verification
    mock_verify_password.return_value = True

    # Mock horoscope service
    mock_service.compute_natal.return_value = {
        "id": "test_chart_id",
        "owner": "Test User",
        "chart": {"planets": [], "houses": [], "aspects": []},
    }
    mock_service.get_today.return_value = {
        "date": "2024-01-01",
        "leaders": [],
        "influences": [],
        "eao": {"energy": 0, "attention": 0, "opportunity": 0},
        "snippets": [],
        "precision_score": 100,
    }

    # Mock container components
    mock_user_repo = mock_container.user_repo

    # Mock user data without plus entitlement
    user_data = {
        "id": "test_user_id",
        "email": "noplus@test.io",
        "password_hash": "$2b$12$test_hash",  # Mocked hash
        "entitlements": [],
    }

    # Track signup calls to simulate user creation
    user_created = False

    # Configure mock behavior
    def mock_get_by_email(email):
        if email == "noplus@test.io" and user_created:
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

    c = TestClient(app)
    # signup without plus entitlement
    r = c.post(
        "/auth/signup",
        json={"email": "noplus@test.io", "password": "p", "entitlements": []},
    )
    assert r.status_code == TEST_HTTP_STATUS_OK
    # login
    r = c.post("/auth/login", json={"email": "noplus@test.io", "password": "p"})
    assert r.status_code == TEST_HTTP_STATUS_OK
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    # create chart and try premium
    chart_id = _create_chart(c)
    rp = c.get(f"/horoscope/today/premium/{chart_id}", headers=headers)
    assert rp.status_code == TEST_HTTP_STATUS_FORBIDDEN
    assert "missing_entitlement" in rp.json().get("detail", "")
