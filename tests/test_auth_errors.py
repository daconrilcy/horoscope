from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


def test_duplicate_signup_409() -> None:
    c = TestClient(app)
    payload = {"email": "dup@test.io", "password": "p", "entitlements": []}
    r1 = c.post("/auth/signup", json=payload)
    assert r1.status_code == 200
    r2 = c.post("/auth/signup", json=payload)
    assert r2.status_code == 409


def test_invalid_login_401() -> None:
    c = TestClient(app)
    c.post("/auth/signup", json={"email": "bad@test.io", "password": "p", "entitlements": []})
    r = c.post("/auth/login", json={"email": "bad@test.io", "password": "wrong"})
    assert r.status_code == 401


def test_missing_and_invalid_token() -> None:
    c = TestClient(app)
    # missing token
    r = c.get("/horoscope/today/premium/doesnotexist")
    assert r.status_code == 401

    # invalid token
    r = c.get(
        "/horoscope/today/premium/doesnotexist",
        headers={"Authorization": "Bearer not.a.valid.token"},
    )
    assert r.status_code == 401

