"""SQLAlchemy models for persistence layer (ContentVersion)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Classe de base pour tous les modèles SQLAlchemy."""

    metadata = MetaData()


class ContentVersionORM(Base):
    """Modèle ORM pour les versions de contenu."""

    __tablename__ = "content_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(255), nullable=False)
    version = Column(String(64), nullable=False)
    content_hash = Column(String(128), nullable=False)
    embedding_model_name = Column(String(128), nullable=False)
    embedding_model_version = Column(String(64), nullable=False)
    embed_params = Column(JSON, nullable=False, default=dict)
    tenant = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now(UTC))

    __table_args__ = (
        UniqueConstraint("source", "version", "tenant", name="uq_source_version_tenant"),
    )
