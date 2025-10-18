"""Schémas Pydantic exposés par l'API.

Objectif du module
------------------
- Définir des contrats d'entrée/sortie stables pour les endpoints.
- Séparer les modèles de domaine (`domain.models`) des schémas API pour éviter
  les fuites d'implémentation côté client.
"""

from domain.models import Chart
from pydantic import BaseModel


class ComputeChartRequest(BaseModel):
    """Payload attendu pour demander le calcul d'une carte natale."""

    name: str
    date: str
    time: str
    tz: str
    lat: float
    lon: float


class ChartResponse(Chart):
    """Réponse renvoyée par l'API pour une carte calculée.

    Hérite du modèle de domaine `Chart` pour exposer les mêmes champs.
    """

    pass
