from typing import Literal

from pydantic import BaseModel, Field

TimeCertainty = Literal["exact", "morning", "afternoon", "evening", "unknown"]


class User(BaseModel):
    id: str
    email: str
    entitlements: list[str] = Field(default_factory=list)


class BirthInput(BaseModel):
    name: str
    date: str  # YYYY-MM-DD
    time: str | None  # HH:MM or None
    tz: str  # IANA TZ
    lat: float
    lon: float
    time_certainty: TimeCertainty = "exact"

