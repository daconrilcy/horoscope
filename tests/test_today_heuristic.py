"""Tests pour les heuristiques de sélection des facteurs du jour.

Ce module teste les fonctions de scoring et de sélection des facteurs astrologiques
pour les horoscopes quotidiens.
"""

# Constantes pour éviter les erreurs PLR2004 (Magic values)
EXPECTED_COUNT_2 = 2
EXPECTED_COUNT_3 = 3
EXPECTED_COUNT_4 = 4
EXPECTED_COUNT_5 = 5
EXPECTED_COUNT_6 = 6
SCORE_2_5 = 2.5
SCORE_3_0 = 3.0
SCORE_2_0 = 2.0
SCORE_0_5 = 0.5
SCORE_4_0 = 4.0
SCORE_5_0 = 5.0
SCORE_6_0 = 6.0
SCORE_7_0 = 7.0

from __future__ import annotations

from backend.domain.today_heuristic import (
    energy_attention_opportunity,
    pick_today,
    score_factor,
)


def test_score_factor_basic() -> None:
    """Teste le calcul de score de base pour un facteur."""
    factor = {"weight": 2.0, "intensity": 1.5, "friction": 0.5}
    result = score_factor(factor)
    assert result == SCORE_2_5  # 2.0 * 1.5 - 0.5


def test_score_factor_default_values() -> None:
    """Teste le calcul de score avec des valeurs par défaut."""
    factor = {}
    result = score_factor(factor)
    assert result == 1.0  # 1.0 * 1.0 - 0.0


def test_score_factor_partial_values() -> None:
    """Teste le calcul de score avec des valeurs partielles."""
    factor = {"weight": 3.0}
    result = score_factor(factor)
    assert result == SCORE_3_0  # 3.0 * 1.0 - 0.0

    factor = {"intensity": 2.0}
    result = score_factor(factor)
    assert result == SCORE_2_0  # 1.0 * 2.0 - 0.0

    factor = {"friction": 0.5}
    result = score_factor(factor)
    assert result  == SCORE_0_5  # 1.0 * 1.0 - 0.5


def test_score_factor_negative_result() -> None:
    """Teste le calcul de score avec un résultat négatif."""
    factor = {"weight": 1.0, "intensity": 1.0, "friction": 2.0}
    result = score_factor(factor)
    assert result == -1.0  # 1.0 * 1.0 - 2.0


def test_pick_today_empty_list() -> None:
    """Teste la sélection avec une liste vide."""
    leaders, influences = pick_today([])
    assert leaders == []
    assert influences == []


def test_pick_today_single_factor() -> None:
    """Teste la sélection avec un seul facteur."""
    transits = [{"weight": 2.0, "intensity": 1.0, "friction": 0.0}]
    leaders, influences = pick_today(transits)
    assert len(leaders) == 1
    assert len(influences) == 0
    assert leaders[0] == transits[0]


def test_pick_today_three_factors() -> None:
    """Teste la sélection avec exactement trois facteurs."""
    transits = [
        {"weight": 3.0, "intensity": 1.0, "friction": 0.0},  # score: 3.0
        {"weight": 2.0, "intensity": 1.0, "friction": 0.0},  # score: 2.0
        {"weight": 1.0, "intensity": 1.0, "friction": 0.0},  # score: 1.0
    ]
    leaders, influences = pick_today(transits)
    assert len(leaders) == EXPECTED_COUNT_3
    assert len(influences) == 0
    assert leaders[0]["weight"] == SCORE_3_0
    assert leaders[1]["weight"] == SCORE_2_0
    assert leaders[2]["weight"] == 1.0


def test_pick_today_six_factors() -> None:
    """Teste la sélection avec six facteurs (3 leaders + 3 influences)."""
    transits = [
        {"weight": 6.0, "intensity": 1.0, "friction": 0.0},  # score: 6.0
        {"weight": 5.0, "intensity": 1.0, "friction": 0.0},  # score: 5.0
        {"weight": 4.0, "intensity": 1.0, "friction": 0.0},  # score: 4.0
        {"weight": 3.0, "intensity": 1.0, "friction": 0.0},  # score: 3.0
        {"weight": 2.0, "intensity": 1.0, "friction": 0.0},  # score: 2.0
        {"weight": 1.0, "intensity": 1.0, "friction": 0.0},  # score: 1.0
    ]
    leaders, influences = pick_today(transits)
    assert len(leaders) == EXPECTED_COUNT_3
    assert len(influences) == EXPECTED_COUNT_3
    assert leaders[0]["weight"] == SCORE_6_0
    assert leaders[1]["weight"] == SCORE_5_0
    assert leaders[2]["weight"] == SCORE_4_0
    assert influences[0]["weight"] == SCORE_3_0
    assert influences[1]["weight"] == SCORE_2_0
    assert influences[2]["weight"] == 1.0


