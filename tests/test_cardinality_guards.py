"""
Tests pour les gardes de cardinalité des labels.

Ce module teste que les labels de tenants et modèles sont projetés vers 'unknown' quand ils sont
hors de la whitelist.

Cardinality guard tests for label whitelists.

Ensures tenant/model labels are projected to 'unknown' when outside whitelist.
"""

from __future__ import annotations

from backend.app.metrics import labelize_model, labelize_tenant


def test_labelize_tenant_whitelist(monkeypatch) -> None:
    """Teste que les labels de tenant sont filtrés selon la whitelist."""
    allowed = ["t1", "t2", "default"]
    assert labelize_tenant("t1", allowed) == "t1"
    assert labelize_tenant("nope", allowed) == "unknown"
    assert labelize_tenant("", allowed) == "unknown"


def test_labelize_model_whitelist(monkeypatch) -> None:
    """Teste que les labels de modèle sont filtrés selon la whitelist."""
    allowed = ["gpt-4o-mini", "claude-3-haiku"]
    assert labelize_model("gpt-4o-mini", allowed) == "gpt-4o-mini"
    assert labelize_model("other", allowed) == "unknown"
