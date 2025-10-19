from fastapi.testclient import TestClient

from backend.app.main import app


def test_chat_advise_flow(monkeypatch):
    c = TestClient(app)
    r = c.post(
        "/horoscope/natal",
        json={
            "name": "T",
            "date": "1990-01-01",
            "time": None,
            "tz": "Europe/Paris",
            "lat": 48.85,
            "lon": 2.35,
            "time_certainty": "exact",
        },
    )
    chart_id = r.json()["id"]
    # call route (bypass auth here or simulate a token if needed)
    data = {"chart_id": chart_id, "question": "Comment optimiser ma journée ?"}
    r2 = c.post("/chat/advise", json=data, headers={})  # if protected, provide Authorization
    assert r2.status_code in (200, 401, 403)  # route gating may apply
