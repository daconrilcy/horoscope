# ============================================================
# Module : backend/tasks/utils.py
# Objet  : Utilitaires tasks (idempotence).
# ============================================================

from __future__ import annotations

import hashlib


def idempotency_key(payload: dict, fields: list[str]) -> str:
    """Construit une clé d'idempotence à partir de champs du payload.

    Args:
        payload: dictionnaire d'entrée.
        fields: champs à concaténer.
    Returns:
        Empreinte hexadécimale stable.
    """
    parts: list[str] = []
    for f in fields:
        parts.append(str(payload.get(f, "")))
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
