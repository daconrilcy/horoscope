"""
Middleware de protection LLM contre les injections et fuites de données.

Ce module implémente des garde-fous pour protéger les interactions LLM : sanitisation des entrées,
détection d'injections de prompts, masquage des données personnelles et validation des sorties.
"""

from __future__ import annotations

import re

from backend.app.metrics import LLM_GUARD_PII_MASKED
from backend.core.settings import get_settings


def sanitize_input(payload: dict) -> dict:
    """
    Sanitize input payload (length, denylist).

    - Trim text fields.
    - Enforce max length via LLM_GUARD_MAX_INPUT_LEN (default 1000).
    - Deny common prompt-injection phrases (EN/FR).
    - If LLM_GUARD_ENABLE=false, only trimming is applied.
    Raises:
        ValueError: on violation (empty, too long, injection detected).
    """
    settings = get_settings()
    data = dict(payload)
    question = str(data.get("question", ""))
    q = question.strip()
    if not q:
        raise ValueError("empty_question")
    if not getattr(settings, "LLM_GUARD_ENABLE", True):
        data["question"] = q
        return data
    max_len = getattr(settings, "LLM_GUARD_MAX_INPUT_LEN", 1000)
    try:
        max_len = int(max_len)
    except Exception:  # pragma: no cover - defensive
        max_len = 1000
    if len(q) > max_len:
        raise ValueError("question_too_long")
    patterns = [
        r"ignore\s+previous\s+instructions",
        r"system\s+prompt",
        r"jailbreak",
        r"do\s+anything\s+now",
        # FR variants (accented/unaccented)
        r"ignore\s+les\s+instructions\s+pr[ée]c[ée]dentes",
        r"ignorer\s+les\s+instructions\s+pr[ée]c[ée]dentes",
    ]
    for pat in patterns:
        if re.search(pat, q, flags=re.IGNORECASE):
            raise ValueError("prompt_injection_detected")
    data["question"] = q
    return data


def enforce_policies(context: dict) -> dict:
    """Apply simple policies (placeholder)."""
    return dict(context)


def validate_output(text: str, tenant: str | None) -> str:
    """
    Validate and filter output (mask PII and leaks).

    - Mask emails and simple phone numbers (count masks via metrics).
    - If LLM_GUARD_ENABLE=false, return the text unchanged.
    """
    settings = get_settings()
    if not getattr(settings, "LLM_GUARD_ENABLE", True):
        return text
    masked = text
    # Emails
    new = re.sub(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[redacted-email]", masked
    )
    if new != masked:
        LLM_GUARD_PII_MASKED.labels("email").inc()
    masked = new
    # Phones (very simple): sequences of 8+ digits (with separators)
    new = re.sub(r"\+?\d[\d\s\-]{7,}\d", "[redacted-phone]", masked)
    if new != masked:
        LLM_GUARD_PII_MASKED.labels("phone").inc()
    masked = new
    return masked
