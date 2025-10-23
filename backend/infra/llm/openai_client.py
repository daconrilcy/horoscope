"""
Client LLM basé sur l'API OpenAI avec fallback déterministe.

Ce module fournit une implémentation robuste de l'interface LLM utilisant le SDK OpenAI avec gestion
des erreurs et fallback pour les tests.
"""

from __future__ import annotations

"""
Client LLM basé sur l'API OpenAI.

Ce module fournit une implémentation de l'interface `LLM` qui utilise
le SDK OpenAI si disponible, avec un repli déterministe pour les
environnements de développement et de test sans dépendances externes.

Responsabilités:
- Initialiser un client OpenAI optionnel en fonction de la présence d'une clé API.
- Exposer une méthode `generate` robuste, compatible avec plusieurs versions du SDK.
- Fournir un fallback stable quand l'API OpenAI n'est pas accessible.
"""

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

from backend.infra.llm.base import LLM  # noqa: E402


class OpenAILLM(LLM):
    """
    LLM basé sur OpenAI avec fallback.

    Cette classe tente d'utiliser l'API OpenAI (chat.completions ou responses) si le SDK et la clé
    API sont disponibles. À défaut, elle retourne une réponse déterministe utile pour les tests
    (sans effectuer d'appels réseau).
    """

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini") -> None:
        """
        Construit le client.

        Paramètres:
        - api_key: Clé API OpenAI. Si absente, utilise le mode fallback.
        - model: Nom du modèle à utiliser (ex.: "gpt-4o-mini").
        """
        self.model = model
        if OpenAI is not None and api_key:
            self.client = OpenAI(api_key=api_key)
        else:
            self.client = None

    def generate(
        self, messages: list[dict[str, str]], **kwargs
    ):  # returns str | (str, dict)
        """
        Génère une réponse à partir d'un historique de messages.

        Paramètres:
        - messages: Liste de messages de type chat [{"role", "content"}].
        - **kwargs: Arguments transmis au client OpenAI (ex.: temperature).

        Retour:
        - str: Contenu textuel de la meilleure complétion.

        Comportement:
        - Si le client OpenAI est indisponible, renvoie un texte de fallback.
        - Tente d'abord `chat.completions.create`, puis `responses.create`.
        """
        if not self.client:
            return self._fallback_response(messages)

        # Try chat.completions API first
        result = self._try_chat_completions(messages, **kwargs)
        if result is not None:
            return result

        # Try responses API as fallback
        result = self._try_responses_api(messages, **kwargs)
        if result is not None:
            return result

        # Last resort fallback
        return self._fallback_response(messages)

    def _fallback_response(self, messages: list[dict[str, str]]) -> tuple[str, None]:
        """Retourne une réponse de fallback déterministe."""
        last = messages[-1]["content"] if messages else ""
        return f"FAKE_OPENAI: {last[:80]}".strip(), None

    def _try_chat_completions(
        self, messages: list[dict[str, str]], **kwargs
    ) -> tuple[str, dict] | None:
        """Tente d'utiliser l'API chat.completions."""
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                **kwargs,
            )
            choice = resp.choices[0]
            content = getattr(getattr(choice, "message", None), "content", None)
            if content:
                usage_dict = self._extract_usage_dict(resp)
                return content, usage_dict
        except Exception:
            pass
        return None

    def _try_responses_api(
        self, messages: list[dict[str, str]], **kwargs
    ) -> tuple[str, dict] | None:
        """Tente d'utiliser l'API responses."""
        try:
            resp = self.client.responses.create(
                model=self.model,
                input=messages,
                **kwargs,
            )
            content = getattr(resp, "output_text", None)
            if content:
                usage_dict = self._extract_usage_dict(resp)
                return str(content), usage_dict
        except Exception:
            pass
        return None

    def _extract_usage_dict(self, resp) -> dict | None:
        """Extrait les informations d'usage d'une réponse OpenAI."""
        try:
            usage = getattr(resp, "usage", None)
            if usage and hasattr(usage, "usage"):  # new SDKs nest usage
                usage = usage.usage
            if usage:
                return {
                    "prompt_tokens": int(getattr(usage, "prompt_tokens", 0)),
                    "completion_tokens": int(getattr(usage, "completion_tokens", 0)),
                    "total_tokens": int(getattr(usage, "total_tokens", 0)),
                }
        except Exception:
            pass
        return None
