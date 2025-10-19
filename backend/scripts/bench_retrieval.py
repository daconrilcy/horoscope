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
import time
from datetime import datetime
from typing import Any

from ..services.retrieval_proxy import RetrievalProxy


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

    # Placeholder de bench minimal (simulé) — à remplacer par réel dataset
    latencies: list[float] = []
    start = time.time()
    for _ in range(min(200, args.docs // 10)):
        t0 = time.time()
        proxy.search(query="test query", top_k=args.topk, tenant="bench")
        latencies.append(time.time() - t0)
    elapsed = time.time() - start

    report: dict[str, Any] = {
        "adapter": args.adapter,
        "docs": args.docs,
        "qps_target": args.qps,
        "topk": args.topk,
        "p50_ms": round(_percentile(latencies, 0.50) * 1000, 2),
        "p95_ms": round(_percentile(latencies, 0.95) * 1000, 2),
        "elapsed_s": round(elapsed, 3),
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
