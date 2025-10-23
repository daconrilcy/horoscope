"""
Tests pour les erreurs d'horoscope.

Ce module teste les cas d'erreur dans les endpoints d'horoscope, incluant les thèmes manquants et
les erreurs 404/422.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app

c = TestClient(app)


def test_today_404_when_chart_missing():
    """Teste que l'endpoint today retourne 404/422 pour un thème inexistant."""
    r = c.get("/horoscope/today/does-not-exist")
    assert r.status_code in (404, 422)
    # Message exact dépend de l'implémentation


def test_pdf_404_when_chart_missing():
    """Teste que l'endpoint PDF retourne 404/422 pour un thème inexistant."""
    r = c.get("/horoscope/pdf/does-not-exist")
    assert r.status_code in (404, 422)
