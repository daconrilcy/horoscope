"""Modèles de domaine (cœur métier) indépendants de l'API.

Objectif du module
------------------
- Définir les entités et structures utilisées au cœur du domaine.
"""

from typing import Literal

from pydantic import BaseModel, Field


class BirthData(BaseModel):
    """Données de naissance nécessaires au calcul d'une carte."""

    name: str = Field(..., description="Person name")
    date: str = Field(..., description="ISO date YYYY-MM-DD")
    time: str = Field(..., description="HH:MM")
    tz: str = Field(..., description="IANA TZ, e.g. Europe/Paris")
    lat: float
    lon: float


class Chart(BaseModel):
    """Représente une carte (chart) calculée pour une personne."""

    id: str
    owner: str
    system: Literal["tropical", "sidereal"] = "tropical"
    summary: str | None = None
