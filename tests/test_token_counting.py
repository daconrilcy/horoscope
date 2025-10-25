# Constantes pour éviter les erreurs PLR2004 (Magic values)
EXPECTED_COUNT_3 = 3
EXPECTED_COUNT_4 = 4
TOKEN_COUNT_123 = 123
TOKEN_COUNT_456 = 456
"""Tests for token counting strategies.

Covers API usage, tiktoken path (with fake module), fallback to words, and auto preference for API
over tiktoken.
"""

from __future__ import annotations

import sys
from typing import Any

from backend.api.routes_chat import estimate_tokens


def test_strategy_api_uses_usage_when_available(monkeypatch: Any) -> None:
    """When strategy=api and usage has total_tokens, it is used for metrics."""
    monkeypatch.setenv("TOKEN_COUNT_STRATEGY", "api")

    # Test the estimate_tokens function directly
    text = "hello world"
    model = "gpt-3.5-turbo"
    usage = {"total_tokens": 123}

    result = estimate_tokens(text, model, usage)
    assert result  == TOKEN_COUNT_123


def test_strategy_tiktoken_import_ok(monkeypatch: Any) -> None:
    """When strategy=tiktoken and module is available, use it."""
    monkeypatch.setenv("TOKEN_COUNT_STRATEGY", "tiktoken")

    class _FakeEnc:
        def encode(self, s: str) -> list[int]:  # pragma: no cover - trivial
            return [len(word) for word in s.split()]

    class _FakeTik:
        def encoding_for_model(self, _m: str) -> _FakeEnc:  # type: ignore[override]
            return _FakeEnc()

        def get_encoding(self, _n: str) -> _FakeEnc:  # type: ignore[override]
            return _FakeEnc()

    sys.modules["tiktoken"] = _FakeTik()  # type: ignore[assignment]

    text = "one two three"
    model = "gpt-3.5-turbo"
    usage = None

    result = estimate_tokens(text, model, usage)
    assert result  == EXPECTED_COUNT_3  # 3 words


def test_strategy_tiktoken_import_fail_fallback_words(monkeypatch: Any) -> None:
    """If tiktoken import fails, fallback to words counting."""
    monkeypatch.setenv("TOKEN_COUNT_STRATEGY", "tiktoken")
    if "tiktoken" in sys.modules:
        del sys.modules["tiktoken"]

    text = "four words right here"
    model = "gpt-3.5-turbo"
    usage = None

    result = estimate_tokens(text, model, usage)
    assert result  == EXPECTED_COUNT_4  # 4 words


def test_strategy_auto_prefers_api_over_tiktoken(monkeypatch: Any) -> None:
    """Auto strategy should prefer API usage over tiktoken when usage is present."""
    monkeypatch.setenv("TOKEN_COUNT_STRATEGY", "auto")

    # Even if tiktoken is present, usage should be taken
    class _FakeEnc:
        def encode(self, s: str) -> list[int]:  # pragma: no cover - trivial
            return [len(word) for word in s.split()]

    class _FakeTik:
        def encoding_for_model(self, _m: str) -> _FakeEnc:  # type: ignore[override]
            return _FakeEnc()

        def get_encoding(self, _n: str) -> _FakeEnc:  # type: ignore[override]
            return _FakeEnc()

    sys.modules["tiktoken"] = _FakeTik()  # type: ignore[assignment]

    text = "one two three"
    model = "gpt-3.5-turbo"
    usage = {"total_tokens": 456}

    result = estimate_tokens(text, model, usage)
    assert result  == TOKEN_COUNT_456  # Should use API usage, not tiktoken
