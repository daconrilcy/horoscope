"""
Tests pour les cas limites des métriques de récupération.

Ce module teste les cas limites et les cas particuliers des métriques de récupération (accord et
NDCG).
"""

from __future__ import annotations

from backend.core.constants import (
    TEST_METRICS_NDCG_DISJOINT,
    TEST_METRICS_NDCG_MAX,
    TEST_METRICS_NDCG_MIN,
    TUPLE_LENGTH,
)
from backend.services.retrieval_proxy import agreement_at_k, ndcg_at_10


def _make(ids: list[str]) -> list[dict]:
    """Crée une liste de documents factices avec des IDs donnés."""
    return [{"id": i, "score": 1.0} for i in ids]


def test_agreement_k_empty() -> None:
    """Teste que l'accord avec des listes vides retourne 0."""
    assert agreement_at_k([], [], k=5) == 0.0


def test_agreement_k_partial_overlap() -> None:
    """Teste l'accord avec un chevauchement partiel."""
    p = _make(["a", "b", "c", "d", "e"])
    s = _make(["x", "b", "y", "d", "z"])
    assert agreement_at_k(p, s, k=5) == TUPLE_LENGTH / 5


def test_agreement_k_k_gt_len() -> None:
    """Teste l'accord quand k est plus grand que la taille des listes."""
    p = _make(["a", "b"])  # size 2
    s = _make(["a", "b"])  # perfect overlap
    assert agreement_at_k(p, s, k=5) == 1.0


def test_ndcg_no_overlap() -> None:
    """Teste NDCG avec aucun chevauchement."""
    p = _make(["a", "b", "c", "d", "e"])
    s = _make(["x", "y", "z"])  # disjoint
    v = ndcg_at_10(p, s)
    assert 0.0 <= v <= TEST_METRICS_NDCG_DISJOINT


def test_ndcg_full_overlap_reordered() -> None:
    """Teste NDCG avec chevauchement complet mais ordre inversé."""
    p = _make(["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"])
    s = _make(["j", "i", "h", "g", "f", "e", "d", "c", "b", "a"])  # reversed
    v = ndcg_at_10(p, s)
    assert TEST_METRICS_NDCG_MIN <= v <= TEST_METRICS_NDCG_MAX


def test_ndcg_clamp_and_dupes() -> None:
    """Teste NDCG avec doublons et valeurs clampées."""
    p = _make(["a", "a", "b", "b", "c"])  # duplicates
    s = _make(["a", "x", "a", "y", "b"])  # duplicates
    v = ndcg_at_10(p, s)
    assert 0.0 <= v <= 1.0
