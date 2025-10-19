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


def test_pdf_cached():
    c = TestClient(app)
    chart_id = _create_chart(c)
    r1 = c.get(f"/horoscope/pdf/natal/{chart_id}")
    assert r1.status_code == 200 and r1.headers["content-type"].startswith("application/pdf")
    # second call should hit cache (still 200)
    r2 = c.get(f"/horoscope/pdf/natal/{chart_id}")
    assert r2.status_code == 200
