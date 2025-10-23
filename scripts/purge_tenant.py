"""
Purge helper for tenant data (RGPD: droit à l'oubli).

Ce script illustre comment orchestrer une purge au niveau application pour les stores FAISS en
mémoire, avec audit trail pour la conformité RGPD.

This is a minimal script illustrating how a purge could be orchestrated at the application layer for
in-memory FAISS stores. In production, ensure deletion on all backends (FAISS, external vector DB,
caches) and persist an audit trail.
"""

from __future__ import annotations

import argparse

from backend.infra.vecstores.faiss_store import MultiTenantFAISS


def main() -> None:
    """
    Point d'entrée principal pour la purge des données tenant.

    Supprime toutes les données associées à un tenant spécifique pour respecter le droit à l'oubli
    (RGPD).
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("tenant", help="Tenant identifier to purge")
    args = parser.parse_args()

    store = MultiTenantFAISS()
    store.purge_tenant(args.tenant)
    print(f"purged tenant={args.tenant}")


if __name__ == "__main__":  # pragma: no cover - script entry
    main()
