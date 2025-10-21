from __future__ import annotations

import json
import random


def faiss_topk(query: str, k: int) -> list[dict]:
    """Return a simulated FAISS top-k for the demo.

    Replace with the real adapter call in staging if desired.
    """
    random.seed(hash(query) % 10_000)
    res: list[dict] = []
    for i in range(k):
        res.append({"id": f"doc_{random.randint(1, 6000):04d}", "score": 1.0 - i * 0.01})
    return res


def main() -> None:
    """Generate a demo truth-set with frozen baseline_topk."""
    queries: list[dict] = [
        {"query_id": "q001", "query": "compatibilité signe solaire et ascendant", "k": 10},
        {"query_id": "q002", "query": "calcul de thème astral natal", "k": 10},
        {"query_id": "q003", "query": "synastrie compatibilités couple", "k": 10},
        {"query_id": "q004", "query": "transits planétaires du mois", "k": 10},
        {"query_id": "q005", "query": "maisons astrologiques explications", "k": 10},
    ]
    items: list[dict] = []
    for q in queries:
        topk = faiss_topk(q["query"], q["k"])
        items.append(
            {
                "query_id": q["query_id"],
                "query": q["query"],
                "k": q["k"],
                "baseline_topk": [d["id"] for d in topk],
                "relevant_ids": [],
            }
        )
    with open("docs/examples/truthset.sample.json", "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()

