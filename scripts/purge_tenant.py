from __future__ import annotations

"""Purge helper for tenant data (RGPD: droit à l'oubli).

This is a minimal script illustrating how a purge could be orchestrated at the
application layer for in-memory FAISS stores. In production, ensure deletion on
all backends (FAISS, external vector DB, caches) and persist an audit trail.
"""

import argparse

from backend.infra.vecstores.faiss_store import MultiTenantFAISS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tenant", help="Tenant identifier to purge")
    args = parser.parse_args()

    store = MultiTenantFAISS()
    store.purge_tenant(args.tenant)
    print(f"purged tenant={args.tenant}")


if __name__ == "__main__":  # pragma: no cover - script entry
    main()

