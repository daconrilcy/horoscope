from __future__ import annotations

from backend.infra.embeddings.base import Embeddings
from backend.infra.llm.base import LLM


class FakeEmbeddings(Embeddings):
    def embed(self, texts: list[str]) -> list[list[float]]:
        # simple length-based vector for determinism
        return [[float(len(t)), 1.0] for t in texts]


class FakeLLM(LLM):
    def generate(self, messages: list[dict[str, str]], **kwargs) -> str:
        return "FAKE_ADVICE_OK"
