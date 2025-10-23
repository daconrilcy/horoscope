"""
Repositories pour la gestion des données.

Ce module fournit des implémentations de repositories pour différents types de données, avec des
versions en mémoire et Redis.
"""

import json
from typing import Any

import redis


class InMemoryChartRepo:
    """
    Dépôt de thèmes en mémoire (utilisé pour dev/tests).

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


class InMemoryUserRepo:
    """Dépôt utilisateurs en mémoire (email indexée par scan simple)."""

    def __init__(self):
        """Initialise une base mémoire vide."""
        self._db: dict[str, dict[str, Any]] = {}

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        """Recherche un utilisateur par email."""
        return next((u for u in self._db.values() if u.get("email") == email), None)

    def save(self, user: dict[str, Any]) -> dict[str, Any]:
        """Sauvegarde un utilisateur."""
        self._db[user["id"]] = user
        return user


class RedisUserRepo:
    """Dépôt utilisateurs via Redis avec index email->id (hash)."""

    def __init__(self, url: str):
        """Crée un client Redis à partir de l'URL fournie."""
        self.client = redis.Redis.from_url(url, decode_responses=True)
        self.idx_key = "user:idx:email"

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        """Recherche un utilisateur par email via l'index Redis."""
        user_id = self.client.hget(self.idx_key, email)
        if not user_id:
            return None
        raw = self.client.get(f"user:{user_id}")
        return json.loads(raw) if raw else None

    def save(self, user: dict[str, Any]) -> dict[str, Any]:
        """Sauvegarde un utilisateur et met à jour l'index email."""
        key = f"user:{user['id']}"
        pipe = self.client.pipeline()
        pipe.set(key, json.dumps(user))
        pipe.hset(self.idx_key, user["email"], user["id"])
        pipe.execute()
        return user
