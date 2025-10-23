"""
Embedder OpenAI pour la génération d'embeddings.

Ce module implémente un embedder utilisant l'API OpenAI pour générer des embeddings vectoriels avec
fallback déterministe.
"""

from __future__ import annotations

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

from backend.core.container import container, resolve_secret
from backend.infra.embeddings.base import Embeddings


class OpenAIEmbedder(Embeddings):
    """
    Embedder OpenAI pour la génération d'embeddings.

    Utilise l'API OpenAI pour générer des embeddings vectoriels avec fallback déterministe en cas
    d'indisponibilité.
    """

    def __init__(self):
        """
        Initialise l'embedder OpenAI avec la clé API.

        Configure le client OpenAI et le modèle d'embedding à partir des paramètres de
        configuration.
        """
        if OpenAI is None:
            self.client = None
            self.model = None
        else:
            self.client = OpenAI(api_key=resolve_secret("OPENAI_API_KEY") or None)
            self.model = getattr(
                container.settings, "EMBEDDINGS_MODEL", "text-embedding-3-small"
            )

    def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Génère des embeddings vectoriels via l'API OpenAI.

        Args:
            texts: Liste des textes à convertir en embeddings.

        Returns:
            list[list[float]]: Liste des vecteurs d'embedding.
        """
        if self.client is None:
            # fallback deterministic embedding
            return [[float(len(t)), 1.0] for t in texts]
        resp = self.client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]
