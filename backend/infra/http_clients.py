"""Clients HTTP externes (éphémérides, géocodage, LLMs, etc.).

Objectif du module
------------------
- Encapsuler les appels réseau vers des services tiers.
"""


class GeoClient:
    """Client de géocodage pour obtenir ville/pays à partir de coordonnées."""

    async def reverse_geocode(self, lat: float, lon: float) -> dict:
        """Retourne (mock) les infos de localisation pour des coordonnées données."""
        # TODO: implémentation réelle
        return {"city": "Paris", "country": "France"}
