"""
Gestion des entitlements utilisateur pour l'autorisation.

Ce module fournit les fonctions de vérification des permissions utilisateur pour contrôler l'accès
aux fonctionnalités premium de l'application.
"""

from fastapi import HTTPException


def require_entitlement(user: dict, entitlement: str):
    """
    Vérifie qu'un utilisateur possède un entitlement spécifique.

    Args:
        user: Dictionnaire contenant les informations utilisateur.
        entitlement: Nom de l'entitlement requis.

    Raises:
        HTTPException: Si l'utilisateur ne possède pas l'entitlement requis.
    """
    ents = set(user.get("entitlements", []))
    if entitlement not in ents:
        raise HTTPException(
            status_code=403, detail=f"missing_entitlement:{entitlement}"
        )
