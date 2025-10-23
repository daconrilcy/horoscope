"""
Utilitaires d'authentification et extraction sécurisée des tenants.

Ce module implémente le trust model pour l'extraction des tenants :
- JWT = source de vérité
- Headers client ne surclassent jamais le JWT
- Détection et traçage des tentatives de spoof
"""

import logging
from typing import Any

from fastapi import Request

from backend.apigw.internal_auth import verify_internal_traffic
from backend.app.metrics import APIGW_TENANT_SPOOF_ATTEMPTS, normalize_route
from backend.domain.tenancy import safe_tenant

log = logging.getLogger(__name__)


def extract_tenant_secure(request: Request) -> tuple[str, str, bool]:
    """
    Extract tenant identifier with secure trust model.

    Trust model:
    1. JWT claims (tenant_id) = source of truth
    2. X-Tenant-ID header only accepted if internal traffic
    3. Otherwise → default tenant
    4. If header contradicts JWT non-internal → spoof detected

    Args:
        request: FastAPI request object

    Returns:
        Tuple of (tenant_id, source, is_spoof)
        - tenant_id: extracted tenant identifier
        - source: "jwt", "header", or "default"
        - is_spoof: True if spoof attempt detected
    """
    route = normalize_route(request.url.path)
    tenant_header = request.headers.get("X-Tenant-ID")
    is_internal = verify_internal_traffic(request)

    # Try to get tenant from JWT/authenticated user context
    jwt_tenant = _extract_tenant_from_jwt(request)

    if jwt_tenant:
        # JWT is source of truth
        if tenant_header and tenant_header != jwt_tenant and not is_internal:
            # Spoof attempt: header contradicts JWT in non-internal traffic
            log.warning(
                "Tenant spoof attempt detected",
                extra={
                    "route": route,
                    "jwt_tenant": jwt_tenant,
                    "header_tenant": tenant_header,
                    "trace_id": getattr(request.state, "trace_id", None),
                },
            )

            # Increment spoof counter
            APIGW_TENANT_SPOOF_ATTEMPTS.labels(route=route).inc()

            return jwt_tenant, "jwt", True

        return jwt_tenant, "jwt", False

    # No JWT tenant, check header
    if tenant_header and is_internal:
        # Internal traffic can use header
        return safe_tenant(tenant_header), "header", False

    # Fallback to default tenant
    return safe_tenant("public"), "default", False


def _extract_tenant_from_jwt(request: Request) -> str | None:
    """Extract tenant from JWT claims or authenticated user context."""
    # Try to get tenant from JWT claims first (higher priority)
    if hasattr(request.state, "jwt_claims") and request.state.jwt_claims is not None:
        tenant_id = request.state.jwt_claims.get("tenant_id")
        if tenant_id:
            return safe_tenant(tenant_id)

    # Try to get tenant from authenticated user context
    if hasattr(request.state, "user") and request.state.user:
        user_tenant = getattr(request.state.user, "tenant", None)
        if user_tenant:
            return safe_tenant(user_tenant)

    return None


def _is_internal_traffic(request: Request) -> bool:
    """
    Check if request is from internal/trusted source (legacy function).

    This function is kept for backward compatibility but should not be used. Use
    verify_internal_traffic from internal_auth module instead.
    """
    # This is a placeholder - implement based on your infrastructure
    return False


def get_tenant_source_info(request: Request) -> dict[str, Any]:
    """
    Get detailed tenant source information for logging.

    Returns:
        Dictionary with tenant source information
    """
    tenant, source, is_spoof = extract_tenant_secure(request)

    return {
        "tenant": tenant,
        "tenant_source": source,
        "spoof": is_spoof,
        "route": normalize_route(request.url.path),
        "trace_id": getattr(request.state, "trace_id", None),
    }
