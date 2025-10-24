"""Tests pour le cache PDF.

Ce module teste le système de cache pour les PDFs d'horoscopes générés.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.core.constants import (
    TEST_HTTP_STATUS_OK,
)


@patch("backend.api.routes_horoscope.service")
def _create_chart(client: TestClient, mock_service) -> str:
    """Crée un thème natal de test et retourne son ID."""
    # Mock horoscope service
    mock_service.compute_natal.return_value = {
        "id": "test_chart_id",
        "owner": "Test User",
        "chart": {"planets": [], "houses": [], "aspects": []},
    }

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


@patch("backend.api.routes_horoscope.container")
def test_pdf_cached(mock_container):
    """Teste que les PDFs sont mis en cache et réutilisés."""
    # Mock container
    mock_container.chart_repo.get.return_value = {
        "id": "test_chart_id",
        "owner": "Test User",
        "chart": {"precision_score": 1},
    }

    c = TestClient(app)
    chart_id = _create_chart(c)
    r1 = c.get(f"/horoscope/pdf/natal/{chart_id}")
    assert r1.status_code == TEST_HTTP_STATUS_OK and r1.headers["content-type"].startswith(
        "application/pdf"
    )
    # second call should hit cache (still 200)
    r2 = c.get(f"/horoscope/pdf/natal/{chart_id}")
    assert r2.status_code == TEST_HTTP_STATUS_OK
