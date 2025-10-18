"""
Module C:/dev/astro/v1/backend/api/schemas.py

Objectif du module: Définit les schémas Pydantic de l'API.

TODO:
- Préciser le rôle exact et exemples d'utilisation.
"""

from typing import Literal

from pydantic import BaseModel


class BirthRequest(BaseModel):
    name: str
    date: str
    time: str | None = None
    tz: str
    lat: float
    lon: float
    time_certainty: Literal["exact", "morning", "afternoon", "evening", "unknown"] = "exact"

"""Modèle Pydantic BirthRequest.

Champs:
- name: str
- date: str
- time: str | None
- tz: str
- lat: float
- lon: float
- time_certainty: Literal['exact', 'morning', 'afternoon', 'evening', 'unknown']

TODO:
- Compléter la description et les invariants.
"""

class NatalResponse(BaseModel):
    id: str
    owner: str
    chart: dict


class TodayResponse(BaseModel):
    date: str
    leaders: list[dict]
    """Modèle Pydantic NatalResponse.
    
    Champs:
    - id: str
    - owner: str
    - chart: dict
    
    TODO:
    - Compléter la description et les invariants.
    """
    influences: list[dict]
    eao: dict
    snippets: list[dict]
    precision_score: int

"""Modèle Pydantic TodayResponse.

Champs:
- date: str
- leaders: list[dict]
- influences: list[dict]
- eao: dict
- snippets: list[dict]
- precision_score: int

TODO:
- Compléter la description et les invariants.
"""
