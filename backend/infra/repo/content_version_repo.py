# ============================================================
# Module : backend/infra/repo/content_version_repo.py
# Objet  : Accès SQL (CRUD) pour ContentVersion (squelette).
# Notes  : à intégrer avec SQLAlchemy (non inclus ici).
# ============================================================

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...domain.content_version import ContentVersion
from .models import ContentVersionORM


class ContentVersionRepo:
    """CRUD minimal pour ContentVersion."""

    def __init__(self, session: Session) -> None:
        """Construit le repo avec une session (SQLAlchemy)."""
        self._session = session

    def create(self, cv: ContentVersion) -> None:
        """Crée une ligne en base. Lève IntegrityError sur doublon unique.

        Contrainte d'unicité: (source, version, tenant).
        """
        row = ContentVersionORM(
            source=cv.source,
            version=cv.version,
            content_hash=cv.content_hash,
            embedding_model_name=cv.embedding_model_name,
            embedding_model_version=cv.embedding_model_version,
            embed_params=cv.embed_params,
            tenant=cv.tenant,
        )
        self._session.add(row)
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            raise

    def get_latest(self, source: str, tenant: str | None) -> ContentVersion | None:
        """Retourne la dernière version pour une source/tenant (par created_at desc)."""
        stmt = select(ContentVersionORM).where(ContentVersionORM.source == source)
        if tenant is None:
            stmt = stmt.where(ContentVersionORM.tenant.is_(None))
        else:
            stmt = stmt.where(ContentVersionORM.tenant == tenant)
        stmt = stmt.order_by(ContentVersionORM.created_at.desc()).limit(1)
        row = self._session.execute(stmt).scalars().first()
        if not row:
            return None
        return ContentVersion(
            source=row.source,
            version=row.version,
            content_hash=row.content_hash,
            embedding_model_name=row.embedding_model_name,
            embedding_model_version=row.embedding_model_version,
            embed_params=row.embed_params or {},
            tenant=row.tenant,
            created_at=(row.created_at.isoformat() if row.created_at else ""),
        )

    def list_all(self, tenant: str | None = None) -> list[ContentVersion]:
        """Retourne la liste des versions (filtrable par tenant)."""
        stmt = select(ContentVersionORM)
        if tenant is None:
            stmt = stmt.where(ContentVersionORM.tenant.is_(None))
        else:
            stmt = stmt.where(ContentVersionORM.tenant == tenant)
        rows = self._session.execute(stmt).scalars().all()
        return [
            ContentVersion(
                source=r.source,
                version=r.version,
                content_hash=r.content_hash,
                embedding_model_name=r.embedding_model_name,
                embedding_model_version=r.embedding_model_version,
                embed_params=r.embed_params or {},
                tenant=r.tenant,
                created_at=(r.created_at.isoformat() if r.created_at else ""),
            )
            for r in rows
        ]
