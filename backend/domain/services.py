import uuid
from datetime import date as _date
from typing import Any

from backend.domain.entities import BirthInput, User
from backend.domain.today_heuristic import energy_attention_opportunity, pick_today


class HoroscopeService:
    """Service métier pour calculs et contenus d'horoscopes.

    Responsabilités:
    - Orchestrer les calculs de thème natal et de transits via `astro_engine`.
    - Persister/charger les thèmes via `chart_repo` (en mémoire ou Redis).
    - Récupérer des extraits de contenus via `content_repo`.
    """

    def __init__(self, astro_engine, content_repo, chart_repo):
        """Initialise le service avec ses dépendances.

        Paramètres:
        - astro_engine: composant réalisant les calculs astrologiques.
        - content_repo: dépôt de fragments textuels associés aux facteurs.
        - chart_repo: dépôt de thèmes (InMemory ou Redis).
        """
        self.astro = astro_engine
        self.content = content_repo
        self.charts = chart_repo

    def compute_natal(self, birth: BirthInput) -> dict[str, Any]:
        """Calcule le thème natal et le stocke.

        Paramètres:
        - birth: `BirthInput` avec les informations de naissance.

        Retour: dict avec `id`, `owner` et `chart` (contenu calculé).
        """
        chart = self.astro.compute_natal_chart(birth)
        chart_id = str(uuid.uuid4())
        chart_record = {"id": chart_id, "owner": birth.name, "chart": chart}
        self.charts.save(chart_record)
        return chart_record

    def get_today(self, chart_id: str, user: User | None = None) -> dict[str, Any]:
        """Produit un “horoscope du jour” pour un thème existant.

        Démarche:
        - Charge le thème `chart_id` (erreur si absent).
        - Calcule les transits du jour et sélectionne `leaders` et `influences`.
        - Synthétise un score EAO (énergie/attention/opportunité).
        - Joint les extraits de contenu (snippets) quand disponibles.

        Paramètres:
        - chart_id: identifiant du thème stocké.
        - user: utilisateur (réservé évolutions futures).

        Retour: dict contenant `date`, `leaders`, `influences`, `eao`, `snippets`, `precision_score`.
        """
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
