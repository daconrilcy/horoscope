# ============================================================
# Module : backend/domain/content_version.py
# Objet  : Modèle de gouvernance des contenus/embeddings (POPO).
# ============================================================

from __future__ import annotations


class ContentVersion:
    """Version de contenu et paramètres d'embedding (objet domaine).

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

    def __init__(
        self,
        source: str,
        version: str,
        content_hash: str,
        embedding_model_name: str,
        embedding_model_version: str,
        embed_params: dict,
        tenant: str | None,
        created_at: str,
    ) -> None:
        self.source = source
        self.version = version
        self.content_hash = content_hash
        self.embedding_model_name = embedding_model_name
        self.embedding_model_version = embedding_model_version
        self.embed_params = embed_params
        self.tenant = tenant
        self.created_at = created_at
