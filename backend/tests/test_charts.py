"""Tests d'intégration basiques pour les endpoints charts."""

from app.main import app
from fastapi.testclient import TestClient


def test_compute_and_get_chart():
    client = TestClient(app)
    payload = {
        "name": "Ange",
        "date": "2018-06-12",
        "time": "10:30",
        "tz": "Europe/Paris",
        "lat": 48.8566,
        "lon": 2.3522,
    }
    r = client.post("/charts/compute", json=payload)
    assert r.status_code == 200
    chart = r.json()
    r2 = client.get(f"/charts/{chart['id']}")
    assert r2.status_code == 200
    assert r2.json()["id"] == chart["id"]
