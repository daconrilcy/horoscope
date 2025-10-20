from __future__ import annotations

from backend.domain.retrieval_types import Query
from backend.domain.retriever import Retriever

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

    def advise(self, chart: dict, today: dict, question: str) -> tuple[str, dict | None]:
        base = f"precision={chart['chart'].get('precision_score', 1)}; eao={today.get('eao')}"
        r = self.retriever.query(Query(text=question, k=6))
        ctx = _ctx(r)
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"{base}\nQuestion: {question}\nContext:\n{ctx}"},
        ]
        out = self.llm.generate(messages)
        # Accept either str or (text, usage) from LLM client
        if isinstance(out, tuple) and len(out) == 2:
            return out[0], out[1]
        return str(out), None
