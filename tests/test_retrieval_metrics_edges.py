from __future__ import annotations

from backend.services.retrieval_proxy import agreement_at_k, ndcg_at_10


def _make(ids: list[str]) -> list[dict]:
    return [{"id": i, "score": 1.0} for i in ids]


def test_agreement_k_empty() -> None:
    assert agreement_at_k([], [], k=5) == 0.0


def test_agreement_k_partial_overlap() -> None:
    p = _make(["a", "b", "c", "d", "e"])
    s = _make(["x", "b", "y", "d", "z"])
    assert agreement_at_k(p, s, k=5) == 2 / 5


def test_agreement_k_k_gt_len() -> None:
    p = _make(["a", "b"])  # size 2
    s = _make(["a", "b"])  # perfect overlap
    assert agreement_at_k(p, s, k=5) == 1.0


def test_ndcg_no_overlap() -> None:
    p = _make(["a", "b", "c", "d", "e"])
    s = _make(["x", "y", "z"])  # disjoint
    v = ndcg_at_10(p, s)
    assert 0.0 <= v <= 0.05


def test_ndcg_full_overlap_reordered() -> None:
    p = _make(["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"])
    s = _make(["j", "i", "h", "g", "f", "e", "d", "c", "b", "a"])  # reversed
    v = ndcg_at_10(p, s)
    assert 0.7 <= v <= 0.99


def test_ndcg_clamp_and_dupes() -> None:
    p = _make(["a", "a", "b", "b", "c"])  # duplicates
    s = _make(["a", "x", "a", "y", "b"])  # duplicates
    v = ndcg_at_10(p, s)
    assert 0.0 <= v <= 1.0

