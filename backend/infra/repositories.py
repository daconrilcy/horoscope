"""Dépôts (repositories) d'accès aux données.

Objectif du module
------------------
- Offrir une abstraction de persistance pour les charts.
"""

from domain.models import Chart


class InMemoryChartRepo:
    """Stockage en mémoire pour les charts (usage démo/tests)."""

    def __init__(self):
        # Dictionnaire interne simulant une base clé/valeur
        self._db: dict[str, Chart] = {}

    def save(self, chart: Chart) -> Chart:
        """Persiste ou remplace une chart par son identifiant et la retourne."""
        self._db[chart.id] = chart
        return chart

    def get(self, chart_id: str) -> Chart | None:
        """Récupère une chart par identifiant, ou None si absente."""
        return self._db.get(chart_id)
