"""Services métier encapsulant la logique de calcul de chart.

Objectif du module
------------------
- Proposer des opérations métier (ex: calculer une carte) isolées de l'API et
  de l'infrastructure.
"""

import uuid

from domain.models import BirthData, Chart


class ChartService:
    """Expose la logique de calcul d'une carte.

    Implémentation actuelle mockée; à remplacer par un calcul réel (éphémérides,
    librairies astro, LLM, etc.).
    """

    def compute_chart(self, birth: BirthData) -> Chart:
        """Calcule (mock) et retourne une `Chart` à partir des données de naissance."""
        # TODO: brancher un calcul réel (éphémérides/LLM) ultérieurement
        return Chart(
            id=str(uuid.uuid4()),
            owner=birth.name,
            summary=f"Mock chart for {birth.name} ({birth.date} at {birth.time} {birth.tz})",
        )
