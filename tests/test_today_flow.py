"""Tests pour le flux de génération d'horoscopes.

Ce module teste le flux complet de génération d'horoscopes du thème natal aux transits du jour et au
PDF.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.core.constants import (
    TEST_HTTP_STATUS_OK,
    TEST_PRECISION_SCORE_MAX,
)
from backend.core.container import container
from backend.infra.astro.fake_deterministic import FakeDeterministicAstro


@patch("backend.api.routes_horoscope.service")
@patch("backend.api.routes_horoscope.container")
def test_natal_to_today_and_pdf(mock_container, mock_service):
    """Teste le flux complet natal -> today -> PDF."""
    # Mock container and service
    mock_container.chart_repo.get.return_value = {
        "id": "test_chart_id",
        "owner": "Test User",
        "chart": {"precision_score": 1},
    }
    mock_service.compute_natal.return_value = {
        "id": "test_chart_id",
        "owner": "Test User",
        "chart": {"planets": [], "houses": [], "aspects": []},
    }
    mock_service.get_today.return_value = {
        "date": "2024-01-01",
        "leaders": [{"name": "Sun", "sign": "Leo"}, {"name": "Moon", "sign": "Cancer"}],
        "influences": [
            {"type": "positive", "strength": "strong"},
            {"type": "creative", "strength": "medium"},
        ],
        "eao": {"element": "fire", "aspect": "trine", "orb": "tight"},
        "snippets": [{"text": "Today is a great day for creativity", "source": "astrology"}],
        "precision_score": 1,
    }

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
