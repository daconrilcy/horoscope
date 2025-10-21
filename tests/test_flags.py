from __future__ import annotations

from backend.config import flags as f


def test_shadow_sample_rate_bounds(monkeypatch) -> None:
    monkeypatch.setenv("FF_RETRIEVAL_SHADOW_SAMPLE_RATE", "-1")
    assert f.shadow_sample_rate() == 0.0
    monkeypatch.setenv("FF_RETRIEVAL_SHADOW_SAMPLE_RATE", "2")
    assert f.shadow_sample_rate() == 1.0
    monkeypatch.setenv("FF_RETRIEVAL_SHADOW_SAMPLE_RATE", "0.5")
    assert f.shadow_sample_rate() == 0.5


def test_tenant_allowlist_parse(monkeypatch) -> None:
    monkeypatch.setenv("RETRIEVAL_TENANT_ALLOWLIST", "a, b ,c,, ")
    vals = f.tenant_allowlist()
    assert vals == {"a", "b", "c"}


def test_dual_write_flag(monkeypatch) -> None:
    monkeypatch.delenv("FF_RETRIEVAL_DUAL_WRITE", raising=False)
    monkeypatch.delenv("RETRIEVAL_DUAL_WRITE", raising=False)
    assert f.ff_retrieval_dual_write() is False
    monkeypatch.setenv("FF_RETRIEVAL_DUAL_WRITE", "true")
    assert f.ff_retrieval_dual_write() is True

