"""Tenancy utilities and RGPD helpers.

Provides simple helpers to derive a safe tenant label and constants for
defaults. This module does not trust frontend headers in production; prefer
deriving the tenant from authenticated user claims.
"""

from __future__ import annotations

from typing import Any

DEFAULT_TENANT = "default"


def tenant_from_context(user: dict[str, Any] | None, header_tenant: str | None) -> str:
    """Return a tenant label from context.

    Preference order:
    1) user["tenant"] if present (JWT/claims)
    2) header_tenant (e.g., injected by trusted auth proxy)
    3) "default"
    """
    if user and isinstance(user.get("tenant"), str) and user["tenant"].strip():
        return user["tenant"].strip()
    if header_tenant and header_tenant.strip():
        return header_tenant.strip()
    return DEFAULT_TENANT

