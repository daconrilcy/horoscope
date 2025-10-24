# ============================================================
# Module : tests/test_api_versioning.py
# Objet  : Tests unitaires pour le versioning API et politique de dépréciation.
# Notes  : Couvrir routes /v1, warnings legacy, headers de dépréciation.
# ============================================================
"""Tests pour le versioning API et la politique de dépréciation.

Ce module teste:
- Le fonctionnement des routes versionnées /v1
- Les warnings et redirections pour les routes legacy
- Les headers de dépréciation
- La conformité avec la politique de sunset
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.core.constants import HTTP_STATUS_MOVED_PERMANENTLY, HTTP_STATUS_PERMANENT_REDIRECT


@pytest.fixture
def client() -> TestClient:
    """Crée un client de test pour l'application FastAPI."""
    return TestClient(app)


class TestAPIVersioning:
    """Tests pour le versioning API /v1."""

    def test_health_endpoint_no_versioning(self, client: TestClient) -> None:
        """Vérifie que l'endpoint /health n'a pas besoin de versioning."""
        response = client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()

    def test_metrics_endpoint_no_versioning(self, client: TestClient) -> None:
        """Vérifie que l'endpoint /metrics n'a pas besoin de versioning."""
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_auth_endpoint_versioned(self) -> None:
        """Vérifie que l'endpoint /v1/auth est bien configuré."""
        # Ce test vérifie que la route versionnée existe dans le routing
        # On ne teste pas l'exécution car cela nécessite Redis
        # On vérifie juste que la route est bien définie avec le préfixe /v1
        from backend.api.routes_auth import router as auth_router

        assert auth_router.prefix == "/v1/auth"

        # Vérifier que les routes sont bien définies
        routes = [route.path for route in auth_router.routes]
        assert "/v1/auth/signup" in routes
        assert "/v1/auth/login" in routes

    def test_horoscope_endpoint_versioned(self) -> None:
        """Vérifie que l'endpoint /v1/horoscope est bien configuré."""
        # Ce test vérifie que la route versionnée existe dans le routing
        from backend.api.routes_horoscope import router as horoscope_router

        assert horoscope_router.prefix == "/v1/horoscope"

        # Vérifier que les routes sont bien définies
        routes = [route.path for route in horoscope_router.routes]
        assert "/v1/horoscope/natal" in routes
        assert "/v1/horoscope/today/{chart_id}" in routes

    def test_chat_endpoint_versioned(self) -> None:
        """Vérifie que l'endpoint /v1/chat est bien configuré."""
        # Ce test vérifie que la route versionnée existe dans le routing
        from backend.api.routes_chat import router as chat_router

        assert chat_router.prefix == "/v1/chat"

        # Vérifier que les routes sont bien définies
        routes = [route.path for route in chat_router.routes]
        assert "/v1/chat/advise" in routes
        # La route /answer n'existe pas, on vérifie juste que /advise existe


