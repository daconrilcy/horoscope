"""
Tests pour les erreurs d'authentification.

Ce module teste les cas d'erreur dans l'authentification, incluant les inscriptions en double et les
tokens invalides.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.core.constants import (
    TEST_HTTP_STATUS_CONFLICT,
    TEST_HTTP_STATUS_OK,
    TEST_HTTP_STATUS_UNAUTHORIZED,
)


def test_duplicate_signup_409() -> None:
    """Teste que l'inscription en double retourne une erreur 409."""
    c = TestClient(app)
    payload = {"email": "dup@test.io", "password": "p", "entitlements": []}
    r1 = c.post("/auth/signup", json=payload)
    assert r1.status_code == TEST_HTTP_STATUS_OK
    r2 = c.post("/auth/signup", json=payload)
    assert r2.status_code == TEST_HTTP_STATUS_CONFLICT


def test_invalid_login_401() -> None:
    """Teste que la connexion avec un mauvais mot de passe retourne 401."""
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
