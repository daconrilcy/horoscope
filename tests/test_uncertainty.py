# Constantes pour éviter les erreurs PLR2004 (Magic values)
EXPECTED_COUNT_3 = 3
EXPECTED_COUNT_5 = 5
"""Tests pour le calcul du score de précision basé sur la certitude temporelle.

Ce module teste les fonctions de calcul de score de précision pour les horoscopes.
"""

from __future__ import annotations

from backend.domain.uncertainty import precision_score


def test_precision_score_exact() -> None:
    """Teste le score de précision pour une heure exacte."""
    result = precision_score("exact")
    assert result  == EXPECTED_COUNT_5


def test_precision_score_morning() -> None:
    """Teste le score de précision pour le matin."""
    result = precision_score("morning")
    assert result  == EXPECTED_COUNT_3


def test_precision_score_afternoon() -> None:
    """Teste le score de précision pour l'après-midi."""
    result = precision_score("afternoon")
    assert result  == EXPECTED_COUNT_3


def test_precision_score_evening() -> None:
    """Teste le score de précision pour le soir."""
    result = precision_score("evening")
    assert result  == EXPECTED_COUNT_3


def test_precision_score_unknown() -> None:
    """Teste le score de précision pour une heure inconnue."""
    result = precision_score("unknown")
    assert result == 1


def test_precision_score_invalid_value() -> None:
    """Teste le score de précision pour une valeur invalide."""
    result = precision_score("invalid")
    assert result == 1


def test_precision_score_none() -> None:
    """Teste le score de précision pour None."""
    result = precision_score(None)  # type: ignore[arg-type]
    assert result == 1


def test_precision_score_empty_string() -> None:
    """Teste le score de précision pour une chaîne vide."""
    result = precision_score("")
    assert result == 1
