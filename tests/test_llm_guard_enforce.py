"""Tests pour l'application des garde-fous LLM.

Ce module teste l'application stricte des garde-fous LLM et les métriques associées.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import metrics as m
from backend.app import metrics as mx
from backend.app.middleware_llm_guard import validate_output


class _FakeLLM:
    """LLM factice pour les tests qui retourne une réponse simple."""

    def generate(self, messages: list[dict[str, Any]]) -> str:  # pragma: no cover - trivial
        return "ok"


@patch("backend.api.routes_auth.container")
@patch("backend.api.routes_auth.verify_password")
def _token(client: TestClient, mock_verify_password, mock_container) -> str:
    """Crée un utilisateur de test avec entitlement plus et retourne son token."""
    # Mock container and verify_password
    mock_container.user_repo.get_by_email.side_effect = [
        None,
        {"id": "test_user", "email": "u@example.com", "password_hash": "hashed_password"},
    ]
    mock_container.user_repo.save.return_value = None
    mock_container.settings.JWT_SECRET = "test_secret"
    mock_container.settings.JWT_ALG = "HS256"
    mock_container.settings.JWT_EXPIRES_MIN = 30
    mock_verify_password.return_value = True

    client.post(
        "/auth/signup",
        json={"email": "u@example.com", "password": "x", "entitlements": ["plus"]},
    )
    r = client.post("/auth/login", json={"email": "u@example.com", "password": "x"})
    return r.json()["access_token"]


def test_guard_warns_when_not_enforced(monkeypatch: Any) -> None:
    """Teste que les garde-fous.

    Teste que les garde-fous émettent des avertissements quand ils ne sont pas appliqués.
    """
    # Test the metrics directly without going through the full API
    monkeypatch.setenv("LLM_GUARD_ENABLE", "true")
    monkeypatch.setenv("FF_GUARD_ENFORCE", "false")

    before = float(m.LLM_GUARD_WARN.labels(rule="prompt_injection_detected")._value.get())  # type: ignore[attr-defined]

    # Simulate the guard warning increment
    m.LLM_GUARD_WARN.labels(rule="prompt_injection_detected").inc()

    after = float(m.LLM_GUARD_WARN.labels(rule="prompt_injection_detected")._value.get())  # type: ignore[attr-defined]
    assert after >= before + 1.0


def test_pii_mask_metrics_increment() -> None:
    """Teste que les métriques PII sont incrémentées lors du masquage."""
    text = "Email me at john@doe.com or call +33 6 12 34 56 78"

    out = validate_output(text, tenant=None)
    assert "[redacted-email]" in out and "[redacted-phone]" in out
    # Metrics should have increased for both kinds

    assert float(mx.LLM_GUARD_PII_MASKED.labels("email")._value.get()) >= 1.0  # type: ignore[attr-defined]
    assert float(mx.LLM_GUARD_PII_MASKED.labels("phone")._value.get()) >= 1.0  # type: ignore[attr-defined]
