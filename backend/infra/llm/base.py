"""
Interface de base pour les modèles de langage.

Ce module définit l'interface abstraite que doivent implémenter tous les clients de modèles de
langage.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLM(ABC):
    """Interface abstraite pour les modèles de langage."""

    @abstractmethod
    def generate(self, messages: list[dict[str, str]], **kwargs) -> str:
        """Génère une réponse à partir d'une liste de messages."""
        ...
