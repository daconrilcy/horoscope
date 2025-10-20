from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


def test_today_404_for_unknown_chart() -> None:
    c = TestClient(app)
    r = c.get("/horoscope/today/unknown-id")
    assert r.status_code == 404


def test_pdf_404_for_unknown_chart() -> None:
    c = TestClient(app)
    r = c.get("/horoscope/pdf/natal/unknown-id")
    assert r.status_code == 404

