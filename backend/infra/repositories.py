import json
from typing import Any

import redis


class InMemoryChartRepo:
    def __init__(self):
        self._db: dict[str, dict[str, Any]] = {}

    def save(self, record: dict[str, Any]) -> dict[str, Any]:
        self._db[record["id"]] = record
        return record

    def get(self, chart_id: str) -> dict[str, Any] | None:
        return self._db.get(chart_id)


class RedisChartRepo:
    def __init__(self, url: str):
        self.client = redis.Redis.from_url(url, decode_responses=True)

    def save(self, record: dict[str, Any]) -> dict[str, Any]:
        key = f"chart:{record['id']}"
        self.client.set(key, json.dumps(record))
        return record

    def get(self, chart_id: str) -> dict[str, Any] | None:
        key = f"chart:{chart_id}"
        raw = self.client.get(key)
        return json.loads(raw) if raw else None

