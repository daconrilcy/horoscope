from __future__ import annotations

import os

from backend.domain.retrieval_types import Document, Query
from backend.infra.vecstores.memory_adapter import MemoryMultiTenantAdapter
from backend.services.retrieval_proxy import FAISSAdapter


def test_memory_adapter_isolation_and_purge() -> None:
    a = MemoryMultiTenantAdapter()
    a.index_for_tenant("t1", [Document(id="1", text="hello")])
    a.index_for_tenant("t2", [Document(id="2", text="world")])
    r1 = a.search_for_tenant("t1", Query(text="hello", k=1))
    r2 = a.search_for_tenant("t2", Query(text="hello", k=1))
    assert r1 and r1[0].doc.id == "1"
    assert not r2
    a.purge_tenant("t1")
    assert a.search_for_tenant("t1", Query(text="hello", k=1)) == []


def test_factory_backend_env_memory(monkeypatch) -> None:
    monkeypatch.setenv("VECSTORE_BACKEND", "memory")
    fa = FAISSAdapter()
    res = fa.search("hello", top_k=1, tenant="tZ")
    assert isinstance(res, list)
    assert len(res) == 1

