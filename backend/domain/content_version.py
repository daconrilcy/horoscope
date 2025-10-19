# ============================================================
# Module : backend/domain/content_version.py
# Objet  : Modèle de gouvernance des contenus/embeddings (POPO).
# ============================================================

from __future__ import annotations


class ContentVersion:
    """Représente une version de contenu et ses paramètres d'embedding.

    Attributs:
        source: Chemin/identifiant de la source.
        version: Version sémantique.
        hash: Empreinte du contenu (intégrité).
        model: Nom du modèle d'embedding.
        model_version: Version du modèle.
        embed_params: Paramètres d'embedding.
        tenant: Identifiant tenant (facultatif).
        created_at: ISO datetime de création.
    """

    def __init__(
        self,
        source: str,
        version: str,
        hash: str,
        model: str,
        model_version: str,
        embed_params: dict,
        tenant: str | None,
        created_at: str,
    ) -> None:
        self.source = source
        self.version = version
        self.hash = hash
        self.model = model
        self.model_version = model_version
        self.embed_params = embed_params
        self.tenant = tenant
        self.created_at = created_at
