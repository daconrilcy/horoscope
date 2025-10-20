# ============================================================
# Module : backend/app/middleware_llm_guard.py
# Objet  : Garde-fous LLM (entrée/contexte/sortie).
# ============================================================

from __future__ import annotations

import re

from backend.core.settings import get_settings


def sanitize_input(payload: dict) -> dict:
    """Nettoie le payload d'entrée (taille, patterns interdits).

    - Trim des champs texte.
    - Longueur max question configurable via env `LLM_GUARD_MAX_INPUT_LEN` (défaut 1000).
    - Denylist FR/EN de tentatives de prompt-injection (multi-casse).
    - Si `LLM_GUARD_ENABLE=false`, seul le trim est appliqué.
    Lève ValueError en cas de violation.
    """
    settings = get_settings()
    data = dict(payload)
    question = str(data.get("question", ""))
    q = question.strip()

    if not q:
        raise ValueError("empty_question")

    # If guard disabled, only return trimmed content
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
        # FR variants
        r"ignore\s+les\s+instructions\s+précédentes",
        r"ignore\s+les\s+instructions\s+precedentes",
        r"ignorer\s+les\s+instructions\s+précédentes",
        r"ignorer\s+les\s+instructions\s+precedentes",
    ]
    for pat in patterns:
        if re.search(pat, q, flags=re.IGNORECASE):
            raise ValueError("prompt_injection_detected")

    data["question"] = q
    return data


def enforce_policies(context: dict) -> dict:
    """Applique des politiques simples (placeholder).

    Pour MVP: pass-through. Point d'extension pour RBAC/tenant isolation.
    """
    return dict(context)


def validate_output(text: str, tenant: str | None) -> str:
    """Validate and filter output (PII masking, leaks).

    - Mask emails.
    - Mask simple phone numbers.
    - If `LLM_GUARD_ENABLE=false`, return the text unchanged.
    """
    settings = get_settings()
    if not getattr(settings, "LLM_GUARD_ENABLE", True):
        return text

    masked = text
    # Emails
    masked = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[redacted-email]", masked)
    # Téléphones (très simple): séquences de 8+ chiffres avec séparateurs
    masked = re.sub(r"\+?\d[\d\s\-]{7,}\d", "[redacted-phone]", masked)
    return masked
