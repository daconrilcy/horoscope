# Schémas Pydantic exposés par l'API (requêtes et réponses).

from typing import Literal

from pydantic import BaseModel


class BirthRequest(BaseModel):
    """Modèle de requête pour créer un thème natal.

    Champs:
    - name: str
    - date: str (YYYY-MM-DD)
    - time: str | None (HH:MM ou None)
    - tz: str (IANA timezone)
    - lat: float (latitude décimale)
    - lon: float (longitude décimale)
    - time_certainty: précision de l'heure (exact/morning/afternoon/evening/unknown)
    """

    name: str
    date: str
    time: str | None = None
    tz: str
    lat: float
    lon: float
    time_certainty: Literal["exact", "morning", "afternoon", "evening", "unknown"] = "exact"


class NatalResponse(BaseModel):
    """Réponse renvoyée après création d'un thème natal.

    Champs:
    - id: str (identifiant unique du thème)
    - owner: str (nom du propriétaire)
    - chart: dict (contenu du thème calculé)
    """

    id: str
    owner: str
    chart: dict


class TodayResponse(BaseModel):
    """Réponse “horoscope du jour” pour un thème existant.

    Champs:
    - date: str (YYYY-MM-DD)
    - leaders: list[dict] (facteurs dominants)
    - influences: list[dict] (facteurs secondaires)
    - eao: dict (scores énergie/attention/opportunité)
    - snippets: list[dict] (extraits de contenu associés)
    - precision_score: int (qualité du thème)
    """

    date: str
    leaders: list[dict]
    influences: list[dict]
    eao: dict
    snippets: list[dict]
    precision_score: int
