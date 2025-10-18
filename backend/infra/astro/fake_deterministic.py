from typing import Dict, Any, List


class FakeDeterministicAstro:
    def compute_natal_chart(self, birth) -> Dict[str, Any]:
        return {
            "name": birth.name,
            "birth": birth.model_dump(),
            "precision_score": 5 if getattr(birth, "time", None) else 3,
            "factors": [{"axis": "SUN"}, {"axis": "ASC"}, {"axis": "MC"}],
        }

    def compute_daily_transits(self, natal: Dict[str, Any], day_iso: str) -> List[Dict[str, Any]]:
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

