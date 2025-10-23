"""
Fakes et mocks pour les tests unitaires.

Ce module fournit des implémentations factices des interfaces Embeddings et LLM pour les tests
unitaires avec comportement déterministe.
"""

from __future__ import annotations

from backend.infra.embeddings.base import Embeddings
from backend.infra.llm.base import LLM


class FakeEmbeddings(Embeddings):
    """
    Implémentation factice d'Embeddings pour les tests.

    Génère des embeddings déterministes basés sur la longueur du texte pour faciliter les tests
    unitaires.
    """

    def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Génère des embeddings factices basés sur la longueur.

        Args:
            texts: Liste des textes à convertir en embeddings.

        Returns:
            list[list[float]]: Liste des vecteurs d'embedding factices.
        """
        # simple length-based vector for determinism
        return [[float(len(t)), 1.0] for t in texts]


class FakeLLM(LLM):
    """
    Implémentation factice de LLM pour les tests.

    Retourne toujours la même réponse prédéfinie pour faciliter les tests unitaires sans dépendances
    externes.
    """

    def generate(self, messages: list[dict[str, str]], **kwargs) -> str:
        """
        Génère une réponse factice prédéfinie.

        Args:
            messages: Liste des messages de conversation (ignorés).
            **kwargs: Arguments supplémentaires (ignorés).

        Returns:
            str: Réponse factice constante.
        """
        return "FAKE_ADVICE_OK"
