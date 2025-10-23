# mypy: ignore-errors
"""
Migration Alembic pour créer la table content_versions.

Cette migration crée la table content_versions qui stocke les métadonnées des versions de contenu
avec leurs embeddings et paramètres associés.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20251019_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Applique la migration pour créer la table content_versions.

    Crée la table content_versions avec tous les champs nécessaires pour stocker les métadonnées des
    versions de contenu.
    """
    op.create_table(
        "content_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("embedding_model_name", sa.String(length=128), nullable=False),
        sa.Column("embedding_model_version", sa.String(length=64), nullable=False),
        sa.Column("embed_params", sa.JSON(), nullable=False),
        sa.Column("tenant", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "source", "version", "tenant", name="uq_source_version_tenant"
        ),
    )


def downgrade() -> None:
    """
    Annule la migration en supprimant la table content_versions.

    Supprime la table content_versions créée par la migration upgrade.
    """
    op.drop_table("content_versions")
