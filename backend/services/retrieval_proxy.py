# ============================================================
# Module : backend/services/retrieval_proxy.py
# Objet  : Proxy stateless pour l'accès retrieval/embeddings.
# Contexte : Découple l'app du store (FAISS / Weaviate / etc.).
# Invariants :
#  - Aucune logique d'état persistant ici.
#  - Les adaptateurs implémentent la même interface minimale.
# ============================================================

from __future__ import annotations

import os
from abc import ABC, abstractmethod


class BaseRetrievalAdapter(ABC):
    """Interface minimale pour un store vectoriel.

    Méthodes à implémenter :
      - embed_texts
      - search
    """

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Retourne des embeddings pour une liste de textes.

        Args:
            texts: Liste de textes bruts.
        Returns:
            Liste d'embeddings (liste de flottants par texte).
        Raises:
            ValueError: si texts est vide.
        """
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, top_k: int = 5, tenant: str | None = None) -> list[dict]:
        """Recherche les items les plus proches de la requête.

        Args:
            query: Texte de requête.
            top_k: Nombre de résultats souhaité.
            tenant: Contexte locataire (multi-tenant) éventuel.
        Returns:
            Liste de documents {id, score, metadata}.
        """
        raise NotImplementedError


class FAISSAdapter(BaseRetrievalAdapter):
    """Adaptateur FAISS. Chargement lazy, fallback si indisponible."""

    def __init__(self) -> None:
        # Import local pour éviter ImportError à l'import du module.
        try:
            import faiss  # noqa: F401

            self._faiss_available = True
        except Exception:
            self._faiss_available = False
        self._index = None  # type: Any

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Voir interface. Ici, délégation à un embedder externe (OpenAI/local)."""
        if not texts:
            raise ValueError("texts ne doit pas être vide")
        # TODO: brancher un embedder (OpenAI/local). Placeholder contrôlé :
        return [[0.0, 0.0, 0.0] for _ in texts]

    def search(self, query: str, top_k: int = 5, tenant: str | None = None) -> list[dict]:
        """Recherche FAISS ou fallback in-memory si FAISS indisponible."""
        if not query:
            return []
        # TODO: implémentation réelle. Placeholder contrôlé :
        results = [
            {"id": "doc_1", "score": 0.99, "metadata": {"tenant": tenant or "default"}},
            {"id": "doc_2", "score": 0.95, "metadata": {"tenant": tenant or "default"}},
        ]
        return results[: max(0, top_k)]


class WeaviateAdapter(BaseRetrievalAdapter):
    """Adaptateur Weaviate (squelette)."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            raise ValueError("texts ne doit pas être vide")
        return [[0.0, 0.0, 0.0] for _ in texts]

    def search(self, query: str, top_k: int = 5, tenant: str | None = None) -> list[dict]:
        if not query:
            return []
        return [{"id": "w_doc_1", "score": 0.9, "metadata": {"tenant": tenant or "default"}}]


class PineconeAdapter(BaseRetrievalAdapter):
    """Adaptateur Pinecone (squelette)."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            raise ValueError("texts ne doit pas être vide")
        return [[0.0, 0.0, 0.0] for _ in texts]

    def search(self, query: str, top_k: int = 5, tenant: str | None = None) -> list[dict]:
        if not query:
            return []
        return [{"id": "p_doc_1", "score": 0.9, "metadata": {"tenant": tenant or "default"}}]


class ElasticVectorAdapter(BaseRetrievalAdapter):
    """Adaptateur Elasticsearch v8 (squelette)."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            raise ValueError("texts ne doit pas être vide")
        return [[0.0, 0.0, 0.0] for _ in texts]

    def search(self, query: str, top_k: int = 5, tenant: str | None = None) -> list[dict]:
        if not query:
            return []
        return [{"id": "e_doc_1", "score": 0.9, "metadata": {"tenant": tenant or "default"}}]


class RetrievalProxy:
    """Proxy stateless exposant `embed_texts` et `search`.

    Sélectionne dynamiquement l'adaptateur via variable d'environnement
    RETRIEVAL_BACKEND in {"faiss", "weaviate", "pinecone", "elastic"}.
    """

    def __init__(self) -> None:
        backend = (os.getenv("RETRIEVAL_BACKEND") or "faiss").lower()
        if backend == "weaviate":
            self._adapter: BaseRetrievalAdapter = WeaviateAdapter()
        elif backend == "pinecone":
            self._adapter = PineconeAdapter()
        elif backend == "elastic":
            self._adapter = ElasticVectorAdapter()
        else:
            self._adapter = FAISSAdapter()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Délègue à l'adaptateur courant.

        Args:
            texts: Liste des textes à encoder.
        Returns:
            Vecteurs d'embeddings.
        """
        return self._adapter.embed_texts(texts)

    def search(self, query: str, top_k: int = 5, tenant: str | None = None) -> list[dict]:
        """Délègue à l'adaptateur courant.

        Args:
            query: Requête textuelle.
            top_k: Nombre maximum de résultats.
            tenant: Identifiant tenant (multi-tenant).
        Returns:
            Résultats triés par score décroissant.
        """
        return self._adapter.search(query=query, top_k=top_k, tenant=tenant)
