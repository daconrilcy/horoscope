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
    """LLM basé sur OpenAI avec fallback.

    Cette classe tente d'utiliser l'API OpenAI (chat.completions ou responses)
    si le SDK et la clé API sont disponibles. À défaut, elle retourne une
    réponse déterministe utile pour les tests (sans effectuer d'appels réseau).
    """

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini") -> None:
        """Construit le client.

        Paramètres:
        - api_key: Clé API OpenAI. Si absente, utilise le mode fallback.
        - model: Nom du modèle à utiliser (ex.: "gpt-4o-mini").
        """
        self.model = model
        if OpenAI is not None and api_key:
            self.client = OpenAI(api_key=api_key)
        else:
            self.client = None

    def generate(self, messages: list[dict[str, str]], **kwargs):  # returns str | (str, dict)
        """Génère une réponse à partir d'un historique de messages.

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
            # Fallback deterministic output for environments without OpenAI
            last = messages[-1]["content"] if messages else ""
            return f"FAKE_OPENAI: {last[:80]}".strip(), None

        try:
            # Prefer chat.completions API if available
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                **kwargs,
            )
            choice = resp.choices[0]
            content = getattr(getattr(choice, "message", None), "content", None)
            if content:
                usage = getattr(resp, "usage", None)
                usage_dict = None
                if usage:
                    try:
                        usage_dict = {
                            "prompt_tokens": int(getattr(usage, "prompt_tokens", 0)),
                            "completion_tokens": int(getattr(usage, "completion_tokens", 0)),
                            "total_tokens": int(getattr(usage, "total_tokens", 0)),
                        }
                    except Exception:
                        usage_dict = None
                return content, usage_dict
        except Exception:
            # Try the newer responses API as a fallback
            try:
                resp = self.client.responses.create(
                    model=self.model,
                    input=messages,
                    **kwargs,
                )
                # .output_text may exist on newer SDKs
                content = getattr(resp, "output_text", None)
                usage_dict = None
                if content:
                    try:
                        usage = getattr(resp, "usage", None)
                        if usage and hasattr(usage, "usage"):  # new SDKs nest usage
                            usage = usage.usage
                        if usage:
                            usage_dict = {
                                "prompt_tokens": int(getattr(usage, "prompt_tokens", 0)),
                                "completion_tokens": int(getattr(usage, "completion_tokens", 0)),
                                "total_tokens": int(getattr(usage, "total_tokens", 0)),
                            }
                    except Exception:
                        usage_dict = None
                    return str(content), usage_dict
            except Exception:
                pass

        # Last resort fallback
        last = messages[-1]["content"] if messages else ""
        return f"FAKE_OPENAI: {last[:80]}".strip(), None
