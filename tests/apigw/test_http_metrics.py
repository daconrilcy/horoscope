"""Tests pour les métriques HTTP server spécifiques.

Ce module teste le middleware HTTPServerMetricsMiddleware et les métriques
http_server_requests_seconds_bucket et http_server_requests_total.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.apigw.http_metrics import HTTPServerMetricsMiddleware

# Constantes pour éviter les erreurs PLR2004 (Magic values)
HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_SERVER_ERROR = 500
TEST_TRACE_ID = "test-trace-123"
EXPECTED_DURATION_MIN = 0.001
EXPECTED_DURATION_MAX = 0.1
HTTP_METHODS_COUNT = 4
CONCURRENT_REQUESTS_COUNT = 5


class TestHTTPServerMetricsMiddleware:
    """Tests pour HTTPServerMetricsMiddleware."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.app = FastAPI()
        self.middleware = HTTPServerMetricsMiddleware(self.app)

    def test_middleware_initialization(self) -> None:
        """Test middleware initialization."""
        app = FastAPI()
        middleware = HTTPServerMetricsMiddleware(app)
        assert middleware.app == app

    def test_successful_request_metrics(self) -> None:
        """Test métriques pour requête réussie."""
        app = FastAPI()
        app.add_middleware(HTTPServerMetricsMiddleware)

        @app.get("/v1/test")
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)

        with (
            patch("backend.apigw.http_metrics.HTTP_SERVER_REQUESTS_SECONDS") as mock_histogram,
            patch("backend.apigw.http_metrics.HTTP_SERVER_REQUESTS_TOTAL") as _,
        ):
            response = client.get("/v1/test")

            assert response.status_code == HTTP_OK

            # Check histogram metric
            mock_histogram.labels.assert_called_once_with(
                route="/v1/test",
                method="GET",
                status=str(HTTP_OK),
            )
            mock_histogram.labels.return_value.observe.assert_called_once()

            # Check counter metric
            _.labels.assert_called_once_with(
                route="/v1/test",
                method="GET",
                status=str(HTTP_OK),
            )
            _.labels().inc.assert_called_once()

    def test_error_request_metrics(self) -> None:
        """Test métriques pour requête avec erreur (no double count)."""
        app = FastAPI()
        app.add_middleware(HTTPServerMetricsMiddleware)

        @app.get("/v1/error")
        async def error_endpoint():
            raise ValueError("Test error")

        client = TestClient(app)

        with (
            patch("backend.apigw.http_metrics.HTTP_SERVER_REQUESTS_SECONDS") as mock_histogram,
            patch("backend.apigw.http_metrics.HTTP_SERVER_REQUESTS_TOTAL") as mock_total,
        ):
            # Snapshot calls before (not used; keep for clarity of intent)

            with pytest.raises(Exception, match="Request failed"):
                client.get("/v1/error")

            # Check histogram metric
            mock_histogram.labels.assert_called_once_with(
                route="/v1/error",
                method="GET",
                status="500",
            )
            mock_histogram.labels.return_value.observe.assert_called_once()

            # Check counter metric
            mock_total.labels.assert_called_once_with(
                route="/v1/error",
                method="GET",
                status="500",
            )
            mock_total.labels.return_value.inc.assert_called_once()

            # Ensure exactly one observation/increment recorded for the failing request
            # labels() may be invoked internally more than once; enforce single observe/inc instead.
            assert mock_histogram.labels.return_value.observe.call_count == 1
            assert mock_total.labels.return_value.inc.call_count == 1

    def test_different_http_methods(self) -> None:
        """Test métriques pour différentes méthodes HTTP."""
        app = FastAPI()
        app.add_middleware(HTTPServerMetricsMiddleware)

        @app.get("/v1/test")
        async def get_endpoint():
            return {"method": "GET"}

        @app.post("/v1/test")
        async def post_endpoint():
            return {"method": "POST"}

        @app.put("/v1/test")
        async def put_endpoint():
            return {"method": "PUT"}

        @app.delete("/v1/test")
        async def delete_endpoint():
            return {"method": "DELETE"}

        client = TestClient(app)

        with (
            patch("backend.apigw.http_metrics.HTTP_SERVER_REQUESTS_SECONDS") as mock_histogram,
            patch("backend.apigw.http_metrics.HTTP_SERVER_REQUESTS_TOTAL") as _,
        ):
            # Test GET
            response = client.get("/v1/test")
            assert response.status_code == HTTP_OK

            # Test POST
            response = client.post("/v1/test")
            assert response.status_code == HTTP_OK

            # Test PUT
            response = client.put("/v1/test")
            assert response.status_code == HTTP_OK

            # Test DELETE
            response = client.delete("/v1/test")
            assert response.status_code == HTTP_OK

            # Check that metrics were called for each method
            assert mock_histogram.labels.call_count == HTTP_METHODS_COUNT
            assert _.labels.call_count == HTTP_METHODS_COUNT

    def test_route_normalization(self) -> None:
        """Test normalisation des routes pour les métriques."""
        app = FastAPI()
        app.add_middleware(HTTPServerMetricsMiddleware)

        @app.get("/v1/chat/{chat_id}")
        async def chat_endpoint(chat_id: str):
            return {"chat_id": chat_id}

        client = TestClient(app)

        with (
            patch("backend.apigw.http_metrics.HTTP_SERVER_REQUESTS_SECONDS") as mock_histogram,
            patch("backend.apigw.http_metrics.HTTP_SERVER_REQUESTS_TOTAL") as _,
        ):
            response = client.get("/v1/chat/123")
            assert response.status_code == HTTP_OK

            # Check that route was normalized
            mock_histogram.labels.assert_called_once_with(
                route="/v1/chat/{id}",
                method="GET",
                status=str(HTTP_OK),
            )

    def test_query_parameters_ignored(self) -> None:
        """Test que les paramètres de requête sont ignorés dans la normalisation."""
        app = FastAPI()
        app.add_middleware(HTTPServerMetricsMiddleware)

        @app.get("/v1/test")
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)

        with (
            patch("backend.apigw.http_metrics.HTTP_SERVER_REQUESTS_SECONDS") as mock_histogram,
            patch("backend.apigw.http_metrics.HTTP_SERVER_REQUESTS_TOTAL") as _,
        ):
            response = client.get("/v1/test?param1=value1&param2=value2")
            assert response.status_code == HTTP_OK

            # Check that query parameters were ignored
            mock_histogram.labels.assert_called_once_with(
                route="/v1/test",
                method="GET",
                status=str(HTTP_OK),
            )

    def test_duration_measurement(self) -> None:
        """Test mesure de la durée des requêtes."""
        app = FastAPI()
        app.add_middleware(HTTPServerMetricsMiddleware)

        @app.get("/v1/slow")
        async def slow_endpoint():
            await asyncio.sleep(0.01)  # 10ms delay
            return {"message": "slow"}

        client = TestClient(app)

        with patch("backend.apigw.http_metrics.HTTP_SERVER_REQUESTS_SECONDS") as mock_histogram:
            response = client.get("/v1/slow")
            assert response.status_code == HTTP_OK

            # Check that duration was measured
            mock_histogram.labels().observe.assert_called_once()
            observed_duration = mock_histogram.labels().observe.call_args[0][0]
            assert observed_duration >= EXPECTED_DURATION_MIN
            assert observed_duration <= EXPECTED_DURATION_MAX

    def test_middleware_dispatch_method(self) -> None:
        """Test méthode dispatch du middleware."""
        request = MagicMock()
        request.url.path = "/v1/test"
        request.method = "GET"

        call_next = AsyncMock()
        response = MagicMock()
        response.status_code = HTTP_OK
        call_next.return_value = response

        with (
            patch("backend.apigw.http_metrics.HTTP_SERVER_REQUESTS_SECONDS") as mock_histogram,
            patch("backend.apigw.http_metrics.HTTP_SERVER_REQUESTS_TOTAL") as _,
        ):
            result = asyncio.run(self.middleware.dispatch(request, call_next))

            # Should call next middleware
            call_next.assert_called_once_with(request)

            # Should record metrics
            mock_histogram.labels().observe.assert_called_once()
            _.labels().inc.assert_called_once()

            # Should return the response
            assert result == response

    def test_middleware_with_trace_id(self) -> None:
        """Test middleware avec trace ID."""
        app = FastAPI()
        app.add_middleware(HTTPServerMetricsMiddleware)

        @app.get("/v1/test")
        async def test_endpoint(request: Request):
            return {"trace_id": getattr(request.state, "trace_id", None)}

        client = TestClient(app)

        with (
            patch("backend.apigw.http_metrics.HTTP_SERVER_REQUESTS_SECONDS") as mock_histogram,
            patch("backend.apigw.http_metrics.HTTP_SERVER_REQUESTS_TOTAL") as _,
        ):
            response = client.get("/v1/test", headers={"X-Trace-ID": TEST_TRACE_ID})
            assert response.status_code == HTTP_OK

            # Metrics should still be recorded
            mock_histogram.labels().observe.assert_called_once()
            _.labels().inc.assert_called_once()

    def test_concurrent_requests(self) -> None:
        """Test métriques pour requêtes concurrentes."""
        app = FastAPI()
        app.add_middleware(HTTPServerMetricsMiddleware)

        @app.get("/v1/test")
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)

        with (
            patch("backend.apigw.http_metrics.HTTP_SERVER_REQUESTS_SECONDS") as mock_histogram,
            patch("backend.apigw.http_metrics.HTTP_SERVER_REQUESTS_TOTAL") as mock_counter,
        ):
            # Make multiple concurrent requests
            responses = []
            for _ in range(5):
                response = client.get("/v1/test")
                responses.append(response)

            # All should succeed
            for response in responses:
                assert response.status_code == HTTP_OK

            # Metrics should be recorded for each request
            assert mock_histogram.labels.call_count == CONCURRENT_REQUESTS_COUNT
            assert mock_counter.labels.call_count == CONCURRENT_REQUESTS_COUNT

    def test_error_handling_in_middleware(self) -> None:
        """Test gestion d'erreur dans le middleware."""
        request = MagicMock()
        request.url.path = "/v1/test"
        request.method = "GET"

        call_next = AsyncMock()
        call_next.side_effect = Exception("Test error")

        with (
            patch("backend.apigw.http_metrics.HTTP_SERVER_REQUESTS_SECONDS") as mock_histogram,
            patch("backend.apigw.http_metrics.HTTP_SERVER_REQUESTS_TOTAL") as _,
        ):
            with pytest.raises(Exception, match="Request failed"):
                asyncio.run(self.middleware.dispatch(request, call_next))

            # Metrics should still be recorded even if error occurs
            mock_histogram.labels().observe.assert_called_once()
            _.labels().inc.assert_called_once()

    def test_metrics_labels_consistency(self) -> None:
        """Test cohérence des labels entre histogram et counter."""
        app = FastAPI()
        app.add_middleware(HTTPServerMetricsMiddleware)

        @app.get("/v1/test")
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)

        with (
            patch("backend.apigw.http_metrics.HTTP_SERVER_REQUESTS_SECONDS") as mock_histogram,
            patch("backend.apigw.http_metrics.HTTP_SERVER_REQUESTS_TOTAL") as _,
        ):
            response = client.get("/v1/test")
            assert response.status_code == HTTP_OK

            # Check that both metrics use the same labels
            histogram_labels = mock_histogram.labels.call_args[1]
            counter_labels = _.labels.call_args[1]

            assert histogram_labels == counter_labels
            assert histogram_labels["route"] == "/v1/test"
            assert histogram_labels["method"] == "GET"
            assert histogram_labels["status"] == str(HTTP_OK)
