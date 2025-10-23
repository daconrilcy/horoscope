"""Interface de base pour les magasins vectoriels.

Ce module définit l'interface abstraite que doivent implémenter tous les magasins vectoriels pour la
recherche de documents.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from backend.domain.retrieval_types import Document, Query, ScoredDocument


class VectorStore(ABC):
    """Interface abstraite pour les magasins vectoriels."""

    @abstractmethod
    def index(self, docs: list[Document]) -> int:
        """Indexe une liste de documents et retourne le nombre indexé."""
        raise NotImplementedError

    @abstractmethod
    def search(self, q: Query) -> list[ScoredDocument]:
        """Recherche des documents similaires à une requête."""
        raise NotImplementedError


class VectorStoreProtocol(Protocol):
    """Protocole pour les magasins vectoriels avec support multi-tenant."""

    def index_for_tenant(self, tenant: str, docs: list[Document]) -> int:
        """Indexe des documents pour un tenant spécifique.

        Args:
            tenant: Identifiant du tenant.
            docs: Liste des documents à indexer.

        Returns:
            int: Nombre de documents indexés.
        """

    def search_for_tenant(self, tenant: str, q: Query) -> list[ScoredDocument]:
        """Recherche des documents pour un tenant spécifique.

        Args:
            tenant: Identifiant du tenant.
            q: Requête de recherche.

        Returns:
            list[ScoredDocument]: Liste des documents trouvés avec scores.
        """

    def purge_tenant(self, tenant: str) -> None:
        """Supprime toutes les données d'un tenant.

        Args:
            tenant: Identifiant du tenant à purger.
        """
