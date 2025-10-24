"""Tests pour les erreurs d'authentification.

Ce module teste les cas d'erreur dans l'authentification, incluant les inscriptions en double et les
tokens invalides.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.core.constants import (
    TEST_HTTP_STATUS_CONFLICT,
    TEST_HTTP_STATUS_OK,
    TEST_HTTP_STATUS_UNAUTHORIZED,
)


@patch("backend.api.routes_auth.container")
@patch("backend.api.routes_auth.verify_password")
def test_duplicate_signup_409(mock_verify_password, mock_container) -> None:
    """Teste que l'inscription en double retourne une erreur 409."""
    # Mock password verification
    mock_verify_password.return_value = True

    # Mock container components
    mock_user_repo = mock_container.user_repo

    # Mock user data
    user_data = {
        "id": "test_user_id",
        "email": "dup@test.io",
        "password_hash": "$2b$12$test_hash",
        "entitlements": [],
    }

    # Track signup calls to simulate user creation
    user_created = False

    # Configure mock behavior
    def mock_get_by_email(email):
        if email == "dup@test.io" and user_created:
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
    payload = {"email": "dup@test.io", "password": "p", "entitlements": []}
    r1 = c.post("/auth/signup", json=payload)
    assert r1.status_code == TEST_HTTP_STATUS_OK
    r2 = c.post("/auth/signup", json=payload)
    assert r2.status_code == TEST_HTTP_STATUS_CONFLICT


@patch("backend.api.routes_auth.container")
@patch("backend.api.routes_auth.verify_password")
def test_invalid_login_401(mock_verify_password, mock_container) -> None:
    """Teste que la connexion avec un mauvais mot de passe retourne 401."""

    # Mock password verification - return True for signup, False for login
    def mock_verify_password_func(password, hashed):
        # Return True for signup (password "p"), False for login (password "wrong")
        return password == "p"

    mock_verify_password.side_effect = mock_verify_password_func

    # Mock container components
    mock_user_repo = mock_container.user_repo

    # Mock user data
    user_data = {
        "id": "test_user_id",
        "email": "bad@test.io",
        "password_hash": "$2b$12$test_hash",
        "entitlements": [],
    }

    # Track signup calls to simulate user creation
    user_created = False

    # Configure mock behavior
    def mock_get_by_email(email):
        if email == "bad@test.io" and user_created:
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
    c.post(
        "/auth/signup",
        json={"email": "bad@test.io", "password": "p", "entitlements": []},
    )
    r = c.post("/auth/login", json={"email": "bad@test.io", "password": "wrong"})
    assert r.status_code == TEST_HTTP_STATUS_UNAUTHORIZED


def test_missing_and_invalid_token() -> None:
    """Teste que les requêtes sans token ou avec token invalide sont rejetées."""
    c = TestClient(app)
    # missing token
    r = c.get("/horoscope/today/premium/doesnotexist")
    assert r.status_code == TEST_HTTP_STATUS_UNAUTHORIZED

    # invalid token
    r = c.get(
        "/horoscope/today/premium/doesnotexist",
        headers={"Authorization": "Bearer not.a.valid.token"},
    )
    assert r.status_code == TEST_HTTP_STATUS_UNAUTHORIZED
