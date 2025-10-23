"""Embedder local utilisant Sentence Transformers.

Ce module implémente un embedder local utilisant Sentence Transformers avec fallback déterministe
pour les environnements sans dépendances.
"""

from __future__ import annotations

import os

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    SentenceTransformer = None  # type: ignore

from backend.infra.embeddings.base import Embeddings


class LocalEmbedder(Embeddings):
    """Embedder local utilisant Sentence Transformers.

    Génère des embeddings vectoriels en utilisant Sentence Transformers avec fallback déterministe
    pour les environnements sans dépendances.
    """

    _model = None

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialise l'embedder local avec le modèle spécifié.

        Args:
            model_name: Nom du modèle Sentence Transformers à utiliser.
        """
        # Avoid remote model loads in CI/test by default, or when explicitly disabled.
        offline = (os.getenv("EMBEDDINGS_OFFLINE", "").lower() in {"1", "true", "yes"}) or (
            os.getenv("CI", "").lower() == "true"
        )
        if offline or SentenceTransformer is None:
            # lightweight fallback to avoid heavy deps and network during tests/CI
            self.model = None
        else:
            try:
                if LocalEmbedder._model is None:
                    LocalEmbedder._model = SentenceTransformer(model_name)
                self.model = LocalEmbedder._model
            except Exception:
                # On any load error, fall back to lightweight deterministic embeddings
                self.model = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Génère des embeddings vectoriels pour une liste de textes.

        Args:
            texts: Liste des textes à convertir en embeddings.

        Returns:
            list[list[float]]: Liste des vecteurs d'embedding.
        """
        if self.model is None:
            return [[float(len(t)), 1.0] for t in texts]
        return self.model.encode(texts, convert_to_numpy=True).tolist()
