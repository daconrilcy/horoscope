"""
Module C:/dev/astro/v1/backend/api/routes_health.py

Objectif du module: Expose les routes et structures de l'API.

TODO:
- Préciser le rôle exact et exemples d'utilisation.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """Vérifie la disponibilité de l'API.

    Retour: dict avec la clé `status` à "ok" si l'API répond.
    """
    return {"status": "ok"}
