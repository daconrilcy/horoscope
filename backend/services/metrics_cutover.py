"""Métriques de cutover pour l'évaluation des systèmes de récupération.

Ce module implémente les métriques d'évaluation (agreement@k, nDCG@10) pour comparer les
performances des systèmes de récupération lors des cutovers.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _uniq_ids(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for i in ids:
        if i in seen:
            continue
        seen.add(i)
        out.append(i)
    return out


def agreement_at_k(truth_ids: list[str], cand_ids: list[str], k: int = 5) -> float:
    """Compute agreement@k between truth and candidate IDs.

    Returns a value in [0, 1]. IDs are deduplicated and we use min(k, len(truth_ids)).
    """
    k = max(1, int(k))
    t = set(_uniq_ids(truth_ids)[:k])
    if not t:
        return 0.0
    c = _uniq_ids(cand_ids)[:k]
    inter = sum(1 for x in c if x in t)
    v = inter / float(len(t))
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def ndcg_at_10(truth_ids: list[str], cand_ids: list[str]) -> float:
    """Compute nDCG@10 with binary relevance from truth IDs.

    DCG is computed on the top-10 candidate list with rel=1 if the candidate
    ID is present in `truth_ids`. IDCG is the DCG with all relevant items at
    the top. The final score is clamped to [0, 1].
    """
    truth = set(_uniq_ids(truth_ids))
    cand = _uniq_ids(cand_ids)[:10]
    if not cand:
        return 0.0
    # DCG over candidates
    dcg = 0.0
    rel_count = 0
    for i, rid in enumerate(cand):
        rel = 1.0 if rid in truth else 0.0
        if rel > 0:
            rel_count += 1
        dcg += rel / math.log2(i + 2)
    if rel_count <= 0:
        return 0.0
    # Ideal DCG with all relevant items first (up to 10)
    idcg = 0.0
    for i in range(min(rel_count, 10)):
        idcg += 1.0 / math.log2(i + 2)
    v = dcg / idcg if idcg > 0 else 0.0
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


@dataclass
class CutoverScores:
    """Scores de métriques pour l'évaluation de cutover.

    Contient les métriques d'agreement@5, nDCG@10 et le nombre total de requêtes évaluées pour
    l'analyse de cutover.
    """

    agreement_at_5: float
    ndcg_at_10: float
    total: int


def evaluate_from_truth(truth_entries: list[dict], fetch_func: Any, k: int = 10) -> CutoverScores:
    """Evaluate agreement@5 and nDCG@10 using a truth set plus a fetcher.

    Each truth entry contains at least {"query": str, "truth_ids": list[str]}.
    It may also include {"tenant": str} passed to the fetch function.
    The fetch signature is: (query: str, top_k: int, tenant: str | None)
    and must return a list of result dicts containing an "id" field.
    """
    if not truth_entries:
        return CutoverScores(agreement_at_5=0.0, ndcg_at_10=0.0, total=0)
    agg_a = 0.0
    agg_n = 0.0
    total = 0
    for row in truth_entries:
        q = str(row.get("query") or "").strip()
        if not q:
            continue
        t_ids = [str(x) for x in (row.get("truth_ids") or [])]
        tenant = row.get("tenant")
        cand = fetch_func(q, k, tenant)
        c_ids = [str(d.get("id") or "") for d in cand]
        agg_a += agreement_at_k(t_ids, c_ids, k=5)
        agg_n += ndcg_at_10(t_ids, c_ids)
        total += 1
    if total <= 0:
        return CutoverScores(agreement_at_5=0.0, ndcg_at_10=0.0, total=0)
    return CutoverScores(agreement_at_5=agg_a / total, ndcg_at_10=agg_n / total, total=total)


def load_truth(path: str | Path) -> list[dict]:
    """Charge un jeu de données de vérité depuis un fichier.

    Args:
        path: Chemin vers le fichier de vérité.

    Returns:
        list[dict]: Liste des données de vérité chargées.
    """
    p = Path(path)
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    return []


def append_ndjson(path: str | Path, obj: dict) -> None:
    """Ajoute un objet au fichier NDJSON.

    Args:
        path: Chemin vers le fichier NDJSON.
        obj: Objet à ajouter au fichier.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
