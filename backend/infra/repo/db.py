"""DB utilities for SQLAlchemy sessions/engine.

Uses `DATABASE_URL` env var or falls back to `sqlite+pysqlite:///:memory:` for tests.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def get_engine(url: str | None = None) -> Engine:
    """Crée un moteur SQLAlchemy à partir de l'URL de base de données."""
    db_url = url or os.getenv("DATABASE_URL") or "sqlite+pysqlite:///:memory:"
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(db_url, future=True, echo=False, connect_args=connect_args)


def get_session_factory(engine: Engine) -> sessionmaker:
    """Crée une factory de sessions SQLAlchemy."""
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """Contexte de session SQLAlchemy avec gestion automatique des transactions.

    Cette fonction fournit un contexte de session SQLAlchemy avec gestion automatique des
    transactions. Elle est utilisée pour exécuter les requêtes SQL de manière transparente et
    sécurisée.
    """
    SessionLocal = get_session_factory(engine)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
