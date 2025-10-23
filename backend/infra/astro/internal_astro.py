"""
Moteur astrologique interne avec génération pseudo-aléatoire.

Ce module implémente un moteur astrologique interne qui génère des résultats pseudo-aléatoires pour
les calculs de thèmes natals et transits quotidiens.
"""

import random
from typing import Any

from backend.domain.entities import BirthInput
from backend.domain.uncertainty import precision_score


class InternalAstroEngine:
    """
    Moteur astrologique interne avec génération pseudo-aléatoire.

    Implémente des calculs astrologiques simplifiés avec génération pseudo-aléatoire pour les tests
    et le développement.
    """

    def __init__(self, seed: int | None = None):
        """
        Initialise le moteur avec une graine optionnelle.

        Args:
            seed: Graine pour la génération pseudo-aléatoire (optionnel).
        """
        # Allow deterministic behavior when a seed is provided
        self._rng = random.Random(seed)

    def compute_natal_chart(self, birth: BirthInput) -> dict[str, Any]:
        """
        Calculate a simplified natal chart.

        Args:
            birth: Données de naissance avec informations temporelles.

        Returns:
            dict[str, Any]: Thème natal avec facteurs de base et score de précision.
        """
        return {
            "name": birth.name,
            "birth": birth.model_dump(),
            "precision_score": precision_score(birth.time_certainty),
            "factors": [{"axis": "SUN"}, {"axis": "ASC"}, {"axis": "MC"}],
        }

    def compute_daily_transits(
        self, natal: dict[str, Any], day_iso: str
    ) -> list[dict[str, Any]]:
        """
        Calculate pseudo-random daily transits.

        Args:
            natal: Thème natal (non utilisé dans cette implémentation simplifiée).
            day_iso: Date au format ISO (non utilisée).

        Returns:
            list[dict[str, Any]]: Liste de transits générés pseudo-aléatoirement.
        """
        axes = [
            "SUN",
            "MARS",
            "ASC",
            "MERCURY",
            "SATURN",
            "MC",
            "VENUS",
            "JUPITER",
            "NN",
        ]
        transits = []
        for _i in range(6):
            axis = self._rng.choice(axes)
            intensity = round(self._rng.uniform(0.5, 1.5), 2)
            friction = round(self._rng.uniform(0.0, 0.6), 2)
            weight = 1.0
            snippet_id = f"TODAY_{axis}_EN"
            transits.append(
                {
                    "axis": axis,
                    "intensity": intensity,
                    "friction": friction,
                    "weight": weight,
                    "snippet_id": snippet_id,
                }
            )
        return transits
