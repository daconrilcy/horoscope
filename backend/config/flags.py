"""Gestion des feature flags pour la migration de récupération.

Ce module gère les flags de fonctionnalités pour contrôler le comportement
de la migration de récupération avec support pour le dual-write et shadow-read.

Feature flags for retrieval migration (dual-write, shadow-read).

Defaults: OFF. Values can be toggled via environment variables or settings.

Env vars (truthy if in {"1","true","yes","on"}, case-insensitive):
- FF_RETRIEVAL_DUAL_WRITE | RETRIEVAL_DUAL_WRITE
- FF_RETRIEVAL_SHADOW_READ | RETRIEVAL_SHADOW_READ
"""

from __future__ import annotations

import os

from backend.core.container import container

_TRUE = {"1", "true", "yes", "on"}


def _get_bool(*env_keys: str, fallback_setting: str | None = None, default: bool = False) -> bool:
    """Read a boolean from env or settings.

    Args:
        env_keys: Environment variable names to try in order.
        fallback_setting: Optional attribute name on settings.
        default: Default value if not found.
    Returns:
        bool: Effective flag value.
    """
    for k in env_keys:
        v = os.getenv(k)
        if v is not None:
            return str(v).strip().lower() in _TRUE
    if fallback_setting:
        try:
            val = getattr(container.settings, fallback_setting)
            if isinstance(val, bool):
                return val
            if val is not None:
                return str(val).strip().lower() in _TRUE
        except Exception:
            pass
    return default


def ff_retrieval_dual_write() -> bool:
    """Return whether dual-write to target is enabled (default OFF)."""
    return _get_bool(
        "FF_RETRIEVAL_DUAL_WRITE",
        "RETRIEVAL_DUAL_WRITE",
        fallback_setting="RETRIEVAL_DUAL_WRITE",
        default=False,
    )


def ff_retrieval_shadow_read() -> bool:
    """Return whether shadow-read is enabled (default OFF)."""
    return _get_bool(
        "FF_RETRIEVAL_SHADOW_READ",
        "RETRIEVAL_SHADOW_READ",
        fallback_setting="RETRIEVAL_SHADOW_READ",
        default=False,
    )


def shadow_sample_rate() -> float:
    """Return shadow-read sampling rate in [0,1] (default 0.25)."""
    raw = (
        os.getenv("FF_RETRIEVAL_SHADOW_SAMPLE_RATE")
        or os.getenv("RETRIEVAL_SHADOW_SAMPLE_RATE")
        or "0.25"
    )
    try:
        v = float(str(raw))
        if v < 0.0:
            return 0.0
        if v > 1.0:
            return 1.0
        return v
    except Exception:
        return 0.25


def tenant_allowlist() -> set[str]:
    """Return allowlisted tenants for shadow-read; empty set means allow all."""
    raw = os.getenv("RETRIEVAL_TENANT_ALLOWLIST") or ""
    vals = [x.strip() for x in raw.split(",") if x.strip()]
    return set(vals)
