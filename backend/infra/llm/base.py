"""Interface de base pour les modèles de langage."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal, overload


class LLM(ABC):
    """Interface abstraite pour les modèles de langage."""

    # Cas le plus spécifique : with_usage=True -> retourne (str, dict)
    @overload
    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        with_usage: Literal[True],
        **kwargs: Any,
    ) -> tuple[str, dict[str, int]]: ...

    # Cas par défaut / False : retourne str
    @overload
    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        with_usage: Literal[False] = False,
        **kwargs: Any,
    ) -> str: ...

    @abstractmethod
    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        with_usage: bool = False,
        **kwargs: Any,
    ) -> str | tuple[str, dict[str, int]]:
        """Génère une réponse à partir d'une liste de messages."""
        ...
