"""
Modèle de gouvernance des contenus et embeddings (POPO).

Ce module définit le modèle de domaine ContentVersion pour gérer les versions de contenu avec leurs
métadonnées d'embedding et paramètres associés.
"""

# ============================================================
# Module : backend/domain/content_version.py
# Objet  : Modèle de gouvernance des contenus/embeddings (POPO).
# ============================================================

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ContentVersion:
    """
    Version de contenu et paramètres d'embedding (objet domaine).

    Attributs
    - source: identifiant de la source.
    - version: version sémantique.
    - content_hash: empreinte du contenu.
    - embedding_model_name: nom du modèle d'embedding.
    - embedding_model_version: version du modèle.
    - embed_params: paramètres d'embedding (dict sérialisable JSON).
    - tenant: identifiant tenant (optionnel).
    - created_at: ISO datetime de création.
    """

    source: str
    version: str
    content_hash: str
    embedding_model_name: str
    embedding_model_version: str
    embed_params: dict
    tenant: str | None
    created_at: str
