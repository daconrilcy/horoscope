"""Tenancy utilities and RGPD helpers.

Provides simple helpers to derive a safe tenant label and constants for defaults. This module does
not trust frontend headers in production; prefer deriving the tenant from authenticated user claims.
"""

from __future__ import annotations

import re
from typing import Any

DEFAULT_TENANT = "default"
_SAFE_TENANT_RE = re.compile(r"^[a-z0-9_-]{1,64}$")


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


def normalize_tenant(value: str | None) -> str | None:
    """Normalize tenant to lowercase trimmed string if it matches the safe regex.

    Returns None if value is falsy or does not match the allowed pattern.
    """
    if not value:
        return None
    t = value.strip().lower()
    if _SAFE_TENANT_RE.match(t):
        return t
    return None


def safe_tenant(value: str | None, default: str = DEFAULT_TENANT) -> str:
    """Return a safe tenant value (normalized) or the provided default."""
    return normalize_tenant(value) or default
