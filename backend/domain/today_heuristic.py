"""
Heuristiques pour sélectionner et résumer les facteurs du jour.

Objectif: à partir d'une liste de transits/facteurs (dict),
ordonner les éléments pertinents, en retirer un petit ensemble “leaders”
et calculer un score synthétique EAO (énergie/attention/opportunité).
"""

from typing import Any


def score_factor(f: dict[str, Any]) -> float:
    """Score simple d'un facteur en fonction de son poids, intensité et friction."""
    return f.get("weight", 1.0) * f.get("intensity", 1.0) - f.get("friction", 0.0)


def pick_today(
    transits: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Classe/transits → leaders/influences selon `score_factor` (ordre décroissant).

    - leaders: top 3
    - influences: 3 suivants (positions 4 à 6)
    """
    ranked = sorted(transits, key=score_factor, reverse=True)
    leaders = ranked[:3]
    influences = ranked[3:6]
    return leaders, influences


def energy_attention_opportunity(leaders: list[dict[str, Any]]) -> dict[str, int]:
    """
    Calculer un score EAO basé sur l'axe de chaque leader.

    Règles simples:
    - Énergie: compte axes SUN/MARS/ASC
    - Attention: compte axes MERCURY/SATURN/MC
    - Opportunité: compte axes VENUS/JUPITER/NN
    """  # noqa: D401
    e = sum(1 for f in leaders if f.get("axis") in ("SUN", "MARS", "ASC"))
    a = sum(1 for f in leaders if f.get("axis") in ("MERCURY", "SATURN", "MC"))
    o = sum(1 for f in leaders if f.get("axis") in ("VENUS", "JUPITER", "NN"))
    return {"energy": e, "attention": a, "opportunity": o}
