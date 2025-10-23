"""
Interface de base pour les générateurs d'embeddings.

Ce module définit l'interface abstraite que doivent implémenter tous les générateurs d'embeddings
vectoriels.
"""

from abc import ABC, abstractmethod


class Embeddings(ABC):
    """Interface abstraite pour les générateurs d'embeddings."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Génère des embeddings vectoriels pour une liste de textes."""
        ...
