# ============================================================
# Module : backend/app/middleware_llm_guard.py
# Objet  : Garde-fous LLM (entrée/contexte/sortie).
# ============================================================

from __future__ import annotations


def sanitize_input(payload: dict) -> dict:
    """Nettoie le payload d'entrée (taille, patterns interdits).

    Args:
        payload: dictionnaire d'entrée utilisateur.
    Returns:
        Payload nettoyé/normalisé.
    Raises:
        ValueError: si le payload est invalide.
    """
    # TODO: bornes de taille/longueur champs, listes deny-list, etc.
    return payload


def enforce_policies(context: dict) -> dict:
    """Applique les politiques de contexte (RBAC/entitlements/tenant).

    Args:
        context: Contexte appelant (tenant, rôles, etc.).
    Returns:
        Contexte borné et sûr.
    """
    # TODO: scoping strict, no cross-tenant
    return context


def validate_output(text: str, tenant: str | None) -> str:
    """Validate and filter output (PII masking, leaks).

    Args:
        text: Réponse générée par le LLM.
        tenant: Identifiant tenant (facultatif).
    Returns:
        Texte validé/épuré.
    """
    # TODO: masquage PII (regex), règles de contenu interdit
    return text