def test_pick_today_more_than_six_factors() -> None:
    """Teste la sélection avec plus de six facteurs."""
    transits = [
        {"weight": 7.0, "intensity": 1.0, "friction": 0.0},  # score: 7.0
        {"weight": 6.0, "intensity": 1.0, "friction": 0.0},  # score: 6.0
        {"weight": 5.0, "intensity": 1.0, "friction": 0.0},  # score: 5.0
        {"weight": 4.0, "intensity": 1.0, "friction": 0.0},  # score: 4.0
        {"weight": 3.0, "intensity": 1.0, "friction": 0.0},  # score: 3.0
        {"weight": 2.0, "intensity": 1.0, "friction": 0.0},  # score: 2.0
        {"weight": 1.0, "intensity": 1.0, "friction": 0.0},  # score: 1.0
    ]
    leaders, influences = pick_today(transits)
    assert len(leaders) == EXPECTED_COUNT_3
    assert len(influences) == EXPECTED_COUNT_3
    assert leaders[0]["weight"]  == SCORE_7_0
    assert leaders[1]["weight"] == SCORE_6_0
    assert leaders[2]["weight"] == SCORE_5_0
    assert influences[0]["weight"] == SCORE_4_0
    assert influences[1]["weight"] == SCORE_3_0
    assert influences[2]["weight"] == SCORE_2_0


def test_pick_today_sorting_order() -> None:
    """Teste que les facteurs sont triés par score décroissant."""
    transits = [
        {"weight": 1.0, "intensity": 1.0, "friction": 0.0},  # score: 1.0
        {"weight": 3.0, "intensity": 1.0, "friction": 0.0},  # score: 3.0
        {"weight": 2.0, "intensity": 1.0, "friction": 0.0},  # score: 2.0
    ]
    leaders, _influences = pick_today(transits)
    assert leaders[0]["weight"] == SCORE_3_0
    assert leaders[1]["weight"] == SCORE_2_0
    assert leaders[2]["weight"] == 1.0


def test_energy_attention_opportunity_empty() -> None:
    """Teste le calcul EAO avec une liste vide."""
    result = energy_attention_opportunity([])
    assert result == {"energy": 0, "attention": 0, "opportunity": 0}


def test_energy_attention_opportunity_energy_axes() -> None:
    """Teste le calcul EAO avec des axes d'énergie."""
    leaders = [
        {"axis": "SUN"},
        {"axis": "MARS"},
        {"axis": "ASC"},
    ]
    result = energy_attention_opportunity(leaders)
    assert result == {"energy": 3, "attention": 0, "opportunity": 0}


def test_energy_attention_opportunity_attention_axes() -> None:
    """Teste le calcul EAO avec des axes d'attention."""
    leaders = [
        {"axis": "MERCURY"},
        {"axis": "SATURN"},
        {"axis": "MC"},
    ]
    result = energy_attention_opportunity(leaders)
    assert result == {"energy": 0, "attention": 3, "opportunity": 0}


def test_energy_attention_opportunity_opportunity_axes() -> None:
    """Teste le calcul EAO avec des axes d'opportunité."""
    leaders = [
        {"axis": "VENUS"},
        {"axis": "JUPITER"},
        {"axis": "NN"},
    ]
    result = energy_attention_opportunity(leaders)
    assert result == {"energy": 0, "attention": 0, "opportunity": 3}


def test_energy_attention_opportunity_mixed_axes() -> None:
    """Teste le calcul EAO avec des axes mixtes."""
    leaders = [
        {"axis": "SUN"},  # energy
        {"axis": "MERCURY"},  # attention
        {"axis": "VENUS"},  # opportunity
        {"axis": "MARS"},  # energy
        {"axis": "SATURN"},  # attention
        {"axis": "JUPITER"},  # opportunity
    ]
    result = energy_attention_opportunity(leaders)
    assert result == {"energy": 2, "attention": 2, "opportunity": 2}


def test_energy_attention_opportunity_unknown_axes() -> None:
    """Teste le calcul EAO avec des axes inconnus."""
    leaders = [
        {"axis": "UNKNOWN1"},
        {"axis": "UNKNOWN2"},
        {"axis": "UNKNOWN3"},
    ]
    result = energy_attention_opportunity(leaders)
    assert result == {"energy": 0, "attention": 0, "opportunity": 0}


def test_energy_attention_opportunity_missing_axis() -> None:
    """Teste le calcul EAO avec des facteurs sans axe."""
    leaders = [
        {"weight": 1.0},
        {"intensity": 2.0},
        {},
    ]
    result = energy_attention_opportunity(leaders)
    assert result == {"energy": 0, "attention": 0, "opportunity": 0}


def test_energy_attention_opportunity_partial_matches() -> None:
    """Teste le calcul EAO avec des correspondances partielles."""
    leaders = [
        {"axis": "SUN"},  # energy
        {"axis": "UNKNOWN"},  # none
        {"axis": "MERCURY"},  # attention
        {"axis": "UNKNOWN"},  # none
        {"axis": "VENUS"},  # opportunity
    ]
    result = energy_attention_opportunity(leaders)
    assert result == {"energy": 1, "attention": 1, "opportunity": 1}
