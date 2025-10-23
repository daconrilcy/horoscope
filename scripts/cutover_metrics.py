"""
Script d'évaluation des métriques de cutover.

Ce script évalue les métriques de cutover (agreement@5 et nDCG@10) en utilisant un jeu de données de
vérité et génère des rapports JSON et NDJSON.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Allow running standalone
SYS_ROOT = Path(__file__).resolve().parents[2]
if str(SYS_ROOT) not in sys.path:
    sys.path.append(str(SYS_ROOT))

from backend.services.metrics_cutover import (  # noqa: E402
    CutoverScores,
    append_ndjson,
    evaluate_from_truth,
    load_truth,
)
from backend.services.retrieval_proxy import RetrievalProxy  # noqa: E402


def _fetch(
    proxy: RetrievalProxy, query: str, top_k: int, tenant: str | None
) -> list[dict]:
    return proxy.search(query=query, top_k=top_k, tenant=tenant)


def main() -> int:
    """
    Run cutover evaluation and emit a JSON + NDJSON log.

    Exits 0 if thresholds are met, 1 otherwise.
    """
    parser = argparse.ArgumentParser(
        description="Cutover gates: agreement@5 & nDCG@10 evaluator"
    )
    parser.add_argument(
        "--truth-set", type=str, required=True, help="Path to frozen truth set JSON"
    )
    parser.add_argument(
        "--k", type=int, default=10, help="Top-k to request from retrieval"
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output JSON path (default: artifacts/cutover_YYYYMMDD-HH.json)",
    )
    parser.add_argument("--min-agreement", type=float, default=0.95)
    parser.add_argument("--min-ndcg", type=float, default=0.90)
    parser.add_argument(
        "--log",
        type=str,
        default="artifacts/cutover_log.ndjson",
        help="NDJSON log file to append",
    )
    args = parser.parse_args()

    truth = load_truth(args.truth_set)
    proxy = RetrievalProxy()
    scores: CutoverScores = evaluate_from_truth(
        truth, lambda q, k, t: _fetch(proxy, q, k, t), k=args.k
    )

    now = datetime.utcnow()
    outdir = Path("artifacts")
    outdir.mkdir(parents=True, exist_ok=True)
    out_path = (
        Path(args.out)
        if args.out is not None
        else outdir / f"cutover_{now.strftime('%Y%m%d-%H')}.json"
    )
    result = {
        "timestamp": now.isoformat() + "Z",
        "agreement_at_5": round(scores.agreement_at_5, 6),
        "ndcg_at_10": round(scores.ndcg_at_10, 6),
        "total": scores.total,
        "k": int(args.k),
        "min_agreement": float(args.min_agreement),
        "min_ndcg": float(args.min_ndcg),
        "flags": {
            "FF_RETRIEVAL_SHADOW_READ": os.getenv("FF_RETRIEVAL_SHADOW_READ") or "",
            "FF_RETRIEVAL_DUAL_WRITE": os.getenv("FF_RETRIEVAL_DUAL_WRITE") or "",
            "RETRIEVAL_TARGET_BACKEND": os.getenv("RETRIEVAL_TARGET_BACKEND") or "",
        },
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    append_ndjson(args.log, result)

    ok = (scores.agreement_at_5 >= args.min_agreement) and (
        scores.ndcg_at_10 >= args.min_ndcg
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
