from fastapi.testclient import TestClient

from backend.app.main import app


def test_natal_to_today_and_pdf():
    client = TestClient(app)
    birth = {
        "name": "Test User",
        "date": "1990-01-01",
        "time": None,
        "tz": "Europe/Paris",
        "lat": 48.8566,
        "lon": 2.3522,
        "time_certainty": "morning",
    }
    r = client.post("/horoscope/natal", json=birth)
    assert r.status_code == 200
    chart_id = r.json()["id"]

    r2 = client.get(f"/horoscope/today/{chart_id}")
    assert r2.status_code == 200
    data = r2.json()
    assert "leaders" in data and len(data["leaders"]) > 0
    assert 1 <= data["precision_score"] <= 5

    r3 = client.get(f"/horoscope/pdf/natal/{chart_id}")
    assert r3.status_code == 200
    assert r3.headers["content-type"].startswith("application/pdf")
