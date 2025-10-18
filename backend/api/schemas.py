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


class NatalResponse(BaseModel):
    id: str
    owner: str
    chart: dict


class TodayResponse(BaseModel):
    date: str
    leaders: list[dict]
    influences: list[dict]
    eao: dict
    snippets: list[dict]
    precision_score: int

