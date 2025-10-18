"""
Endpoint de santé pour vérifier la disponibilité de l'API.
"""

from fastapi import APIRouter
from backend.core.container import container

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """Vérifie la disponibilité de l'API et le backend de stockage."""
    return {
        "status": "ok",
        "storage": getattr(container, "storage_backend", "unknown"),
        "redis_url": bool(getattr(container.settings, "REDIS_URL", None)),
    }
