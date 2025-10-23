"""
Tests pour l'authentification et les permissions.

Ce module teste les fonctionnalités d'authentification, d'inscription, de connexion et de gestion
des permissions utilisateur.
"""

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


def test_signup_login_and_premium_gate():
    """Teste le flux complet d'inscription, connexion et vérification des permissions."""
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


def test_premium_forbidden_without_plus():
    """Teste que l'accès premium est refusé sans entitlement 'plus'."""
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
