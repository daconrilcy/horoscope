"""Tests pour les métriques Prometheus.

Ce module teste que les métriques Prometheus sont correctement exposées via l'endpoint /metrics.
"""

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.core.constants import (
    TEST_HTTP_STATUS_OK,
)


def test_metrics_exposed():
    """Teste que l'endpoint /metrics expose les métriques Prometheus."""
    c = TestClient(app)
    r = c.get("/metrics")
    assert r.status_code == TEST_HTTP_STATUS_OK
    assert b"http_requests_total" in r.content
    # Les métriques par endpoint de l'API Gateway doivent être présentes
    # même si le histogram Prom utilise *_bucket interne, le nom logique
    # est exposé via le client comme indiqué dans l'app.
    assert b"http_server_requests_total" in r.content
