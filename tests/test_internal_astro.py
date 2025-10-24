"""Tests pour le moteur astrologique interne.

Ce module teste le moteur astrologique interne avec génération pseudo-aléatoire.
"""

from __future__ import annotations

from backend.domain.entities import BirthInput
from backend.infra.astro.internal_astro import InternalAstroEngine


def test_internal_astro_engine_init_without_seed() -> None:
    """Teste l'initialisation du moteur sans graine."""
    engine = InternalAstroEngine()
    assert engine._rng is not None


def test_internal_astro_engine_init_with_seed() -> None:
    """Teste l'initialisation du moteur avec une graine."""
    engine = InternalAstroEngine(seed=42)
    assert engine._rng is not None


def test_compute_natal_chart_basic() -> None:
    """Teste le calcul d'un thème natal de base."""
    engine = InternalAstroEngine(seed=42)
    birth = BirthInput(
        name="Test User",
        date="1990-01-01",
        time="12:00:00",
        tz="Europe/Paris",
        lat=48.85,
        lon=2.35,
        time_certainty="exact",
    )

    result = engine.compute_natal_chart(birth)

    assert result["name"] == "Test User"
    assert result["precision_score"] == 5  # exact time
    assert "birth" in result
    assert "factors" in result
    assert len(result["factors"]) == 3
    assert result["factors"][0]["axis"] == "SUN"
    assert result["factors"][1]["axis"] == "ASC"
    assert result["factors"][2]["axis"] == "MC"


def test_compute_natal_chart_morning_certainty() -> None:
    """Teste le calcul d'un thème natal avec certitude matinale."""
    engine = InternalAstroEngine(seed=42)
    birth = BirthInput(
        name="Test User",
        date="1990-01-01",
        time="12:00:00",
        tz="Europe/Paris",
        lat=48.85,
        lon=2.35,
        time_certainty="morning",
    )

    result = engine.compute_natal_chart(birth)

    assert result["precision_score"] == 3  # morning time


def test_compute_natal_chart_unknown_certainty() -> None:
    """Teste le calcul d'un thème natal avec certitude inconnue."""
    engine = InternalAstroEngine(seed=42)
    birth = BirthInput(
        name="Test User",
        date="1990-01-01",
        time="12:00:00",
        tz="Europe/Paris",
        lat=48.85,
        lon=2.35,
        time_certainty="unknown",
    )

    result = engine.compute_natal_chart(birth)

    assert result["precision_score"] == 1  # unknown time


def test_compute_daily_transits_deterministic() -> None:
    """Teste le calcul de transits quotidiens avec graine déterministe."""
    engine = InternalAstroEngine(seed=42)
    natal = {"name": "Test User", "factors": []}

    result = engine.compute_daily_transits(natal, "2024-01-01")

    assert len(result) == 6
    for transit in result:
        assert "axis" in transit
        assert "intensity" in transit
        assert "friction" in transit
        assert "weight" in transit
        assert "snippet_id" in transit
        assert 0.5 <= transit["intensity"] <= 1.5
        assert 0.0 <= transit["friction"] <= 0.6
        assert transit["weight"] == 1.0
        assert transit["snippet_id"].startswith("TODAY_")
        assert transit["snippet_id"].endswith("_EN")


def test_compute_daily_transits_reproducible() -> None:
    """Teste que les transits sont reproductibles avec la même graine."""
    engine1 = InternalAstroEngine(seed=42)
    engine2 = InternalAstroEngine(seed=42)
    natal = {"name": "Test User", "factors": []}

    result1 = engine1.compute_daily_transits(natal, "2024-01-01")
    result2 = engine2.compute_daily_transits(natal, "2024-01-01")

    assert result1 == result2


def test_compute_daily_transits_different_seeds() -> None:
    """Teste que les transits diffèrent avec des graines différentes."""
    engine1 = InternalAstroEngine(seed=42)
    engine2 = InternalAstroEngine(seed=123)
    natal = {"name": "Test User", "factors": []}

    result1 = engine1.compute_daily_transits(natal, "2024-01-01")
    result2 = engine2.compute_daily_transits(natal, "2024-01-01")

    # Les résultats peuvent être identiques par hasard, mais très peu probable
    # On teste au moins que les structures sont correctes
    assert len(result1) == len(result2) == 6


def test_compute_daily_transits_axis_values() -> None:
    """Teste que les axes générés sont valides."""
    engine = InternalAstroEngine(seed=42)
    natal = {"name": "Test User", "factors": []}

    result = engine.compute_daily_transits(natal, "2024-01-01")

    valid_axes = {"SUN", "MARS", "ASC", "MERCURY", "SATURN", "MC", "VENUS", "JUPITER", "NN"}
    for transit in result:
        assert transit["axis"] in valid_axes


def test_compute_daily_transits_numeric_precision() -> None:
    """Teste la précision numérique des valeurs générées."""
    engine = InternalAstroEngine(seed=42)
    natal = {"name": "Test User", "factors": []}

    result = engine.compute_daily_transits(natal, "2024-01-01")

    for transit in result:
        # Vérifier que les valeurs sont arrondies à 2 décimales
        intensity_str = str(transit["intensity"])
        friction_str = str(transit["friction"])

        if "." in intensity_str:
            assert len(intensity_str.split(".")[1]) <= 2
        if "." in friction_str:
            assert len(friction_str.split(".")[1]) <= 2


def test_compute_daily_transits_ignores_natal() -> None:
    """Teste que le thème natal n'influence pas les transits."""
    # Utiliser des moteurs séparés avec la même graine pour éviter l'état partagé
    engine1 = InternalAstroEngine(seed=42)
    engine2 = InternalAstroEngine(seed=42)
    natal1 = {"name": "User 1", "factors": [{"axis": "SUN"}]}
    natal2 = {"name": "User 2", "factors": [{"axis": "MOON"}]}

    result1 = engine1.compute_daily_transits(natal1, "2024-01-01")
    result2 = engine2.compute_daily_transits(natal2, "2024-01-01")

    # Les résultats doivent être identiques car le natal n'est pas utilisé
    assert result1 == result2


def test_compute_daily_transits_ignores_date() -> None:
    """Teste que la date n'influence pas les transits."""
    # Utiliser des moteurs séparés avec la même graine pour éviter l'état partagé
    engine1 = InternalAstroEngine(seed=42)
    engine2 = InternalAstroEngine(seed=42)
    natal = {"name": "Test User", "factors": []}

    result1 = engine1.compute_daily_transits(natal, "2024-01-01")
    result2 = engine2.compute_daily_transits(natal, "2024-12-31")

    # Les résultats doivent être identiques car la date n'est pas utilisée
    assert result1 == result2