class TestLegacyDeprecation:
    """Tests pour la dépréciation des routes legacy."""

    def test_legacy_auth_redirect(self, client: TestClient) -> None:
        """Vérifie la redirection et warning pour /auth legacy."""
        response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "password"},
            follow_redirects=False,  # Ne pas suivre les redirections
        )

        # POST doit retourner 308 (Permanent Redirect) pour préserver la méthode
        assert response.status_code == HTTP_STATUS_PERMANENT_REDIRECT
        assert response.headers["Location"] == "/v1/auth/login"
        assert response.headers["Deprecation"] == "@1761264000"  # RFC 9745 format (2025-10-24)
        assert response.headers["Sunset"] == "Wed, 31 Dec 2025 23:59:59 GMT"  # RFC 8594 format
        assert "Warning" in response.headers
        assert "deprecation" in response.headers["Link"]

        data = response.json()
        assert data["code"] == "DEPRECATED_ROUTE"
        assert "deprecation" in data
        assert data["deprecation"]["sunset_date"] == "2025-12-31"
        assert data["deprecation"]["new_path"] == "/v1/auth/login"

    def test_legacy_horoscope_redirect(self, client: TestClient) -> None:
        """Vérifie la redirection et warning pour /horoscope legacy."""
        response = client.post(
            "/horoscope/natal",
            json={"birth_date": "1990-01-01", "birth_time": "12:00", "birth_place": "Paris"},
            follow_redirects=False,
        )

        assert response.status_code == HTTP_STATUS_PERMANENT_REDIRECT
        assert response.headers["Location"] == "/v1/horoscope/natal"
        assert response.headers["Deprecation"] == "@1761264000"
        assert response.headers["Sunset"] == "Wed, 31 Dec 2025 23:59:59 GMT"

    def test_legacy_chat_redirect(self, client: TestClient) -> None:
        """Vérifie la redirection et warning pour /chat legacy."""
        response = client.post("/chat/advise", json={"message": "test"}, follow_redirects=False)

        assert response.status_code == HTTP_STATUS_PERMANENT_REDIRECT
        assert response.headers["Location"] == "/v1/chat/advise"
        assert response.headers["Deprecation"] == "@1761264000"
        assert response.headers["Sunset"] == "Wed, 31 Dec 2025 23:59:59 GMT"

    def test_legacy_redirect_with_query_params(self, client: TestClient) -> None:
        """Vérifie que les paramètres de requête sont préservés dans la redirection."""
        response = client.post(
            "/auth/login?redirect=/dashboard&token=abc123",
            json={"email": "test@example.com", "password": "password"},
            follow_redirects=False,
        )

        assert response.status_code == HTTP_STATUS_PERMANENT_REDIRECT
        # Les paramètres de requête peuvent être encodés en URL
        location = response.headers["Location"]
        assert location.startswith("/v1/auth/login?")
        assert "redirect=" in location
        assert "token=abc123" in location

    def test_legacy_redirect_with_path_params(self, client: TestClient) -> None:
        """Vérifie que les paramètres de chemin sont préservés dans la redirection."""
        response = client.get("/horoscope/today/chart-123", follow_redirects=False)

        assert response.status_code == HTTP_STATUS_MOVED_PERMANENTLY
        assert response.headers["Location"] == "/v1/horoscope/today/chart-123"

    def test_legacy_redirect_all_methods(self, client: TestClient) -> None:
        """Vérifie que tous les méthodes HTTP sont redirigées avec les bons codes."""
        # GET doit retourner 301
        response_get = client.get("/auth/test", follow_redirects=False)
        assert response_get.status_code == HTTP_STATUS_MOVED_PERMANENTLY

        # HEAD est bypassé pour monitoring (pas de redirection)
        response_head = client.head("/auth/test", follow_redirects=False)
        assert response_head.status_code in [
            200,
            404,
            405,
        ]  # 200 OK, 404 Not Found, ou 405 Method Not Allowed
        assert "Deprecation" not in response_head.headers
        assert "Sunset" not in response_head.headers

        # POST, PUT, PATCH, DELETE doivent retourner 308
        methods_308 = ["POST", "PUT", "PATCH", "DELETE"]
        for method in methods_308:
            response = client.request(method, "/auth/test", follow_redirects=False)
            assert response.status_code == HTTP_STATUS_PERMANENT_REDIRECT
            assert response.headers["Deprecation"] == "@1761264000"
            assert response.headers["Sunset"] == "Wed, 31 Dec 2025 23:59:59 GMT"

    def test_legacy_options_bypass(self, client: TestClient) -> None:
        """Vérifie que OPTIONS est bypassé pour CORS."""
        response = client.options("/auth/login", follow_redirects=False)

        # OPTIONS ne doit pas être redirigé (bypass pour CORS)
        # Peut retourner 405 (Method Not Allowed) mais pas de headers de dépréciation
        assert response.status_code in [200, 405]  # 200 OK ou 405 Method Not Allowed
        assert "Deprecation" not in response.headers
        assert "Sunset" not in response.headers
        assert "Location" not in response.headers

    def test_legacy_head_bypass(self, client: TestClient) -> None:
        """Vérifie que HEAD est bypassé pour monitoring."""
        response = client.head("/auth/login", follow_redirects=False)

        # HEAD ne doit pas être redirigé (bypass pour monitoring)
        # Peut retourner 405 (Method Not Allowed) mais pas de headers de dépréciation
        assert response.status_code in [200, 405]  # 200 OK ou 405 Method Not Allowed
        assert "Deprecation" not in response.headers
        assert "Sunset" not in response.headers
        assert "Location" not in response.headers

    def test_openapi_not_deprecated(self, client: TestClient) -> None:
        """Vérifie que la route /openapi.json n'est pas dépréciée."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert "Deprecation" not in response.headers


class TestPrometheusMetrics:
    """Tests pour les métriques Prometheus."""

    def test_legacy_hits_metric_incremented(self, client: TestClient) -> None:
        """Vérifie que la métrique apigw_legacy_hits_total est incrémentée."""
        from backend.apigw.versioning import LEGACY_HITS_TOTAL

        # Réinitialiser les métriques
        LEGACY_HITS_TOTAL.clear()

        # Faire une requête legacy
        client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "password"},
            follow_redirects=False,
        )

        # Vérifier que la métrique est incrémentée
        samples = list(LEGACY_HITS_TOTAL.collect()[0].samples)
        assert len(samples) > 0
        assert any(
            sample.labels["route"] == "/auth" and sample.labels["method"] == "POST"
            for sample in samples
        )

    def test_redirects_metric_incremented(self, client: TestClient) -> None:
        """Vérifie que la métrique apigw_redirects_total est incrémentée."""
        from backend.apigw.versioning import REDIRECTS_TOTAL

        # Réinitialiser les métriques
        REDIRECTS_TOTAL.clear()

        # Faire une requête legacy
        client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "password"},
            follow_redirects=False,
        )

        # Vérifier que la métrique est incrémentée
        samples = list(REDIRECTS_TOTAL.collect()[0].samples)
        assert len(samples) > 0
        assert any(
            sample.labels["route"] == "/auth" and sample.labels["status"] == "308"
            for sample in samples
        )


class TestDeprecationHeaders:
    """Tests pour les headers de dépréciation."""

    def test_deprecation_headers_present(self, client: TestClient) -> None:
        """Vérifie que tous les headers de dépréciation sont présents."""
        response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "password"},
            follow_redirects=False,
        )

        headers = response.headers
        assert "Deprecation" in headers
        assert "Sunset" in headers
        assert "Warning" in headers
        assert "Location" in headers
        assert "Link" in headers
        assert "Cache-Control" in headers

    def test_sunset_date_format(self, client: TestClient) -> None:
        """Vérifie que la date de sunset est au bon format RFC 8594."""
        response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "password"},
            follow_redirects=False,
        )

        sunset_date = response.headers["Sunset"]
        assert sunset_date == "Wed, 31 Dec 2025 23:59:59 GMT"

    def test_deprecation_header_format(self, client: TestClient) -> None:
        """Vérifie le format du header Deprecation selon RFC 9745."""
        response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "password"},
            follow_redirects=False,
        )

        deprecation = response.headers["Deprecation"]
        assert deprecation == "@1761264000"  # Unix timestamp avec @

    def test_warning_header_format(self, client: TestClient) -> None:
        """Vérifie le format du header Warning."""
        response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "password"},
            follow_redirects=False,
        )

        warning = response.headers["Warning"]
        assert warning.startswith('299 - "Deprecated API. Use /v1')
        assert "/auth/login" in warning

    def test_link_header_format(self, client: TestClient) -> None:
        """Vérifie le format du header Link avec rel="deprecation"."""
        response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "password"},
            follow_redirects=False,
        )

        link = response.headers["Link"]
        assert "rel=\"successor-version\"" in link
        assert "rel=\"deprecation\"" in link
        assert "/v1/auth/login" in link
        assert "https://docs.astro.com/api/versioning" in link


class TestDeprecationResponse:
    """Tests pour le contenu de la réponse de dépréciation."""

    def test_response_structure(self, client: TestClient) -> None:
        """Vérifie la structure de la réponse JSON de dépréciation."""
        response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "password"},
            follow_redirects=False,
        )
        data = response.json()

        # Champs obligatoires
        assert "code" in data
        assert "message" in data
        assert "trace_id" in data
        assert "deprecation" in data

        # Structure du champ deprecation
        deprecation = data["deprecation"]
        assert "sunset_date" in deprecation
        assert "new_path" in deprecation
        assert "warning" in deprecation

    def test_response_content_values(self, client: TestClient) -> None:
        """Vérifie les valeurs spécifiques dans la réponse."""
        response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "password"},
            follow_redirects=False,
        )
        data = response.json()

        assert data["code"] == "DEPRECATED_ROUTE"
        assert "dépréciée" in data["message"]
        assert "2025-12-31" in data["message"]
        assert data["deprecation"]["sunset_date"] == "2025-12-31"
        assert data["deprecation"]["new_path"] == "/v1/auth/login"

        # Vérifier que le cache est configuré
        assert response.headers["Cache-Control"] == "public, max-age=86400"

    def test_trace_id_present(self, client: TestClient) -> None:
        """Vérifie que le trace_id est présent dans la réponse."""
        response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "password"},
            follow_redirects=False,
        )
        data = response.json()

        assert "trace_id" in data
        assert data["trace_id"] is not None
        assert data["trace_id"] != ""


class TestSystemRoutesExclusion:
    """Tests pour l'exclusion des routes système du versioning."""

    def test_health_not_deprecated(self, client: TestClient) -> None:
        """Vérifie que /health n'a pas de headers de dépréciation."""
        response = client.get("/health")

        assert response.status_code == 200
        assert "Deprecation" not in response.headers
        assert "Sunset" not in response.headers

    def test_openapi_not_deprecated(self, client: TestClient) -> None:
        """Vérifie que la route /openapi.json n'est pas dépréciée."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert "Deprecation" not in response.headers


