from fastapi.testclient import TestClient
from backend.app.main import app


def _create_chart(client: TestClient) -> str:
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
    assert r.status_code == 200
    return r.json()["id"]


def test_signup_login_and_premium_gate():
    c = TestClient(app)
    # signup with plus entitlement
    r = c.post(
        "/auth/signup",
        json={"email": "u@test.io", "password": "p", "entitlements": ["plus"]},
    )
    assert r.status_code == 200
    # login
    r = c.post("/auth/login", json={"email": "u@test.io", "password": "p"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    # premium endpoint requires token and entitlement
    chart_id = _create_chart(c)
    rp = c.get(f"/horoscope/today/premium/{chart_id}", headers=headers)
    assert rp.status_code == 200
    assert rp.json().get("premium") is True


def test_premium_forbidden_without_plus():
    c = TestClient(app)
    # signup without plus entitlement
    r = c.post(
        "/auth/signup",
        json={"email": "noplus@test.io", "password": "p", "entitlements": []},
    )
    assert r.status_code == 200
    # login
    r = c.post("/auth/login", json={"email": "noplus@test.io", "password": "p"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    # create chart and try premium
    chart_id = _create_chart(c)
    rp = c.get(f"/horoscope/today/premium/{chart_id}", headers=headers)
    assert rp.status_code == 403
    assert "missing_entitlement" in rp.json().get("detail", "")
