"""Moteur astrologique déterministe pour les tests et développement.

Ce module implémente un moteur astrologique factice qui produit des résultats déterministes pour les
tests et le développement sans dépendances externes.
"""

from typing import Any


class FakeDeterministicAstro:
    """Moteur astrologique factice déterministe pour les tests.

    Produit des résultats astrologiques prévisibles et cohérents pour les tests et le développement
    sans calculs réels.
    """

    def compute_natal_chart(self, birth) -> dict[str, Any]:
        """Calculate a fake deterministic natal chart.

        Args:
            birth: Données de naissance (objet avec attributs name, time).

        Returns:
            dict[str, Any]: Thème natal factice avec facteurs fixes.
        """
        return {
            "name": birth.name,
            "birth": birth.model_dump(),
            "precision_score": 5 if getattr(birth, "time", None) else 3,
            "factors": [{"axis": "SUN"}, {"axis": "ASC"}, {"axis": "MC"}],
        }

    def compute_daily_transits(self, natal: dict[str, Any], day_iso: str) -> list[dict[str, Any]]:
        """Calculate fake deterministic daily transits.

        Args:
            natal: Thème natal (non utilisé dans cette implémentation factice).
            day_iso: Date au format ISO (non utilisée).

        Returns:
            list[dict[str, Any]]: Liste de transits factices avec axes fixes.
        """
        axes = ["SUN", "MARS", "ASC", "MERCURY", "SATURN", "MC"]
        return [
            {
                "axis": axes[i],
                "intensity": 1.0 + i * 0.1,
                "friction": 0.1 * i,
                "weight": 1.0,
                "snippet_id": f"TODAY_{axes[i]}_EN",
            }
            for i in range(6)
        ]
