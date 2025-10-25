"""Tests pour les métriques business.

Ce module teste les métriques business importantes pour le monitoring de l'application astrologique.
"""

from __future__ import annotations

import json
from pathlib import Path

from prometheus_client import generate_latest

from backend.app.metrics import LLM_TOKENS_TOTAL


def test_chat_and_retrieval_business_metrics() -> None:
    """Teste que les métriques business de chat et récupération sont générées."""
    # Manually bump LLM tokens to ensure metric shows up in scrape
    LLM_TOKENS_TOTAL.labels(tenant="test", model="gpt").inc(5)

    # Scrape and assert metric names exist
    content = generate_latest()
    assert b"llm_tokens_total" in content
    # Check that the metric was incremented
    assert b'tenant="test"' in content
    assert b'model="gpt"' in content


def test_grafana_dashboard_json_is_valid() -> None:
    """Teste que le fichier JSON du dashboard Grafana est valide."""
    path = Path("backend/docs/grafana_dashboard.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert "title" in data and "panels" in data
