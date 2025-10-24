"""Tests supplémentaires pour les erreurs d'horoscope.

Ce module teste des cas d'erreur supplémentaires dans les endpoints d'horoscope, incluant les thèmes
inconnus.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.core.constants import (
    TEST_HTTP_STATUS_NOT_FOUND,
)


@patch("backend.api.routes_horoscope.service")
def test_today_404_for_unknown_chart(mock_service) -> None:
    """Teste que l'endpoint today retourne 404 pour un thème inconnu."""
    # Mock service to raise KeyError for unknown chart
    mock_service.get_today.side_effect = KeyError("Chart not found")

    c = TestClient(app)
    r = c.get("/horoscope/today/unknown-id")
    assert r.status_code == TEST_HTTP_STATUS_NOT_FOUND


@patch("backend.api.routes_horoscope.container")
@patch("backend.api.routes_horoscope.service")
def test_pdf_404_for_unknown_chart(mock_service, mock_container) -> None:
    """Teste que l'endpoint PDF retourne 404 pour un thème inconnu."""
    # Mock container chart_repo to return None for unknown chart
    mock_container.chart_repo.get.return_value = None

    c = TestClient(app)
    r = c.get("/horoscope/pdf/natal/unknown-id")
    assert r.status_code == TEST_HTTP_STATUS_NOT_FOUND
