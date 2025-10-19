# ============================================================
# Module : backend/infra/repo/content_version_repo.py
# Objet  : Accès SQL (CRUD) pour ContentVersion (squelette).
# Notes  : à intégrer avec SQLAlchemy (non inclus ici).
# ============================================================

from __future__ import annotations

from typing import Any

from ...domain.content_version import ContentVersion


class ContentVersionRepo:
    """CRUD minimal pour ContentVersion."""

    def __init__(self, session: Any) -> None:
        """Construit le repo avec une session (SQLAlchemy)."""
        self._session = session

    def create(self, cv: ContentVersion) -> None:
        """Crée une ligne en base (placeholder)."""
        # TODO: mapper ORM + commit
        _ = cv

    def get_latest(self, source: str, tenant: str | None) -> ContentVersion | None:
        """Retourne la dernière version pour une source/tenant."""
        _ = (source, tenant)
        return None

    def list_all(self, tenant: str | None = None) -> list[ContentVersion]:
        """Retourne la liste des versions (filtrable par tenant)."""
        _ = tenant
        return []
