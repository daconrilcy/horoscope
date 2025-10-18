import random
from typing import Any

from backend.domain.entities import BirthInput
from backend.domain.uncertainty import precision_score


class InternalAstroEngine:
    def compute_natal_chart(self, birth: BirthInput) -> dict[str, Any]:
        return {
            "name": birth.name,
            "birth": birth.model_dump(),
            "precision_score": precision_score(birth.time_certainty),
            "factors": [{"axis": "SUN"}, {"axis": "ASC"}, {"axis": "MC"}],
        }

    def compute_daily_transits(self, natal: dict[str, Any], day_iso: str) -> list[dict[str, Any]]:
        axes = ["SUN", "MARS", "ASC", "MERCURY", "SATURN", "MC", "VENUS", "JUPITER", "NN"]
        transits = []
        for _i in range(6):
            axis = random.choice(axes)
            intensity = round(random.uniform(0.5, 1.5), 2)
            friction = round(random.uniform(0.0, 0.6), 2)
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
