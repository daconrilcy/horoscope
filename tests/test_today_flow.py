"""
Tests pour le flux de génération d'horoscopes.

Ce module teste le flux complet de génération d'horoscopes du thème natal aux transits du jour et au
PDF.
"""

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.core.constants import (
    TEST_HTTP_STATUS_OK,
    TEST_PRECISION_SCORE_MAX,
)
from backend.core.container import container
from backend.infra.astro.fake_deterministic import FakeDeterministicAstro


def test_natal_to_today_and_pdf():
    """Teste le flux complet natal -> today -> PDF."""
    container.astro = FakeDeterministicAstro()  # override déterministe pour le test
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
    assert r.status_code == TEST_HTTP_STATUS_OK
    chart_id = r.json()["id"]

    r2 = client.get(f"/horoscope/today/{chart_id}")
    assert r2.status_code == TEST_HTTP_STATUS_OK
    data = r2.json()
    assert "leaders" in data and len(data["leaders"]) > 0
    assert 1 <= data["precision_score"] <= TEST_PRECISION_SCORE_MAX

    r3 = client.get(f"/horoscope/pdf/natal/{chart_id}")
    assert r3.status_code == TEST_HTTP_STATUS_OK
    assert r3.headers["content-type"].startswith("application/pdf")
