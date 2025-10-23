"""
Tests pour les métriques de migration.

Ce module teste les métriques utilisées pour évaluer la qualité de la migration de récupération.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.core.constants import (
    TUPLE_LENGTH,
)
from backend.services.metrics_cutover import (
    agreement_at_k,
    append_ndjson,
    evaluate_from_truth,
    load_truth,
    ndcg_at_10,
)


def test_cutover_agreement_and_ndcg_unit() -> None:
    """Teste les métriques d'accord et NDCG sur des données unitaires."""
    truth_ids = ["a", "b", "c", "d", "e"]
    cand_ids = ["x", "b", "y", "d", "z"]
    a5 = agreement_at_k(truth_ids, cand_ids, k=5)
    n10 = ndcg_at_10(truth_ids, cand_ids)
    assert a5 == TUPLE_LENGTH / 5
    assert 0.0 <= n10 <= 1.0


def test_evaluate_from_truth_with_stub(tmp_path: Path) -> None:
    """Teste l'évaluation à partir d'un fichier de vérité avec un stub."""
    truth = [
        {"query": "q1", "truth_ids": ["a", "b", "c"]},
        {"query": "q2", "truth_ids": ["d", "e", "f"]},
    ]

    def _fetch(q: str, k: int, tenant: str | None) -> list[dict]:  # type: ignore[unused-argument]
        return [
            {"id": "a" if q == "q1" else "x"},
            {"id": "b" if q == "q1" else "y"},
        ]

    scores = evaluate_from_truth(truth, _fetch, k=5)
    assert scores.total == TUPLE_LENGTH
    assert 0.0 <= scores.agreement_at_5 <= 1.0
    assert 0.0 <= scores.ndcg_at_10 <= 1.0


def test_truth_io_and_ndjson(tmp_path: Path) -> None:
    """Teste la lecture/écriture des fichiers de vérité et NDJSON."""
    truth_path = tmp_path / "truth.json"
    with open(truth_path, "w", encoding="utf-8") as f:
        json.dump([{"query": "q", "truth_ids": ["a"]}], f)

    data = load_truth(str(truth_path))
    assert isinstance(data, list) and len(data) == 1

    ndjson_path = tmp_path / "log.ndjson"
    append_ndjson(str(ndjson_path), {"ok": True})
    assert ndjson_path.exists()
    content = ndjson_path.read_text(encoding="utf-8").strip()
    assert content.endswith("}")


def test_edge_empty_and_parent_dir_creation(tmp_path: Path) -> None:
    """Teste les cas limites : fichiers manquants et création de répertoires parents."""
    # load_truth on missing file
    missing = tmp_path / "does_not_exist.json"
    assert load_truth(str(missing)) == []

    # append_ndjson should create parent dirs
    target = tmp_path / "sub" / "logs.ndjson"
    append_ndjson(target, {"a": 1})
    assert target.exists()

    # evaluate_from_truth empty
    scores = evaluate_from_truth([], lambda q, k, t: [])
    assert (
        scores.total == 0 and scores.agreement_at_5 == 0.0 and scores.ndcg_at_10 == 0.0
    )


def test_agreement_and_ndcg_bounds() -> None:
    """Teste les bornes des métriques d'accord et NDCG."""
    # agreement with k larger than lists
    assert agreement_at_k(["a"], ["a", "a"], k=5) == 1.0
    # ndcg with empty candidates
    assert ndcg_at_10(["a"], []) == 0.0
