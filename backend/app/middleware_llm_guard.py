# ============================================================
# Module : backend/app/middleware_llm_guard.py
# Objet  : Garde-fous LLM (entrée/contexte/sortie).
# ============================================================

from __future__ import annotations

import re


def sanitize_input(payload: dict) -> dict:
    """Nettoie le payload d'entrée (taille, patterns interdits).

    - Trim des champs texte.
    - Longueur max question: 1000 caractères.
    - Détection de tentatives de prompt-injection basiques (deny-list) → ValueError.
    """
    data = dict(payload)
    question = str(data.get("question", ""))
    q = question.strip()
    if not q:
        raise ValueError("empty_question")
    if len(q) > 1000:
        raise ValueError("question_too_long")

    patterns = [
        r"ignore\s+previous\s+instructions",
        r"system\s+prompt",
        r"jailbreak",
        r"do\s+anything\s+now",
    ]
    lower = q.lower()
    for pat in patterns:
        if re.search(pat, lower):
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

    - Masque emails.
    - Masque numéros de téléphone simples.
    - Future: filtrage de contenu interdit.
    """
    masked = text
    # Emails
    masked = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[redacted-email]", masked)
    # Téléphones (très simple): séquences de 8+ chiffres avec séparateurs
    masked = re.sub(r"\+?\d[\d\s\-]{7,}\d", "[redacted-phone]", masked)
    return masked
