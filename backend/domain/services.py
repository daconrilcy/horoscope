import uuid
from datetime import date as _date
from typing import Any

from domain.entities import BirthInput, User
from domain.today_heuristic import energy_attention_opportunity, pick_today


class HoroscopeService:
    def __init__(self, astro_engine, content_repo, chart_repo):
        self.astro = astro_engine
        self.content = content_repo
        self.charts = chart_repo

    def compute_natal(self, birth: BirthInput) -> dict[str, Any]:
        chart = self.astro.compute_natal_chart(birth)
        chart_id = str(uuid.uuid4())
        chart_record = {"id": chart_id, "owner": birth.name, "chart": chart}
        self.charts.save(chart_record)
        return chart_record

    def get_today(self, chart_id: str, user: User | None = None) -> dict[str, Any]:
        chart = self.charts.get(chart_id)
        if not chart:
            raise KeyError("chart_not_found")
        today = _date.today().isoformat()
        transits = self.astro.compute_daily_transits(chart["chart"], today)
        leaders, influences = pick_today(transits)
        eao = energy_attention_opportunity(leaders)
        snippets = [self.content.get_snippet(f["snippet_id"]) for f in leaders if "snippet_id" in f]
        return {
            "date": today,
            "leaders": leaders,
            "influences": influences,
            "eao": eao,
            "snippets": snippets,
            "precision_score": chart["chart"].get("precision_score", 1),
        }

