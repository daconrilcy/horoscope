"""
Endpoint de santé pour vérifier la disponibilité de l'API.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """Vérifie la disponibilité de l'API.

    Retour: dict avec la clé `status` à "ok" si l'API répond.
    """
    return {"status": "ok"}
