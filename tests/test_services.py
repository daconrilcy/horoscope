"""
Tests pour le service métier principal des horoscopes.

Ce module teste le service HoroscopeService qui orchestre les calculs astrologiques.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import Mock

from backend.domain.entities import BirthInput, User
from backend.domain.services import HoroscopeService

# Constantes pour éviter les erreurs PLR2004 (Magic values)
EXPECTED_COUNT_3 = 3
EXPECTED_COUNT_5 = 5


def test_horoscope_service_init() -> None:
    """Teste l'initialisation du service horoscope."""
    astro_engine = Mock()
    content_repo = Mock()
    chart_repo = Mock()

    service = HoroscopeService(astro_engine, content_repo, chart_repo)

    assert service.astro == astro_engine
    assert service.content == content_repo
    assert service.charts == chart_repo


def test_compute_natal_basic() -> None:
    """Teste le calcul d'un thème natal de base."""
    # Mock des dépendances
    astro_engine = Mock()
    content_repo = Mock()
    chart_repo = Mock()

    # Configuration des mocks
    mock_chart = {"name": "Test User", "precision_score": 5, "factors": []}
    astro_engine.compute_natal_chart.return_value = mock_chart
    chart_repo.save.return_value = None

    service = HoroscopeService(astro_engine, content_repo, chart_repo)

    birth = BirthInput(
        name="Test User",
        date="1990-01-01",
        time="12:00:00",
        tz="Europe/Paris",
        lat=48.85,
        lon=2.35,
        time_certainty="exact",
    )

    result = service.compute_natal(birth)

    # Vérifications
    assert "id" in result
    assert result["owner"] == "Test User"
    assert result["chart"] == mock_chart
    assert len(result["id"]) > 0  # UUID généré

    # Vérifier que les méthodes ont été appelées
    astro_engine.compute_natal_chart.assert_called_once_with(birth)
    chart_repo.save.assert_called_once()


def test_compute_natal_chart_save() -> None:
    """Teste que le thème natal est sauvegardé correctement."""
    astro_engine = Mock()
    content_repo = Mock()
    chart_repo = Mock()

    mock_chart = {"name": "Test User", "precision_score": 3}
    astro_engine.compute_natal_chart.return_value = mock_chart

    service = HoroscopeService(astro_engine, content_repo, chart_repo)

    birth = BirthInput(
        name="Test User",
        date="1990-01-01",
        time="12:00:00",
        tz="Europe/Paris",
        lat=48.85,
        lon=2.35,
        time_certainty="morning",
    )

    service.compute_natal(birth)

    # Vérifier que save a été appelé avec les bonnes données
    chart_repo.save.assert_called_once()
    saved_record = chart_repo.save.call_args[0][0]
    assert saved_record["owner"] == "Test User"
    assert saved_record["chart"] == mock_chart
    assert "id" in saved_record


def test_get_today_success() -> None:
    """Teste la récupération d'un horoscope du jour avec succès."""
    astro_engine = Mock()
    content_repo = Mock()
    chart_repo = Mock()

    # Mock des données
    chart_id = "test-chart-id"
    mock_chart = {
        "id": chart_id,
        "owner": "Test User",
        "chart": {"precision_score": 5, "factors": []},
    }
    mock_transits = [
        {"axis": "SUN", "snippet_id": "TODAY_SUN_EN"},
        {"axis": "MARS", "snippet_id": "TODAY_MARS_EN"},
        {"axis": "VENUS", "snippet_id": "TODAY_VENUS_EN"},
    ]
    mock_snippet = "Today is a great day for creativity"

    chart_repo.get.return_value = mock_chart
    astro_engine.compute_daily_transits.return_value = mock_transits
    content_repo.get_snippet.return_value = mock_snippet

    service = HoroscopeService(astro_engine, content_repo, chart_repo)

    result = service.get_today(chart_id)

    # Vérifications
    assert result["date"] == date.today().isoformat()
    assert "leaders" in result
    assert "influences" in result
    assert "eao" in result
    assert "snippets" in result
    assert result["precision_score"] == EXPECTED_COUNT_5

    # Vérifier que les méthodes ont été appelées
    chart_repo.get.assert_called_once_with(chart_id)
    astro_engine.compute_daily_transits.assert_called_once_with(
        mock_chart["chart"], date.today().isoformat()
    )


