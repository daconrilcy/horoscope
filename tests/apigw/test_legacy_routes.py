"""Tests pour les routes legacy avec redirection et warning.

Ce module teste la gestion des routes dépréciées, les headers de dépréciation et les réponses
de fin de vie (sunset).
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.apigw.legacy_routes import (
    LegacyRouteMiddleware,
    get_deprecation_status,
    is_route_deprecated,
    is_route_sunset,
)

# Constantes pour éviter les erreurs PLR2004 (Magic values)
HTTP_OK = 200
HTTP_GONE = 410
TEST_TRACE_ID = "test-trace-123"
DEPRECATED_SINCE = "2025-01-01"
SUNSET_DATE = "2026-04-01"
MIGRATION_GUIDE = "https://api.example.com/docs/migration/v0-to-v1"


class TestLegacyRouteMiddleware:
    """Tests pour LegacyRouteMiddleware."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.app = FastAPI()
        self.middleware = LegacyRouteMiddleware(self.app)

    def test_non_legacy_route_passthrough(self) -> None:
        """Test que les routes non-legacy passent à travers."""
        app = FastAPI()
        app.add_middleware(LegacyRouteMiddleware)

        @app.get("/v1/test")
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)
        response = client.get("/v1/test")

        assert response.status_code == HTTP_OK
        assert response.json() == {"message": "success"}

    def test_legacy_route_deprecated_response(self) -> None:
        """Test réponse pour route dépréciée."""
        app = FastAPI()
        app.add_middleware(LegacyRouteMiddleware)

        @app.get("/v0/chat")
        async def legacy_endpoint():
            return {"message": "legacy"}

        client = TestClient(app)
        response = client.get("/v0/chat")

        assert response.status_code == HTTP_OK
        data = response.json()
        assert data["message"] == "legacy"

        # Check deprecation headers
        assert response.headers["Deprecation"] == "true"
        assert response.headers["Sunset"] == SUNSET_DATE

    def test_legacy_route_deprecation_headers(self) -> None:
        """Test headers de dépréciation."""
        app = FastAPI()
        app.add_middleware(LegacyRouteMiddleware)

        @app.get("/v0/chat")
        async def legacy_endpoint():
            return {"message": "legacy"}

        client = TestClient(app)
        response = client.get("/v0/chat")

        assert response.status_code == HTTP_OK
        assert response.headers["Deprecation"] == "true"
        assert response.headers["Sunset"] == SUNSET_DATE
        assert "deprecation" in response.headers["Link"]

    def test_legacy_route_with_trace_id(self) -> None:
        """Test route legacy avec trace ID."""
        app = FastAPI()
        app.add_middleware(LegacyRouteMiddleware)

        @app.get("/v0/chat")
        async def legacy_endpoint(request: Request):
            return {"message": "legacy"}

        client = TestClient(app)
        response = client.get("/v0/chat", headers={"X-Trace-ID": TEST_TRACE_ID})

        assert response.status_code == HTTP_OK
        data = response.json()
        assert data["message"] == "legacy"

        # Check deprecation headers
        assert response.headers["Deprecation"] == "true"

    def test_legacy_route_prefix_match(self) -> None:
        """Test correspondance par préfixe pour routes legacy."""
        app = FastAPI()
        app.add_middleware(LegacyRouteMiddleware)

        @app.get("/v0/chat/123")
        async def legacy_endpoint():
            return {"message": "legacy"}

        client = TestClient(app)
        response = client.get("/v0/chat/123")

        assert response.status_code == HTTP_OK
        data = response.json()
        assert data["message"] == "legacy"

        # Check deprecation headers
        assert response.headers["Deprecation"] == "true"

    def test_sunset_route_response(self) -> None:
        """Test réponse pour route sunset."""
        # Mock sunset date to be in the past
        with patch("backend.apigw.legacy_routes.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime.fromisoformat("2027-05-01")
            mock_datetime.fromisoformat = datetime.fromisoformat

            app = FastAPI()
            app.add_middleware(LegacyRouteMiddleware)

            @app.get("/v0/chat")
            async def legacy_endpoint():
                return {"message": "legacy"}

            client = TestClient(app)
            response = client.get("/v0/chat")

            assert response.status_code == HTTP_GONE
            data = response.json()
            assert data["code"] == "SUNSET_ENDPOINT"
            assert "removed" in data["message"].lower()

    def test_sunset_route_details(self) -> None:
        """Test détails de réponse pour route sunset."""
        with patch("backend.apigw.legacy_routes.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime.fromisoformat("2026-05-01")
            mock_datetime.fromisoformat = datetime.fromisoformat

            app = FastAPI()
            app.add_middleware(LegacyRouteMiddleware)

            @app.get("/v0/chat")
            async def legacy_endpoint():
                return {"message": "legacy"}

            client = TestClient(app)
            response = client.get("/v0/chat")

            assert response.status_code == HTTP_GONE
            data = response.json()
            assert "details" in data
            assert data["details"]["removed_since"] == SUNSET_DATE
            assert data["details"]["alternative_endpoint"] == "/v1/chat/answer"
            assert data["details"]["migration_guide"] == MIGRATION_GUIDE

    def test_middleware_dispatch_non_legacy(self) -> None:
        """Test dispatch middleware pour route non-legacy."""
        request = MagicMock()
        request.url.path = "/v1/test"
        call_next = AsyncMock()
        response = MagicMock()
        call_next.return_value = response

        result = asyncio.run(self.middleware.dispatch(request, call_next))

        call_next.assert_called_once_with(request)
        assert result == response

    def test_middleware_dispatch_legacy_deprecated(self) -> None:
        """Test dispatch middleware pour route legacy dépréciée."""
        request = MagicMock()
        request.url.path = "/v0/chat"
        request.state = MagicMock()
        request.state.trace_id = None

        call_next = AsyncMock()
        response = MagicMock()
        response.headers = {}
        call_next.return_value = response

        result = asyncio.run(self.middleware.dispatch(request, call_next))

        # Should call next for deprecated routes and add headers
        call_next.assert_called_once_with(request)
        assert result == response
        assert result.headers["Deprecation"] == "true"

    def test_middleware_dispatch_legacy_sunset(self) -> None:
        """Test dispatch middleware pour route legacy sunset."""
        with patch("backend.apigw.legacy_routes.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime.fromisoformat("2026-05-01")
            mock_datetime.fromisoformat = datetime.fromisoformat

            request = MagicMock()
            request.url.path = "/v0/chat"
            request.state = MagicMock()
            request.state.trace_id = None

            call_next = AsyncMock()

            result = asyncio.run(self.middleware.dispatch(request, call_next))

            # Should not call next for sunset routes
            call_next.assert_not_called()
            assert result.status_code == HTTP_GONE


class TestLegacyRouteFunctions:
    """Tests pour les fonctions utilitaires des routes legacy."""

    def test_get_deprecation_status_exact_match(self) -> None:
        """Test récupération statut dépréciation avec correspondance exacte."""
        status = get_deprecation_status("/v0/chat")
        assert status is not None
        assert status["target"] == "/v1/chat/answer"
        assert status["deprecated_since"] == DEPRECATED_SINCE
        assert status["sunset_date"] == SUNSET_DATE

    def test_get_deprecation_status_prefix_match(self) -> None:
        """Test récupération statut dépréciation avec correspondance par préfixe."""
        status = get_deprecation_status("/v0/chat/123")
        assert status is not None
        assert status["target"] == "/v1/chat/answer"

    def test_get_deprecation_status_no_match(self) -> None:
        """Test récupération statut dépréciation sans correspondance."""
        status = get_deprecation_status("/v1/test")
        assert status is None

    def test_is_route_deprecated_true(self) -> None:
        """Test vérification route dépréciée - vraie."""
        assert is_route_deprecated("/v0/chat") is True
        assert is_route_deprecated("/v0/retrieval") is True
        assert is_route_deprecated("/v0/horoscope") is True

    def test_is_route_deprecated_false(self) -> None:
        """Test vérification route dépréciée - fausse."""
        assert is_route_deprecated("/v1/chat") is False
        assert is_route_deprecated("/v1/test") is False

    def test_is_route_sunset_false(self) -> None:
        """Test vérification route sunset - fausse (pas encore sunset)."""
        assert is_route_sunset("/v0/chat") is False

    def test_is_route_sunset_true(self) -> None:
        """Test vérification route sunset - vraie."""
        with patch("backend.apigw.legacy_routes.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime.fromisoformat("2026-05-01")
            mock_datetime.fromisoformat = datetime.fromisoformat

            assert is_route_sunset("/v0/chat") is True

    def test_is_route_sunset_non_deprecated(self) -> None:
        """Test vérification route sunset pour route non-dépréciée."""
        assert is_route_sunset("/v1/test") is False


class TestLegacyRouteIntegration:
    """Tests d'intégration pour les routes legacy."""

    def test_full_legacy_workflow(self) -> None:
        """Test workflow complet pour route legacy."""
        app = FastAPI()
        app.add_middleware(LegacyRouteMiddleware)

        @app.get("/v0/chat")
        async def legacy_endpoint():
            return {"message": "legacy"}

        client = TestClient(app)

        # Test deprecated route
        response = client.get("/v0/chat")
        assert response.status_code == HTTP_OK
        assert response.headers["Deprecation"] == "true"
        assert response.headers["Sunset"] == SUNSET_DATE

        data = response.json()
        assert data["message"] == "legacy"

        # Check deprecation headers
        assert response.headers["Deprecation"] == "true"
        assert response.headers["Sunset"] == SUNSET_DATE

    def test_legacy_route_with_query_params(self) -> None:
        """Test route legacy avec paramètres de requête."""
        app = FastAPI()
        app.add_middleware(LegacyRouteMiddleware)

        @app.get("/v0/chat")
        async def legacy_endpoint():
            return {"message": "legacy"}

        client = TestClient(app)
        response = client.get("/v0/chat?param=value")

        assert response.status_code == HTTP_OK
        data = response.json()
        assert data["message"] == "legacy"

        # Check deprecation headers
        assert response.headers["Deprecation"] == "true"

    def test_legacy_route_logging(self) -> None:
        """Test logging pour routes legacy."""
        app = FastAPI()
        app.add_middleware(LegacyRouteMiddleware)

        @app.get("/v0/chat")
        async def legacy_endpoint():
            return {"message": "legacy"}

        with patch("backend.apigw.legacy_routes.log") as mock_log:
            client = TestClient(app)
            client.get("/v0/chat")

            # Should log deprecation warning
            mock_log.info.assert_called_once()
            log_call = mock_log.info.call_args[1]["extra"]
            assert log_call["path"] == "/v0/chat"
            assert log_call["target"] == "/v1/chat/answer"

    def test_sunset_route_logging(self) -> None:
        """Test logging pour routes sunset."""
        with patch("backend.apigw.legacy_routes.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime.fromisoformat("2026-05-01")
            mock_datetime.fromisoformat = datetime.fromisoformat

            app = FastAPI()
            app.add_middleware(LegacyRouteMiddleware)

            @app.get("/v0/chat")
            async def legacy_endpoint():
                return {"message": "legacy"}

            with patch("backend.apigw.legacy_routes.log") as mock_log:
                client = TestClient(app)
                client.get("/v0/chat")

                # Should log sunset warning
                mock_log.warning.assert_called_once()
                log_call = mock_log.warning.call_args[1]["extra"]
                assert log_call["path"] == "/v0/chat"
                assert log_call["sunset_date"] == SUNSET_DATE
