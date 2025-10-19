from fastapi.testclient import TestClient

from backend.app.main import app


def test_metrics_exposed():
    c = TestClient(app)
    r = c.get("/metrics")
    assert r.status_code == 200
    assert b"http_requests_total" in r.content
