"""
Tests pour la validation des tenants.

Ce module teste les fonctions de validation et de normalisation des identifiants de tenants dans
l'application.
"""

from __future__ import annotations

from backend.domain.tenancy import normalize_tenant, safe_tenant


def test_normalize_tenant_valid_and_invalid() -> None:
    """Teste la normalisation des identifiants de tenants."""
    assert normalize_tenant(" Tenant_01 ") == "tenant_01"
    assert normalize_tenant("") is None
    assert normalize_tenant("..") is None
    assert normalize_tenant("A" * 65) is None


def test_safe_tenant_defaults() -> None:
    """Teste que les tenants invalides utilisent la valeur par défaut."""
    assert safe_tenant("OK") == "ok"
    assert safe_tenant("..", default="default") == "default"
