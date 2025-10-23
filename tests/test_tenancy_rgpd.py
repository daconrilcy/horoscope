"""
Tests pour l'isolation multi-tenant et RGPD.

Ce module teste l'isolation des données entre tenants et les fonctionnalités de purge pour la
conformité RGPD.
"""

from __future__ import annotations

from backend.domain.retrieval_types import Document, Query
from backend.infra.vecstores.faiss_store import MultiTenantFAISS


def test_multi_tenant_isolation_and_purge() -> None:
    """Teste l'isolation des données entre tenants et la purge RGPD."""
    store = MultiTenantFAISS()
    # Index docs for two tenants
    store.index_for_tenant(
        "t1", [Document(id="1", text="alpha"), Document(id="2", text="beta")]
    )
    store.index_for_tenant(
        "t2", [Document(id="x", text="gamma"), Document(id="y", text="delta")]
    )

    # Search must be isolated per tenant
    r1 = store.search_for_tenant("t1", Query(text="alpha", k=2))
    r2 = store.search_for_tenant("t2", Query(text="alpha", k=2))
    assert any(s.doc.id == "1" for s in r1)
    assert all(s.doc.id != "1" for s in r2)

    # Purge t1 and ensure no results remain for t1
    store.purge_tenant("t1")
    r1_after = store.search_for_tenant("t1", Query(text="alpha", k=2))
    assert r1_after == []
