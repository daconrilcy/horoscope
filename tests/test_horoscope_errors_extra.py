"""Tests supplémentaires pour les erreurs d'horoscope.

Ce module teste des cas d'erreur supplémentaires dans les endpoints d'horoscope, incluant les thèmes
inconnus.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.core.constants import (
    TEST_HTTP_STATUS_NOT_FOUND,
)


def test_today_404_for_unknown_chart() -> None:
    """Teste que l'endpoint today retourne 404 pour un thème inconnu."""
    c = TestClient(app)
    r = c.get("/horoscope/today/unknown-id")
    assert r.status_code == TEST_HTTP_STATUS_NOT_FOUND


def test_pdf_404_for_unknown_chart() -> None:
    """Teste que l'endpoint PDF retourne 404 pour un thème inconnu."""
    c = TestClient(app)
    r = c.get("/horoscope/pdf/natal/unknown-id")
    assert r.status_code == TEST_HTTP_STATUS_NOT_FOUND