def test_get_today_chart_not_found() -> None:
    """Teste la gestion d'erreur quand le thème n'est pas trouvé."""
    astro_engine = Mock()
    content_repo = Mock()
    chart_repo = Mock()

    chart_repo.get.return_value = None

    service = HoroscopeService(astro_engine, content_repo, chart_repo)

    try:
        service.get_today("non-existent-chart")
        raise AssertionError("KeyError should have been raised")
    except KeyError as e:
        assert str(e) == "'chart_not_found'"


def test_get_today_with_user() -> None:
    """Teste la récupération d'un horoscope du jour avec un utilisateur."""
    astro_engine = Mock()
    content_repo = Mock()
    chart_repo = Mock()

    chart_id = "test-chart-id"
    mock_chart = {
        "id": chart_id,
        "owner": "Test User",
        "chart": {"precision_score": 3, "factors": []},
    }
    mock_transits = [{"axis": "SUN", "snippet_id": "TODAY_SUN_EN"}]

    chart_repo.get.return_value = mock_chart
    astro_engine.compute_daily_transits.return_value = mock_transits
    content_repo.get_snippet.return_value = "Test snippet"

    service = HoroscopeService(astro_engine, content_repo, chart_repo)

    user = User(id="user-1", email="test@example.com", tenant="default")
    result = service.get_today(chart_id, user)

    # Vérifier que le résultat est correct
    assert result["precision_score"] == EXPECTED_COUNT_3
    assert result["date"] == date.today().isoformat()


def test_get_today_without_snippet_id() -> None:
    """Teste la gestion des transits sans snippet_id."""
    astro_engine = Mock()
    content_repo = Mock()
    chart_repo = Mock()

    chart_id = "test-chart-id"
    mock_chart = {
        "id": chart_id,
        "owner": "Test User",
        "chart": {"precision_score": 1, "factors": []},
    }
    mock_transits = [
        {"axis": "SUN"},  # Pas de snippet_id
        {"axis": "MARS", "snippet_id": "TODAY_MARS_EN"},
    ]

    chart_repo.get.return_value = mock_chart
    astro_engine.compute_daily_transits.return_value = mock_transits
    content_repo.get_snippet.return_value = "Test snippet"

    service = HoroscopeService(astro_engine, content_repo, chart_repo)

    service.get_today(chart_id)

    # Vérifier que get_snippet n'est appelé que pour les transits avec snippet_id
    assert content_repo.get_snippet.call_count == 1
    content_repo.get_snippet.assert_called_with("TODAY_MARS_EN")


def test_get_today_precision_score_default() -> None:
    """Teste la valeur par défaut du precision_score."""
    astro_engine = Mock()
    content_repo = Mock()
    chart_repo = Mock()

    chart_id = "test-chart-id"
    mock_chart = {
        "id": chart_id,
        "owner": "Test User",
        "chart": {},  # Pas de precision_score
    }
    mock_transits = []

    chart_repo.get.return_value = mock_chart
    astro_engine.compute_daily_transits.return_value = mock_transits

    service = HoroscopeService(astro_engine, content_repo, chart_repo)

    result = service.get_today(chart_id)

    # Vérifier que la valeur par défaut est utilisée
    assert result["precision_score"] == 1


def test_get_today_empty_transits() -> None:
    """Teste la gestion des transits vides."""
    astro_engine = Mock()
    content_repo = Mock()
    chart_repo = Mock()

    chart_id = "test-chart-id"
    mock_chart = {
        "id": chart_id,
        "owner": "Test User",
        "chart": {"precision_score": 2, "factors": []},
    }
    mock_transits = []  # Liste vide

    chart_repo.get.return_value = mock_chart
    astro_engine.compute_daily_transits.return_value = mock_transits

    service = HoroscopeService(astro_engine, content_repo, chart_repo)

    result = service.get_today(chart_id)

    # Vérifier que les listes sont vides
    assert result["leaders"] == []
    assert result["influences"] == []
    assert result["snippets"] == []
    assert result["eao"] == {"energy": 0, "attention": 0, "opportunity": 0}
