import json
from typing import Any

import redis


class InMemoryChartRepo:
    """Dépôt de thèmes en mémoire (utilisé pour dev/tests).

    Stocke les enregistrements dans un dict local, non persistant.
    """

    def __init__(self):
        """Initialise une base mémoire vide."""
        self._db: dict[str, dict[str, Any]] = {}

    def save(self, record: dict[str, Any]) -> dict[str, Any]:
        """Enregistre/écrase un thème et le renvoie."""
        self._db[record["id"]] = record
        return record

    def get(self, chart_id: str) -> dict[str, Any] | None:
        """Retourne un thème par id, ou None s'il est absent."""
        return self._db.get(chart_id)


class RedisChartRepo:
    """Dépôt de thèmes adossé à Redis (clé: `chart:{id}`)."""

    def __init__(self, url: str):
        """Crée un client Redis à partir de l'URL fournie."""
        self.client = redis.Redis.from_url(url, decode_responses=True)

    def save(self, record: dict[str, Any]) -> dict[str, Any]:
        """Sérialise en JSON et stocke l'enregistrement sous `chart:{id}`."""
        key = f"chart:{record['id']}"
        self.client.set(key, json.dumps(record))
        return record

    def get(self, chart_id: str) -> dict[str, Any] | None:
        """Charge et désérialise le thème `chart:{id}`, si présent."""
        key = f"chart:{chart_id}"
        raw = self.client.get(key)
        return json.loads(raw) if raw else None
