from __future__ import annotations

import os
import random

from backend.app.metrics import RETRIEVAL_AGREEMENT_AT_5
from backend.domain.retrieval_types import Query
from backend.domain.retriever import Retriever
from backend.services.retrieval_proxy import RetrievalProxy

SYSTEM = (
    "Tu es un conseiller astrologique. Explique avec clarté, prudence et bienveillance. "
    "Sois concret, évite le jargon. Mentionne la précision si elle est basse."
)


def _ctx(scored_docs) -> str:
    lines: list[str] = []
    for s in scored_docs[:6]:
        lines.append(f"- {s.doc.text}")
    return "\n".join(lines)


class ChatOrchestrator:
    def __init__(self, retriever: Retriever | None = None, llm=None):
        from backend.infra.llm.openai_client import OpenAILLM

        self.retriever = retriever or Retriever()
        self.llm = llm or OpenAILLM()
        # Shadow-read config
        self._shadow_enabled = (os.getenv("RETRIEVAL_SHADOW_READ") or "false").lower() == "true"
        try:
            self._shadow_ratio = float(os.getenv("RETRIEVAL_SHADOW_READ_PCT") or "0.10")
        except Exception:
            self._shadow_ratio = 0.10
        self._shadow_ratio = max(0.0, min(1.0, self._shadow_ratio))
        self._backend = (os.getenv("RETRIEVAL_BACKEND") or "faiss").lower()
        self._shadow_proxy = RetrievalProxy() if self._backend != "faiss" else None

    def advise(self, chart: dict, today: dict, question: str) -> str:
        base = f"precision={chart['chart'].get('precision_score', 1)}; eao={today.get('eao')}"
        r = self.retriever.query(Query(text=question, k=6))
        # Shadow-read: sample a fraction of requests to compare top-5
        should_shadow = (
            self._shadow_enabled
            and self._shadow_proxy is not None
            and random.random() < self._shadow_ratio
        )
        if should_shadow:
            primary_top5 = [s.doc.id for s in r[:5]]
            try:
                shadow = self._shadow_proxy.search(query=question, top_k=5, tenant=None)
                shadow_top5 = [str(x.get("id", "")) for x in shadow[:5]]
                inter = len(set(primary_top5).intersection(set(shadow_top5)))
                RETRIEVAL_AGREEMENT_AT_5.labels(self._backend).set(inter / 5.0)
            except Exception:
                # best-effort: ignorer toute erreur du shadow
                pass
        ctx = _ctx(r)
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"{base}\nQuestion: {question}\nContext:\n{ctx}"},
        ]
        return self.llm.generate(messages)
