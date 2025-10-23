"""
Client LLM basé sur l'API OpenAI avec fallback déterministe.

Implémente l'interface LLM en supportant:
- chat.completions (SDK OpenAI)
- responses (SDK OpenAI plus récent)
- fallback local déterministe (tests/dev)
"""

from __future__ import annotations

from typing import Any, Literal, Optional, Union, overload  # noqa: F401

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - dépendance optionnelle
    OpenAI = None  # type: ignore

from backend.infra.llm.base import LLM


class OpenAILLM(LLM):
    """
    LLM basé sur OpenAI avec fallback.

    Utilise l'API OpenAI si le SDK et la clé API sont disponibles, sinon renvoie une réponse
    déterministe pour les tests.
    """

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini") -> None:
        """Initialize the OpenAILLM client."""
        self.model = model
        if OpenAI is not None and api_key:
            self.client = OpenAI(api_key=api_key)
        else:
            self.client = None  # type: ignore[assignment]

    # ---- Overloads pour coller à l'interface de base ----
    @overload
    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        with_usage: Literal[True],
        **kwargs: Any,
    ) -> tuple[str, dict[str, int]]: ...

    @overload
    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        with_usage: Literal[False] = False,
        **kwargs: Any,
    ) -> str: ...

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        with_usage: bool = False,
        **kwargs: Any,
    ) -> str | tuple[str, dict[str, int]]:
        """
        Génère du texte (et éventuellement les métriques d'usage).

        - with_usage=False (défaut) -> str
        - with_usage=True -> (str, dict[str, int])
        """
        # Pas de client → fallback
        if not self.client:
            text, usage = self._fallback_response(messages)
            return (text, usage) if with_usage else text

        # Tente d'abord chat.completions
        r = self._try_chat_completions(messages, **kwargs)
        if r is None:
            # Puis responses
            r = self._try_responses_api(messages, **kwargs)
        if r is None:
            # Dernier recours
            r = self._fallback_response(messages)

        text, usage = r
        return (text, usage) if with_usage else text

    # -------------------- Helpers internes --------------------

    def _fallback_response(
        self, messages: list[dict[str, str]]
    ) -> tuple[str, dict[str, int]]:
        """Réponse déterministe (utile pour tests), usage vide."""
        last = messages[-1]["content"] if messages else ""
        return f"FAKE_OPENAI: {last[:80]}".strip(), {}

    def _try_chat_completions(
        self, messages: list[dict[str, str]], **kwargs: Any
    ) -> tuple[str, dict[str, int]] | None:
        """Tente d'utiliser l'API chat.completions."""
        try:
            resp = self.client.chat.completions.create(  # type: ignore[union-attr]
                model=self.model,
                messages=messages,
                **kwargs,
            )
            choice = resp.choices[0]
            content = getattr(getattr(choice, "message", None), "content", None)
            if content:
                usage = self._extract_usage_dict(resp)
                return str(content), usage
        except Exception:
            pass
        return None

    def _try_responses_api(
        self, messages: list[dict[str, str]], **kwargs: Any
    ) -> tuple[str, dict[str, int]] | None:
        """Tente d'utiliser l'API responses."""
        try:
            resp = self.client.responses.create(  # type: ignore[union-attr]
                model=self.model,
                input=messages,
                **kwargs,
            )
            content = getattr(resp, "output_text", None)
            if content:
                usage = self._extract_usage_dict(resp)
                return str(content), usage
        except Exception:
            pass
        return None

    def _extract_usage_dict(self, resp: Any) -> dict[str, int]:
        """
        Extrait les infos d'usage depuis la réponse OpenAI.

        Toujours un dict.
        """
        try:
            usage = getattr(resp, "usage", None)
            # Certains SDK imbriquent l'attribut
            if usage and hasattr(usage, "usage"):
                usage = usage.usage
            if usage:
                return {
                    "prompt_tokens": int(getattr(usage, "prompt_tokens", 0)),
                    "completion_tokens": int(getattr(usage, "completion_tokens", 0)),
                    "total_tokens": int(getattr(usage, "total_tokens", 0)),
                }
        except Exception:
            pass
        return {}
