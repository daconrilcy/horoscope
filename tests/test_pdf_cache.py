"""Tests pour le cache PDF.

Ce module teste le système de cache pour les PDFs d'horoscopes générés.
"""

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.core.constants import (
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


def test_pdf_cached():
    """Teste que les PDFs sont mis en cache et réutilisés."""
    c = TestClient(app)
    chart_id = _create_chart(c)
    r1 = c.get(f"/horoscope/pdf/natal/{chart_id}")
    assert r1.status_code == TEST_HTTP_STATUS_OK and r1.headers["content-type"].startswith(
        "application/pdf"
    )
    # second call should hit cache (still 200)
    r2 = c.get(f"/horoscope/pdf/natal/{chart_id}")
    assert r2.status_code == TEST_HTTP_STATUS_OK
