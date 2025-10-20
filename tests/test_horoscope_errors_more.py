from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


def _token(client: TestClient) -> str:
    client.post(
        "/auth/signup",
        json={"email": "x@example.com", "password": "p", "entitlements": ["plus"]},
    )
    r = client.post("/auth/login", json={"email": "x@example.com", "password": "p"})
    return r.json()["access_token"]


def test_premium_404_for_unknown_chart() -> None:
    c = TestClient(app)
    tok = _token(c)
    headers = {"Authorization": f"Bearer {tok}"}
    r = c.get("/horoscope/today/premium/unknown-id", headers=headers)
    assert r.status_code == 404

