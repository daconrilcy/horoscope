"""Script de benchmark pour les performances de récupération.

Ce script mesure les performances (P50/P95/QPS/RAM) et l'agreement@k entre différents backends de
récupération pour évaluer les performances.
"""

# ============================================================
# Script : backend/scripts/bench_retrieval.py
# Objet  : Bench P50/P95/QPS/RAM et agreement@k entre backends.
# Usage  : python backend/scripts/bench_retrieval.py --adapter faiss --docs 10000 --qps 50 --topk 5
# Sortie : artifacts/bench/<DATE>_<ADAPTER>.json
# ============================================================

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

try:  # optional RAM metrics
    import psutil  # type: ignore
except Exception:  # pragma: no cover - optional dependency in CI
    psutil = None  # type: ignore

# Allow running as a standalone script (python backend/scripts/bench_retrieval.py)
SYS_ROOT = Path(__file__).resolve().parents[2]
if str(SYS_ROOT) not in sys.path:
    sys.path.append(str(SYS_ROOT))

from backend.domain.retrieval_types import Document, Query  # noqa: E402
from backend.domain.retriever import Retriever  # noqa: E402
from backend.services.retrieval_proxy import RetrievalProxy  # noqa: E402


def _percentile(values: list[float], p: float) -> float:
    """Compute a simple percentile (p in [0, 1])."""
    if not values:
        return 0.0
    values_sorted = sorted(values)
    idx = min(int(len(values_sorted) * p), len(values_sorted) - 1)
    return values_sorted[idx]


def main() -> None:
    """Point d'entrée du bench (squelette)."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", type=str, default="faiss")
    parser.add_argument("--docs", type=int, default=10000)
    parser.add_argument("--qps", type=int, default=50)
    parser.add_argument("--topk", type=int, default=5)
    args = parser.parse_args()

    os.environ["RETRIEVAL_BACKEND"] = args.adapter.lower()
    proxy = RetrievalProxy()

    # Dataset synthétique 10k fiches courtes
    total_docs = int(args.docs)
    docs: list[Document] = [
        Document(
            id=f"doc_{i}",
            text=f"Topic {i % 50}: sample note about stars and signs #{i}",
        )
        for i in range(total_docs)
    ]

    retriever: Retriever | None = None
    if args.adapter.lower() == "faiss":
        # Indexer localement via FAISS (embeddings cohérents via embedder du store)
        retriever = Retriever()
        retriever.index(docs)

    # Placeholder de bench minimal (simulé) — à remplacer par réel dataset
    latencies: list[float] = []
    start = time.time()
    queries = [
        "how to read zodiac?",
        "sign traits for aries",
        "compatibility leo and libra",
        "daily horoscope tips",
        "constellation facts",
    ]
    n_iters = max(50, min(500, total_docs // 20))
    for i in range(n_iters):
        t0 = time.time()
        qtext = queries[i % len(queries)]
        if retriever is not None:
            _ = retriever.query(Query(text=qtext, k=args.topk))
        else:
            proxy.search(query=qtext, top_k=args.topk, tenant="bench")
        latencies.append(time.time() - t0)
    elapsed = time.time() - start

    # Compute process RAM if psutil is available
    ram_mb = None
    if psutil is not None:
        try:
            ram_mb = round(psutil.Process().memory_info().rss / (1024 * 1024), 1)
        except Exception:  # pragma: no cover - defensive
            ram_mb = None

    # Add git SHA if available
    sha = None
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:  # pragma: no cover - CI safety
        sha = None

    report: dict[str, Any] = {
        "adapter": args.adapter,
        "docs": args.docs,
        "qps_target": args.qps,
        "topk": args.topk,
        "p50_ms": round(_percentile(latencies, 0.50) * 1000, 2),
        "p95_ms": round(_percentile(latencies, 0.95) * 1000, 2),
        "elapsed_s": round(elapsed, 3),
        "qps_observed": round((len(latencies) / elapsed) if elapsed > 0 else 0.0, 2),
        "ram_mb": ram_mb,
        "git_sha": sha,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    outdir = "artifacts/bench"
    os.makedirs(outdir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{args.adapter}.json"
    outfile = os.path.join(outdir, filename)
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Wrote bench report -> {outfile}")


if __name__ == "__main__":
    main()
