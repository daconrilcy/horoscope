"""Endpoints de santé (healthcheck) de l'application."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """Indique que l'API est joignable et opérationnelle."""
    return {"status": "ok"}
