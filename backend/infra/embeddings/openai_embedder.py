from __future__ import annotations

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

from backend.core.container import container, resolve_secret
from backend.infra.embeddings.base import Embeddings


class OpenAIEmbedder(Embeddings):
    def __init__(self):
        if OpenAI is None:
            self.client = None
            self.model = None
        else:
            self.client = OpenAI(api_key=resolve_secret("OPENAI_API_KEY") or None)
            self.model = getattr(container.settings, "EMBEDDINGS_MODEL", "text-embedding-3-small")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.client is None:
            # fallback deterministic embedding
            return [[float(len(t)), 1.0] for t in texts]
        resp = self.client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]
