# ============================================================
# Tests : tests/test_content_version_repo.py
# Objet  : CRUD ContentVersion via SQLAlchemy (sqlite mémoire).
# ============================================================
"""
Tests pour le repository des versions de contenu.

Ce module teste les opérations CRUD sur les ContentVersion via SQLAlchemy avec une base de données
SQLite en mémoire.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.constants import (
    TUPLE_LENGTH,
)
from backend.domain.content_version import ContentVersion
from backend.infra.repo.content_version_repo import ContentVersionRepo
from backend.infra.repo.models import Base


def _session() -> Session:
    """Crée une session SQLAlchemy avec une base SQLite en mémoire."""
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def test_cv_create_and_get_latest() -> None:
    """Teste la création et la récupération de la dernière version."""
    session = _session()
    repo = ContentVersionRepo(session)
    now = datetime.now(UTC).isoformat()
    cv1 = ContentVersion(
        source="content/a",
        version="v1",
        content_hash="h1",
        embedding_model_name="m",
        embedding_model_version="1",
        embed_params={"dim": 3},
        tenant=None,
        created_at=now,
    )
    repo.create(cv1)
    got = repo.get_latest("content/a", tenant=None)
    assert got is not None and got.version == "v1" and got.content_hash == "h1"


def test_cv_unique_constraint() -> None:
    """Teste que la contrainte d'unicité est respectée."""
    session = _session()
    repo = ContentVersionRepo(session)
    now = datetime.now(UTC).isoformat()
    cv1 = ContentVersion(
        source="content/a",
        version="v1",
        content_hash="h1",
        embedding_model_name="m",
        embedding_model_version="1",
        embed_params={},
        tenant="t1",
        created_at=now,
    )
    repo.create(cv1)
    cv_dup = ContentVersion(
        source="content/a",
        version="v1",
        content_hash="h2",
        embedding_model_name="m",
        embedding_model_version="1",
        embed_params={},
        tenant="t1",
        created_at=now,
    )
    with pytest.raises(IntegrityError):
        repo.create(cv_dup)


def test_cv_list_all_by_tenant() -> None:
    """Teste la liste de toutes les versions par tenant."""
    session = _session()
    repo = ContentVersionRepo(session)
    now = datetime.now(UTC).isoformat()
    for i in range(3):
        repo.create(
            ContentVersion(
                source=f"s{i}",
                version="v1",
                content_hash=f"h{i}",
                embedding_model_name="m",
                embedding_model_version="1",
                embed_params={},
                tenant="tX" if i % 2 == 0 else None,
                created_at=now,
            )
        )
    only_tx = repo.list_all(tenant="tX")
    assert len(only_tx) == TUPLE_LENGTH
    only_none = repo.list_all(tenant=None)
    assert len(only_none) == 1
