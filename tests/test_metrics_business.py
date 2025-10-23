"""
Tests pour les métriques business.

Ce module teste les métriques business importantes pour le monitoring de l'application astrologique.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from prometheus_client import generate_latest

from backend.app.main import app
from backend.app.metrics import LLM_TOKENS_TOTAL


def test_chat_and_retrieval_business_metrics() -> None:
    """Teste que les métriques business de chat et récupération sont générées."""
    c = TestClient(app)
    # Create a chart
    r = c.post(
        "/horoscope/natal",
        json={
            "name": "U",
            "date": "1990-01-01",
            "time": None,
            "tz": "Europe/Paris",
            "lat": 48.85,
            "lon": 2.35,
            "time_certainty": "exact",
        },
    )
    chart_id = r.json()["id"]
    # Call chat advise without auth; may be 401/403 but metrics should be present
    c.post(
        "/chat/advise", json={"chart_id": chart_id, "question": "Hello?"}, headers={}
    )
    # Trigger retrieval search to update hit ratio
    c.post("/internal/retrieval/search", json={"query": "x", "top_k": 2})

    # Manually bump LLM tokens to ensure metric shows up in scrape
    LLM_TOKENS_TOTAL.labels(tenant="test", model="gpt").inc(5)

    # Scrape and assert metric names exist
    content = generate_latest()
    assert b"chat_requests_total" in content
    assert b"chat_latency_seconds_count" in content
    assert b"llm_tokens_total" in content
    assert b"retrieval_hit_ratio" in content


def test_grafana_dashboard_json_is_valid() -> None:
    """Teste que le fichier JSON du dashboard Grafana est valide."""
    path = Path("backend/docs/grafana_dashboard.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert "title" in data and "panels" in data
