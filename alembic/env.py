"""
Configuration de l'environnement Alembic pour les migrations de base de données.

Ce module configure Alembic pour gérer les migrations de la base de données, en supportant à la fois
les modes offline et online avec une configuration flexible des chemins d'importation.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import create_engine, pool

from alembic import context  # type: ignore[attr-defined]

# Allow importing project modules when running via Alembic CLI
_this = Path(__file__).resolve()
_candidates = [
    _this.parent,  # .../alembic
    _this.parent.parent,  # repo root (expected)
    _this.parent.parent.parent,  # workspace root on GitHub Actions
    Path.cwd(),
]
for p in _candidates:
    s = str(p)
    if s and s not in sys.path:
        sys.path.append(s)

from backend.infra.repo.models import Base  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Exécute les migrations Alembic en mode offline.

    Configure Alembic pour exécuter les migrations sans connexion à la base de données en utilisant
    des bindings littéraux.
    """
    url = os.getenv("DATABASE_URL", "sqlite:///./cv.db")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Exécute les migrations Alembic en mode online.

    Configure Alembic pour exécuter les migrations avec une connexion active à la base de données
    via SQLAlchemy.
    """
    url = os.getenv("DATABASE_URL", "sqlite:///./cv.db")
    connectable = create_engine(url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
