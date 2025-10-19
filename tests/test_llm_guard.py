# ============================================================
# Tests : tests/test_llm_guard.py
# Objet  : Cas basiques du middleware LLM Guard.
# ============================================================

from __future__ import annotations

from backend.app.middleware_llm_guard import sanitize_input, validate_output


def test_sanitize_pass():
    payload = {"q": "hello"}
    out = sanitize_input(payload)
    assert out == payload


def test_validate_output_pass():
    out = validate_output("ok", None)
    assert isinstance(out, str)
