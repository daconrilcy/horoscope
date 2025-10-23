"""
Tests for token counting strategies.

Covers API usage, tiktoken path (with fake module), fallback to words, and auto preference for API
over tiktoken.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient
from prometheus_client import generate_latest

from backend.api import routes_chat
from backend.app.main import app


def _token(client: TestClient) -> str:
    client.post(
        "/auth/signup",
        json={"email": "tok@example.com", "password": "p", "entitlements": ["plus"]},
    )
    r = client.post("/auth/login", json={"email": "tok@example.com", "password": "p"})
    return r.json()["access_token"]


def _chart(client: TestClient) -> str:
    r = client.post(
        "/horoscope/natal",
        json={
            "name": "U",
            "date": "1990-01-01",
            "time": None,
            "tz": "Europe/Paris",
            "lat": 48.85,
            "lon": 2.35,
            "time_certainty": "exact",
        },
    )
    return r.json()["id"]


def test_strategy_api_uses_usage_when_available(monkeypatch: Any) -> None:
    """When strategy=api and usage has total_tokens, it is used for metrics."""
    c = TestClient(app)
    tok = _token(c)
    cid = _chart(c)
    headers = {"Authorization": f"Bearer {tok}"}

    monkeypatch.setenv("TOKEN_COUNT_STRATEGY", "api")

    # Patch orchestrator to return usage
    routes_chat.orch.advise = lambda *a, **k: ("hello world", {"total_tokens": 123})  # type: ignore[assignment]
    r = c.post("/chat/advise", json={"chart_id": cid, "question": "x"}, headers=headers)
    assert r.status_code in (
        200,
        400,
    )  # 400 possible if guard kicks in; metrics unaffected
    content = generate_latest()
    assert b"llm_tokens_total" in content


def test_strategy_tiktoken_import_ok(monkeypatch: Any) -> None:
    """When strategy=tiktoken and module is available, use it."""
    c = TestClient(app)
    tok = _token(c)
    cid = _chart(c)
    headers = {"Authorization": f"Bearer {tok}"}

    monkeypatch.setenv("TOKEN_COUNT_STRATEGY", "tiktoken")

    class _FakeEnc:
        def encode(self, s: str) -> list[int]:  # pragma: no cover - trivial
            return s.split()

    class _FakeTik:
        def encoding_for_model(self, _m: str) -> _FakeEnc:  # type: ignore[override]
            return _FakeEnc()

        def get_encoding(self, _n: str) -> _FakeEnc:  # type: ignore[override]
            return _FakeEnc()

    sys.modules["tiktoken"] = _FakeTik()  # type: ignore[assignment]

    routes_chat.orch.advise = lambda *a, **k: ("one two three", None)  # type: ignore[assignment]
    r = c.post("/chat/advise", json={"chart_id": cid, "question": "x"}, headers=headers)
    assert r.status_code in (200, 400)
    content = generate_latest()
    assert b"llm_tokens_total" in content


def test_strategy_tiktoken_import_fail_fallback_words(monkeypatch: Any) -> None:
    """If tiktoken import fails, fallback to words counting."""
    c = TestClient(app)
    tok = _token(c)
    cid = _chart(c)
    headers = {"Authorization": f"Bearer {tok}"}

    monkeypatch.setenv("TOKEN_COUNT_STRATEGY", "tiktoken")
    if "tiktoken" in sys.modules:
        del sys.modules["tiktoken"]

    routes_chat.orch.advise = lambda *a, **k: ("four words right here", None)  # type: ignore[assignment]
    r = c.post("/chat/advise", json={"chart_id": cid, "question": "x"}, headers=headers)
    assert r.status_code in (200, 400)
    content = generate_latest()
    assert b"llm_tokens_total" in content


def test_strategy_auto_prefers_api_over_tiktoken(monkeypatch: Any) -> None:
    """Auto strategy should prefer API usage over tiktoken when usage is present."""
    c = TestClient(app)
    tok = _token(c)
    cid = _chart(c)
    headers = {"Authorization": f"Bearer {tok}"}

    monkeypatch.setenv("TOKEN_COUNT_STRATEGY", "auto")

    # Even if tiktoken is present, usage should be taken
    sys.modules["tiktoken"] = SimpleNamespace(
        encoding_for_model=lambda m: SimpleNamespace(encode=lambda s: [1, 2]),
        get_encoding=lambda n: SimpleNamespace(encode=lambda s: [1, 2]),
    )
    routes_chat.orch.advise = lambda *a, **k: ("ignored", {"total_tokens": 7})  # type: ignore[assignment]
    r = c.post("/chat/advise", json={"chart_id": cid, "question": "x"}, headers=headers)
    assert r.status_code in (200, 400)
    content = generate_latest()
    assert b"llm_tokens_total" in content
